import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pypdf import PdfReader
from dotenv import load_dotenv

from database import (
    applications_collection,
    chat_history_collection,
    retrieval_collection,
    retrieval_metrics_collection,
    build_application_upsert_filter,
    build_document_fingerprint,
    get_effective_application_id,
)
from services import AIService, PDFService

logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="GenAI Credit Risk Analyzer")


@app.on_event("startup")
async def startup_event():
    await applications_collection.create_index([("application_id", 1)], unique=True, sparse=True)
    await applications_collection.create_index([("applicant_id", 1)], unique=True, sparse=True)
    await applications_collection.create_index([("document_hash", 1)], unique=True, sparse=True)
    await applications_collection.create_index([("created_at", -1)])
    await retrieval_collection.create_index([("application_id", 1), ("chunk_index", 1)])
    await retrieval_collection.create_index([("document_hash", 1)])
    await retrieval_metrics_collection.create_index([("application_id", 1), ("created_at", -1)])


allowed_origins = {
    os.getenv("FRONTEND_URL", "http://localhost:5173"),
    "http://localhost:5173",
    "http://localhost:3000",
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    application_id: str | None = None
    applicant_id: str | None = None
    scope: str = "application"
    message: str


def parse_pdf_text(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        extracted = "".join([page.extract_text() or "" for page in reader.pages])
        return extracted.strip()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PDF reading error: {str(exc)}")


def normalize_risk_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def calculate_dashboard_summary(applications: list[dict] | None) -> dict:
    records = applications or []
    total_applications = len(records)
    low_risk = sum(1 for app in records if "low" in normalize_risk_value(app.get("risk_level")))
    medium_risk = sum(1 for app in records if "medium" in normalize_risk_value(app.get("risk_level")))
    high_risk = sum(1 for app in records if "high" in normalize_risk_value(app.get("risk_level")))

    recent_applications = sorted(
        records,
        key=lambda app: str(app.get("created_at") or app.get("updated_at") or "1970-01-01T00:00:00"),
        reverse=True,
    )[:5]

    return {
        "total_applications": total_applications,
        "low_risk": low_risk,
        "medium_risk": medium_risk,
        "high_risk": high_risk,
        "recent_applications": [
            {
                "application_id": app.get("application_id"),
                "applicant_name": app.get("applicant_name"),
                "risk_level": app.get("risk_level"),
                "credit_score": app.get("credit_score"),
                "requested_loan_amount": app.get("requested_loan_amount"),
                "monthly_salary": app.get("monthly_salary"),
                "company_name": app.get("company_name"),
                "created_at": app.get("created_at"),
            }
            for app in recent_applications
        ],
    }


async def analyze_uploaded_pdf(file_name: str, file_bytes: bytes) -> dict:
    raw_text = parse_pdf_text(file_bytes)

    if not raw_text or len(raw_text.strip()) < 15:
        return {
            "status": "DATA_NOT_FOUND",
            "message": "Data not found in the uploaded PDF.",
            "data": None,
        }

    try:
        extracted = await AIService.analyze_document_text(raw_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(exc)}")

    status = "MISSING_FIELDS" if extracted.get("missing_critical_fields") else "SUCCESS"

    document_hash = build_document_fingerprint(raw_text)
    application_id = get_effective_application_id(extracted)
    lookup_filter = build_application_upsert_filter(extracted, raw_text)
    existing_record = await applications_collection.find_one(lookup_filter)

    now = datetime.utcnow()
    normalized_extracted = {
        **extracted,
        "application_id": application_id,
        "raw_text": raw_text,
        "filename": file_name,
        "document_hash": document_hash,
        "status": status,
        "created_at": existing_record.get("created_at") if existing_record else now,
        "updated_at": now,
    }
    if "applicant_id" in normalized_extracted:
        normalized_extracted.pop("applicant_id")

    record = normalized_extracted

    if application_id:
        update_filter = {"application_id": application_id}
    else:
        update_filter = {"document_hash": document_hash}

    result = await applications_collection.update_one(update_filter, {"$set": record}, upsert=True)

    try:
        await AIService.index_application_chunks(record)
    except Exception:
        logger.exception("Failed to index retrieval chunks for application %s", application_id)

    record["application_updated"] = bool(result.upserted_id is None)
    return {"status": status, "data": record}


@app.post("/api/analyze")
async def analyze_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()
    return await analyze_uploaded_pdf(file.filename, file_bytes)


@app.post("/api/analyze-bulk")
async def analyze_bulk_pdfs(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF file is required.")

    processed_files: list[dict] = []
    valid_applications: list[dict] = []

    for uploaded_file in files:
        if not uploaded_file.filename or not uploaded_file.filename.lower().endswith(".pdf"):
            processed_files.append({
                "filename": uploaded_file.filename or "unknown.pdf",
                "status": "INVALID_FILE",
                "message": "Only PDF files are supported.",
            })
            continue

        try:
            file_bytes = await uploaded_file.read()
            result = await analyze_uploaded_pdf(uploaded_file.filename, file_bytes)
            processed_files.append({
                "filename": uploaded_file.filename,
                "status": result.get("status", "ERROR"),
                "message": result.get("message"),
                "data": result.get("data"),
            })
            if result.get("data"):
                valid_applications.append(result["data"])
        except Exception as exc:
            processed_files.append({
                "filename": uploaded_file.filename,
                "status": "ERROR",
                "message": str(exc),
            })

    return {
        "status": "SUCCESS" if processed_files else "ERROR",
        "results": processed_files,
        "summary": calculate_dashboard_summary(valid_applications),
    }


@app.get("/api/dashboard")
async def dashboard_summary():
    applications = await applications_collection.find({}).sort("created_at", -1).to_list(length=200)
    summary = calculate_dashboard_summary(applications)
    return {
        "summary": summary,
        "recent_applications": summary.get("recent_applications", []),
    }


@app.post("/api/chat")
async def chat_handler(req: ChatRequest):
    scope = (req.scope or "application").lower()

    if scope == "global":
        portfolio_apps = await applications_collection.find({}).sort("created_at", -1).to_list(length=50)
        if not portfolio_apps:
            raise HTTPException(status_code=404, detail="No applications found in the portfolio yet.")

        history = []
        try:
            reply = await AIService.chat_portfolio_response(portfolio_apps, history, req.message)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Portfolio chat generation failed: {str(exc)}")

        return {"reply": reply, "scope": "global"}

    lookup_id = req.application_id or req.applicant_id
    if not lookup_id:
        raise HTTPException(status_code=400, detail="Application ID is required for single-application mode.")

    app_doc = await applications_collection.find_one({"application_id": lookup_id})
    if not app_doc:
        app_doc = await applications_collection.find_one({"applicant_id": lookup_id})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Application record not found.")

    cursor = chat_history_collection.find({"application_id": lookup_id}).sort("_id", -1).limit(6)
    history = await cursor.to_list(length=6)
    history.reverse()

    try:
        reply = await AIService.chat_rag_response(app_doc, history, req.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {str(exc)}")

    await chat_history_collection.insert_one({
        "application_id": lookup_id,
        "user_msg": req.message,
        "assistant_msg": reply,
    })

    return {"reply": reply, "scope": "application"}


@app.get("/api/download-report")
async def download_report(application_id: str | None = Query(default=None), applicant_id: str | None = Query(default=None)):
    lookup_id = application_id or applicant_id
    if not lookup_id:
        raise HTTPException(status_code=400, detail="Application ID is required.")

    app_doc = await applications_collection.find_one({"application_id": lookup_id})
    if not app_doc:
        app_doc = await applications_collection.find_one({"applicant_id": lookup_id})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Application data not found.")

    pdf_buffer = PDFService.generate_analysis_pdf(app_doc)
    filename = f"Credit_Risk_Report_{lookup_id}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )