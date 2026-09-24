import os
from datetime import datetime
from io import BytesIO
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pypdf import PdfReader
from pydantic import BaseModel
from dotenv import load_dotenv

from database import (
    applications_collection,
    chat_history_collection,
    build_application_upsert_filter,
    build_document_fingerprint,
    get_effective_application_id,
)
from services import AIService, PDFService

load_dotenv()

app = FastAPI(title="GenAI Credit Risk Analyzer")

@app.on_event("startup")
async def startup_event():
    await applications_collection.create_index([("application_id", 1)], unique=True, sparse=True)
    await applications_collection.create_index([("applicant_id", 1)], unique=True, sparse=True)
    await applications_collection.create_index([("document_hash", 1)], unique=True, sparse=True)
    await applications_collection.create_index([("created_at", -1)])

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
    message: str

def parse_pdf_text(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        extracted = "".join([p.extract_text() or "" for p in reader.pages])
        return extracted.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF reading error: {str(e)}")

@app.get("/")
def health_check():
    return {"status": "Online", "service": "Credit Risk Analyzer Backend"}

@app.post("/api/analyze")
async def analyze_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()
    raw_text = parse_pdf_text(file_bytes)

    if not raw_text or len(raw_text.strip()) < 15:
        return {
            "status": "DATA_NOT_FOUND",
            "message": "Data not found in the uploaded PDF.",
            "data": None
        }

    try:
        extracted = await AIService.analyze_document_text(raw_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(e)}")

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
        "filename": file.filename,
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

    result = await applications_collection.update_one(
        update_filter,
        {"$set": record},
        upsert=True
    )

    if result.upserted_id:
        record["application_updated"] = False
    else:
        record["application_updated"] = True

    return {"status": status, "data": record}

@app.post("/api/chat")
async def chat_handler(req: ChatRequest):
    lookup_id = req.application_id or req.applicant_id
    if not lookup_id:
        raise HTTPException(status_code=400, detail="Application ID is required.")

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {str(e)}")

    await chat_history_collection.insert_one({
        "application_id": lookup_id,
        "user_msg": req.message,
        "assistant_msg": reply
    })

    return {"reply": reply}

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
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )