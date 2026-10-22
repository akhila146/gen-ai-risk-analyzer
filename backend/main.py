import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints
from pypdf import PdfReader
import docx
from dotenv import load_dotenv

from database import (
    applications_collection,
    build_application_upsert_filter,
    build_document_fingerprint,
    get_effective_application_id,
    sessions_collection,
    users_collection,
)
from auth import (
    LoginRequest,
    SignupRequest,
    get_current_user,
    login_account,
    logout_account,
    public_user,
    register_account,
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
    await users_collection.create_index("email", unique=True)
    await sessions_collection.create_index("token_hash", unique=True)
    await sessions_collection.create_index("expires_at", expireAfterSeconds=0)


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

ChatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


@app.post("/api/auth/signup")
async def signup(request: SignupRequest):
    user = await register_account(request)
    return {"user": user}


@app.post("/api/auth/login")
async def login(request: LoginRequest, response: Response):
    user = await login_account(request, response)
    return {"user": user}


@app.get("/api/auth/me")
async def current_user(user: dict = Depends(get_current_user)):
    return {"user": public_user(user)}


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    return await logout_account(request, response)


class ChatTurn(BaseModel):
    user_msg: ChatText
    assistant_msg: Annotated[str, StringConstraints(min_length=1, max_length=16000)]

class ChatRequest(BaseModel):
    application_id: str | None = None
    applicant_id: str | None = None
    scope: Literal["application", "global", "general"] = "general"
    message: ChatText
    history: list[ChatTurn] = Field(default_factory=list, max_length=6)


def parse_file_content(file_bytes: bytes, filename: str) -> tuple[str | None, bytes | None, str | None]:
    """
    Parses different file types and returns text or raw bytes for multimodal/OCR analysis.
    Returns: (extracted_text, raw_image_bytes, mime_type)
    """
    ext = filename.lower().split('.')[-1]
    
    if ext == "pdf":
        try:
            reader = PdfReader(BytesIO(file_bytes))
            extracted = "".join([page.extract_text() or "" for page in reader.pages])
            return extracted.strip(), None, None
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"PDF reading error: {str(exc)}")
            
    elif ext == "docx":
        try:
            doc = docx.Document(BytesIO(file_bytes))
            extracted = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return extracted.strip(), None, None
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"DOCX reading error: {str(exc)}")
            
    elif ext in ["txt", "csv"]:
        try:
            return file_bytes.decode("utf-8", errors="ignore").strip(), None, None
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Text reading error: {str(exc)}")
            
    elif ext in ["png", "jpg", "jpeg", "webp"]:
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp"
        }
        return None, file_bytes, mime_map.get(ext, "image/jpeg")
        
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: .{ext}")


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


async def analyze_uploaded_file(file_name: str, file_bytes: bytes) -> dict:
    extracted_text, image_bytes, mime_type = parse_file_content(file_bytes, file_name)

    if extracted_text and len(extracted_text.strip()) < 15 and not image_bytes:
        return {
            "status": "DATA_NOT_FOUND",
            "message": "Data not found in the uploaded file.",
            "data": None,
        }

    try:
        if image_bytes and mime_type:
            extracted = await AIService.analyze_document_text(image_bytes=image_bytes, mime_type=mime_type)
            raw_text = f"[Multimodal Image Document: {file_name}]"
        else:
            extracted = await AIService.analyze_document_text(raw_text=extracted_text)
            raw_text = extracted_text
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
async def analyze_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    file_bytes = await file.read()
    return await analyze_uploaded_file(file.filename or "unknown", file_bytes)


@app.post("/api/analyze-bulk")
async def analyze_bulk_files(files: list[UploadFile] = File(...), user: dict = Depends(get_current_user)):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    processed_files: list[dict] = []
    valid_applications: list[dict] = []

    for uploaded_file in files:
        filename = uploaded_file.filename or "unknown"
        try:
            file_bytes = await uploaded_file.read()
            result = await analyze_uploaded_file(filename, file_bytes)
            processed_files.append({
                "filename": filename,
                "status": result.get("status", "ERROR"),
                "message": result.get("message"),
                "data": result.get("data"),
            })
            if result.get("data"):
                valid_applications.append(result["data"])
        except Exception as exc:
            processed_files.append({
                "filename": filename,
                "status": "ERROR",
                "message": str(exc),
            })

    return {
        "status": "SUCCESS" if processed_files else "ERROR",
        "results": processed_files,
        "summary": calculate_dashboard_summary(valid_applications),
    }


@app.get("/api/dashboard")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    applications = await applications_collection.find({}).sort("created_at", -1).to_list(length=200)
    summary = calculate_dashboard_summary(applications)
    return {
        "summary": summary,
        "recent_applications": summary.get("recent_applications", []),
    }


@app.post("/api/chat")
async def chat_handler(req: ChatRequest, user: dict = Depends(get_current_user)):
    history = [turn.model_dump() for turn in req.history]
    lookup_id = req.application_id or req.applicant_id
    scope = req.scope if req.scope == "global" or lookup_id else "general"
    try:
        if scope == "global":
            portfolio_apps = await applications_collection.find({}).sort("created_at", -1).to_list(length=50)
            reply = await AIService.chat_portfolio_response(
                portfolio_apps, history, req.message,
            )
        elif scope == "application":
            app_doc = await applications_collection.find_one({"application_id": lookup_id})
            if not app_doc:
                app_doc = await applications_collection.find_one({"applicant_id": lookup_id})
            if app_doc:
                reply = await AIService.chat_rag_response(
                    app_doc, history, req.message,
                )
            else:
                reply = AIService.generate_chat_response(
                    {"availability": "The selected application record is not available."},
                    history, req.message,
                )
        else:
            portfolio_apps = await applications_collection.find({}).sort("created_at", -1).to_list(length=50)
            app_doc = None
            if lookup_id:
                app_doc = await applications_collection.find_one({"application_id": lookup_id})
                if not app_doc:
                    app_doc = await applications_collection.find_one({"applicant_id": lookup_id})
            reply = await AIService.chat_portfolio_response(
                portfolio_apps, history, req.message,
                app_doc=app_doc, selected_application_id=lookup_id,
            )
    except Exception:
        logger.exception("Chat response failed")
        raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable. Please try again.") from None

    return {"reply": reply, "scope": scope}


@app.get("/api/download-report")
async def download_report(
    application_id: str | None = Query(default=None),
    applicant_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
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