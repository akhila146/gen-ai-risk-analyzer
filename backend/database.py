import hashlib
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "credit_risk_db")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


def build_document_fingerprint(raw_text: str) -> str:
    normalized_text = (raw_text or "").strip()
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def normalize_application_id(value):
    if value is None:
        return None

    normalized = str(value).strip()
    if not normalized:
        return None

    normalized = normalized.replace(" ", "")
    normalized = normalized.upper()

    invalid_values = {"", "N/A", "NA", "UNKNOWN", "UNKNOWN_APP", "NULL", "NONE"}
    if normalized in invalid_values:
        return None
    return normalized


def normalize_applicant_id(applicant_id):
    return normalize_application_id(applicant_id)


def get_effective_application_id(extracted: dict):
    if not isinstance(extracted, dict):
        return None

    application_id = normalize_application_id(extracted.get("application_id"))
    applicant_id = normalize_application_id(extracted.get("applicant_id"))

    if application_id and applicant_id and application_id == applicant_id:
        return application_id
    if application_id:
        return application_id
    return applicant_id


def get_effective_applicant_id(extracted: dict):
    return get_effective_application_id(extracted)


def build_application_upsert_filter(extracted: dict, raw_text: str) -> dict:
    document_hash = build_document_fingerprint(raw_text)
    application_id = get_effective_application_id(extracted)

    if application_id:
        return {"application_id": application_id}

    return {"document_hash": document_hash}


applications_collection = db["applications"]
chat_history_collection = db["chat_history"]
retrieval_metrics_collection = db["retrieval_metrics"]