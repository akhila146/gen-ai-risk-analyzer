import os
import json
import logging
import re
import time
from io import BytesIO
from google import genai
from google.genai import errors
from google.genai import types
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from datetime import datetime
from database import retrieval_collection, retrieval_metrics_collection

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

GENERATION_MODEL = os.getenv("GEMINI_GENERATION_MODEL", "gemini-2.5-flash")
GENERATION_FALLBACK_MODELS = tuple(
    model.strip()
    for model in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",")
    if model.strip() and model.strip() != GENERATION_MODEL
)
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
logger = logging.getLogger(__name__)


def generate_content_with_retry(**kwargs):
    primary_model = kwargs.pop("model", GENERATION_MODEL)
    models = (primary_model,) + tuple(
        model for model in GENERATION_FALLBACK_MODELS if model != primary_model
    )

    for model_index, model_name in enumerate(models):
        attempts = 3 if model_index == 0 else 1
        for attempt in range(attempts):
            try:
                return gemini_client.models.generate_content(model=model_name, **kwargs)
            except errors.ServerError as exc:
                if exc.code != 503:
                    raise
                if attempt < attempts - 1:
                    delay = attempt + 1
                    logger.warning(
                        "Gemini model %s returned 503; retrying in %s second(s).",
                        model_name,
                        delay,
                    )
                    time.sleep(delay)
                elif model_index < len(models) - 1:
                    logger.warning(
                        "Gemini model %s remains unavailable; trying configured fallback model.",
                        model_name,
                    )
                else:
                    raise


# --- 1. AI Analysis & RAG Service ---
class AIService:
    DEFAULT_MIN_RETRIEVAL_SCORE = 0.14
    MAX_CONTEXT_CHUNKS = 4

    @staticmethod
    def split_text_into_chunks(raw_text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
        if not raw_text or not raw_text.strip():
            return []

        cleaned = re.sub(r"\s+", " ", raw_text).strip()
        if len(cleaned) <= chunk_size:
            return [cleaned]

        chunks = []
        start = 0
        while start < len(cleaned):
            end = min(start + chunk_size, len(cleaned))
            if end < len(cleaned):
                split_point = cleaned.rfind(" ", start, end)
                if split_point > start + max(int(chunk_size * 0.6), 80):
                    end = split_point

            chunk = cleaned[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= len(cleaned):
                break

            start = max(start + chunk_size - overlap, end)

        return chunks

    @staticmethod
    def _normalize_token(token: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (token or "").lower())

    @staticmethod
    def _keyword_overlap_score(question: str, chunk: str) -> float:
        question_tokens = {
            AIService._normalize_token(token)
            for token in re.split(r"\s+", question.lower())
            if AIService._normalize_token(token)
        }
        chunk_tokens = {
            AIService._normalize_token(token)
            for token in re.split(r"\s+", chunk.lower())
            if AIService._normalize_token(token)
        }

        if not question_tokens or not chunk_tokens:
            return 0.0

        overlap = question_tokens & chunk_tokens
        if not overlap:
            return 0.0

        return len(overlap) / max(len(question_tokens), 1)

    @staticmethod
    def _compute_cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
        if not vector_a or not vector_b:
            return 0.0

        if len(vector_a) != len(vector_b):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
        magnitude_a = sum(a * a for a in vector_a) ** 0.5
        magnitude_b = sum(b * b for b in vector_b) ** 0.5

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    @staticmethod
    def _get_embedding_vector(text: str, *, is_query: bool = False) -> list[float]:
        if not text or not text.strip():
            return []

        contents = (
            f"task: question answering | query: {text.strip()}"
            if is_query
            else f"title: none | text: {text.strip()}"
        )
        try:
            response = gemini_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=contents
            )
            embeddings = getattr(response, "embeddings", None) or getattr(response, "data", None)
            if not embeddings:
                logger.warning("Embedding model %s returned no embeddings.", EMBEDDING_MODEL)
                return []

            values = embeddings[0].values if hasattr(embeddings[0], "values") else embeddings[0].get("values", [])
            if isinstance(values, (list, tuple)):
                vector = [float(value) for value in values]
                if vector:
                    return vector
            logger.warning("Embedding model %s returned an empty or invalid vector.", EMBEDDING_MODEL)
        except Exception:
            logger.exception("Embedding generation failed with model %s.", EMBEDDING_MODEL)
            return []

        return []

    @staticmethod
    async def index_application_chunks(app_doc: dict) -> None:
        application_id = app_doc.get("application_id") or app_doc.get("applicant_id")
        raw_text = app_doc.get("raw_text", "") or ""
        if not application_id or not raw_text.strip():
            return

        chunks = AIService.split_text_into_chunks(raw_text)
        chunk_documents = []
        for index, chunk in enumerate(chunks):
            chunk_documents.append({
                "application_id": application_id,
                "document_hash": app_doc.get("document_hash"),
                "chunk_index": index,
                "text": chunk,
                "embedding": AIService._get_embedding_vector(chunk),
                "embedding_model": EMBEDDING_MODEL,
                "metadata": {
                    "applicant_name": app_doc.get("applicant_name"),
                    "risk_level": app_doc.get("risk_level"),
                    "chunk_size": len(chunk),
                },
            })

        await retrieval_collection.delete_many({"application_id": application_id})
        if chunk_documents:
            await retrieval_collection.insert_many(chunk_documents)

    @staticmethod
    async def retrieve_relevant_chunks(app_doc: dict, question: str, top_k: int = 4, min_score: float | None = None) -> list[dict]:
        min_score = min_score if min_score is not None else AIService.DEFAULT_MIN_RETRIEVAL_SCORE
        application_id = app_doc.get("application_id") or app_doc.get("applicant_id")
        question_embedding = AIService._get_embedding_vector(question, is_query=True)
        ranked = []

        if application_id:
            stored_chunks = await retrieval_collection.find({"application_id": application_id}).sort("chunk_index", 1).to_list(length=200)
            if stored_chunks:
                for chunk_doc in stored_chunks:
                    chunk_text = chunk_doc.get("text") or ""
                    if not chunk_text:
                        continue
                    stored_embedding = chunk_doc.get("embedding") or []
                    if chunk_doc.get("embedding_model") == EMBEDDING_MODEL and stored_embedding:
                        embedding = stored_embedding
                    else:
                        embedding = AIService._get_embedding_vector(chunk_text)
                        if embedding and chunk_doc.get("_id") is not None:
                            await retrieval_collection.update_one(
                                {"_id": chunk_doc["_id"]},
                                {"$set": {"embedding": embedding, "embedding_model": EMBEDDING_MODEL}},
                            )

                    if question_embedding and embedding and len(question_embedding) == len(embedding):
                        score = AIService._compute_cosine_similarity(question_embedding, embedding)
                    else:
                        score = AIService._keyword_overlap_score(question, chunk_text)
                    ranked.append({
                        "chunk": chunk_text,
                        "score": score,
                        "metadata": chunk_doc.get("metadata", {}),
                        "chunk_index": chunk_doc.get("chunk_index", 0),
                    })

        if not ranked:
            raw_text = app_doc.get("raw_text", "") or ""
            for chunk in AIService.split_text_into_chunks(raw_text):
                chunk_embedding = AIService._get_embedding_vector(chunk)
                if question_embedding and chunk_embedding and len(question_embedding) == len(chunk_embedding):
                    score = AIService._compute_cosine_similarity(question_embedding, chunk_embedding)
                else:
                    score = AIService._keyword_overlap_score(question, chunk)
                ranked.append({
                    "chunk": chunk,
                    "score": score,
                    "metadata": {"fallback": True},
                    "chunk_index": 0,
                })

        ranked = sorted(ranked, key=lambda item: item["score"], reverse=True)
        filtered = [item for item in ranked if item["score"] >= min_score]
        if not filtered:
            filtered = ranked[:1]

        selected = filtered[:top_k]
        if not selected:
            return []

        return selected

    @staticmethod
    async def record_retrieval_metrics(application_id: str | None, question: str, results: list[dict]) -> None:
        if not application_id:
            return

        await retrieval_metrics_collection.insert_one({
            "application_id": application_id,
            "question": question,
            "retrieved_chunks": [
                {
                    "chunk_index": item.get("chunk_index"),
                    "score": item.get("score"),
                    "metadata": item.get("metadata", {}),
                }
                for item in results
            ],
            "created_at": datetime.utcnow(),
        })

    @staticmethod
    async def analyze_document_text(raw_text: str) -> dict:
        prompt = f"""
You are a Financial Credit Risk Analysis Engine. Analyze the following document text and return a STRICT JSON object only.

Document Text:
\"\"\"{raw_text}\"\"\"

Extraction & Risk Rules:
1. Extract:
   - application_id: (e.g. APP-XXXX-XXX or N/A)
   - applicant_name: (Full name or N/A)
   - contact_number: (or N/A)
   - company_name: (or N/A)
   - job_role: (or N/A)
   - monthly_salary: (numeric or string)
   - credit_score: (CIBIL/Credit score numeric value or null)
   - existing_emis: (or 0)
   - existing_liabilities: (or 0)
   - requested_loan_amount: (or 0)
   - loan_purpose: (or N/A)
   - own_house: ("Yes", "No", or "Rented")
   - vehicles: (e.g. "1 Car", "None")
   - home_loan_status: (or N/A)

2. Missing Fields Verification:
   - Identify if critical fields like 'credit_score', 'monthly_salary', or 'applicant_name' are missing or unspecified.
   - Populate `missing_critical_fields` array with missing field names.

3. Risk Level:
   - "Low Risk", "Medium Risk", "High Risk", or "Cannot Evaluate"
   - Low Risk: Credit score >= 720, manageable debt-to-income.
   - Medium Risk: Credit score 620-719, moderate debt load.
   - High Risk: Credit score < 620, high liabilities or low disposable income.
   - If missing critical information, set risk_level to "Cannot Evaluate".
4. recommendation: Action (e.g. "Proceed for Approval", "Additional Documentation / Manual review", "Enhanced Review").
5. key_factors: Array of 3 concise points justifying the assessment.
6. summary: Full profile summary paragraph.

Return ONLY raw valid JSON:
{{
  "application_id": "...",
  "applicant_name": "...",
  "contact_number": "...",
  "company_name": "...",
  "job_role": "...",
  "monthly_salary": "...",
  "credit_score": "...",
  "existing_emis": "...",
  "existing_liabilities": "...",
  "requested_loan_amount": "...",
  "loan_purpose": "...",
  "own_house": "...",
  "vehicles": "...",
  "home_loan_status": "...",
  "missing_critical_fields": [],
  "risk_level": "...",
  "recommendation": "...",
  "key_factors": ["...", "...", "..."],
  "summary": "..."
}}
"""
        response = generate_content_with_retry(
            model=GENERATION_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return json.loads(response.text)

    @staticmethod
    async def chat_portfolio_response(applications: list[dict], chat_history: list, question: str) -> str:
        if not applications:
            return "No applications are available in the portfolio yet."

        history_str = "".join([f"User: {h.get('user_msg')}\nAssistant: {h.get('assistant_msg')}\n" for h in chat_history])

        portfolio_lines = []
        for index, app in enumerate(applications[:20], start=1):
            app_id = app.get("application_id") or app.get("applicant_id") or f"APP-{index}"
            applicant_name = app.get("applicant_name") or "N/A"
            risk_level = app.get("risk_level") or "Unknown"
            credit_score = app.get("credit_score") or "N/A"
            monthly_salary = app.get("monthly_salary") or "N/A"
            requested_loan_amount = app.get("requested_loan_amount") or "N/A"
            existing_emis = app.get("existing_emis") or "N/A"
            existing_liabilities = app.get("existing_liabilities") or "N/A"
            own_house = app.get("own_house") or "N/A"
            vehicles = app.get("vehicles") or "N/A"
            home_loan_status = app.get("home_loan_status") or "N/A"
            company_name = app.get("company_name") or "N/A"
            job_role = app.get("job_role") or "N/A"
            loan_purpose = app.get("loan_purpose") or "N/A"
            recommendation = app.get("recommendation") or "N/A"

            portfolio_lines.append(
                f"{index}. Application ID: {app_id}; Applicant: {applicant_name}; "
                f"Company: {company_name}; Role: {job_role}; "
                f"Risk: {risk_level}; Credit Score: {credit_score}; "
                f"Monthly Salary: {monthly_salary}; Requested Loan: {requested_loan_amount}; "
                f"Existing EMIs: {existing_emis}; Existing Liabilities: {existing_liabilities}; "
                f"Own House: {own_house}; Vehicles: {vehicles}; Home Loan Status: {home_loan_status}; "
                f"Loan Purpose: {loan_purpose}; Recommendation: {recommendation}"
            )

        system_prompt = f"""
You are the Portfolio Credit Risk AI Assistant for the entire application portfolio.
Use only the portfolio data below to answer the user's question.

Portfolio Data:
{chr(10).join(portfolio_lines)}

Conversation History:
{history_str}

Critical instruction:
- Carefully inspect all fields in the portfolio data before answering.
- For questions about ownership, vehicle, liabilities, salary, risk, credit score, or loan details, use the exact values from the records above.
- Do not answer 'not available' when the field value is present in the portfolio data.
- If a field is missing, only then say it is not available.

Strict output rules:
1. Answer using only the portfolio data provided.
2. For direct factual questions like total applications, average credit score, risk counts, or applicant-specific values, return the exact answer.
3. When referencing applicants, include their application IDs exactly as they appear in the data, such as APP-101, APP-104.
4. Keep answers concise, business-friendly, and easy to read.
5. Do not start with phrases like 'Based on the portfolio data', 'According to', or 'From the retrieved evidence'.
6. For comparison or summary questions, provide a short answer with the relevant application IDs mentioned clearly.
"""

        response = generate_content_with_retry(
            model=GENERATION_MODEL,
            contents=f"{system_prompt}\nUser Question: {question}\nAssistant Answer:",
            config=types.GenerateContentConfig(temperature=0.2)
        )
        return response.text.strip()

    @staticmethod
    async def chat_rag_response(app_doc: dict, chat_history: list, question: str) -> str:
        history_str = "".join([f"User: {h.get('user_msg')}\nAssistant: {h.get('assistant_msg')}\n" for h in chat_history])
        relevant_chunks = await AIService.retrieve_relevant_chunks(app_doc, question, top_k=AIService.MAX_CONTEXT_CHUNKS)
        evidence_lines = []
        for idx, item in enumerate(relevant_chunks, start=1):
            chunk_text = item.get("chunk") or ""
            evidence_lines.append(f"[{idx}] {chunk_text}")
        evidence = "\n\n---\n\n".join(evidence_lines) if evidence_lines else app_doc.get("raw_text", "")

        system_prompt = f"""
You are the Dedicated Credit Risk AI Assistant for Application ID: {app_doc.get('application_id') or app_doc.get('applicant_id')}.

Answer using only the retrieved evidence and metadata below.

Application Metadata:
- Applicant ID: {app_doc.get('application_id') or app_doc.get('applicant_id')}
- Applicant Name: {app_doc.get('applicant_name')}
- Risk Assessment: {app_doc.get('risk_level')}
- Recommendation: {app_doc.get('recommendation')}

Retrieved Evidence:
{evidence}

Conversation History:
{history_str}

Strict output rules:
1. For direct factual questions like credit score, risk level, salary, loan amount, applicant name, company name, or any single value, return only the exact answer value.
2. Do not start with phrases such as 'Based on the retrieved evidence', 'According to', 'From the retrieved data', 'I found', or 'The retrieved evidence shows'.
3. Do not include citations, explanations, or reasoning in direct-value questions.
4. If the value is missing from the evidence, return exactly: 'Not available in the document'.
5. For summary/compare questions, provide a concise answer without a retrieval preamble.
"""
        response = generate_content_with_retry(
            model=GENERATION_MODEL,
            contents=f"{system_prompt}\nUser Question: {question}\nAssistant Answer:",
            config=types.GenerateContentConfig(temperature=0.2)
        )
        answer = response.text.strip()
        await AIService.record_retrieval_metrics(
            app_doc.get("application_id") or app_doc.get("applicant_id"),
            question,
            relevant_chunks,
        )
        return answer


# --- 2. ReportLab PDF Generation Service ---
class PDFService:
    @staticmethod
    def generate_analysis_pdf(app_data: dict) -> BytesIO:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        risk_level = (app_data.get("risk_level") or "Unknown").upper()
        if "LOW" in risk_level:
            badge_bg = colors.HexColor("#e8f5e9")
            badge_border = colors.HexColor("#4caf50")
            badge_text = colors.HexColor("#2e7d32")
        elif "MEDIUM" in risk_level:
            badge_bg = colors.HexColor("#fff3e0")
            badge_border = colors.HexColor("#ff9800")
            badge_text = colors.HexColor("#e65100")
        else:
            badge_bg = colors.HexColor("#ffebee")
            badge_border = colors.HexColor("#f44336")
            badge_text = colors.HexColor("#c62828")

        title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#1b5e20"))
        story.append(Paragraph("GenAI Credit Risk Assessment Report", title_style))
        story.append(Paragraph(f"Application ID: <b>{app_data.get('application_id') or app_data.get('applicant_id', 'N/A')}</b>", styles['Normal']))
        story.append(Spacer(1, 14))

        applicant_info = [
            [Paragraph("<b>Applicant Name</b>", styles['Normal']), Paragraph(str(app_data.get("applicant_name", "N/A")), styles['Normal'])],
            [Paragraph("<b>Contact Number</b>", styles['Normal']), Paragraph(str(app_data.get("contact_number", "N/A")), styles['Normal'])],
            [Paragraph("<b>Company & Role</b>", styles['Normal']), Paragraph(f"{app_data.get('company_name', 'N/A')} ({app_data.get('job_role', 'N/A')})", styles['Normal'])],
            [Paragraph("<b>Monthly Salary</b>", styles['Normal']), Paragraph(f"Rs. {app_data.get('monthly_salary', 'N/A')}", styles['Normal'])],
            [Paragraph("<b>Requested Loan Amount</b>", styles['Normal']), Paragraph(f"Rs. {app_data.get('requested_loan_amount', 'N/A')}", styles['Normal'])],
            [Paragraph("<b>Loan Purpose</b>", styles['Normal']), Paragraph(str(app_data.get("loan_purpose", "N/A")), styles['Normal'])],
            [Paragraph("<b>Existing EMIs / Liabilities</b>", styles['Normal']), Paragraph(f"EMIs: Rs. {app_data.get('existing_emis', '0')} | Liabilities: Rs. {app_data.get('existing_liabilities', '0')}", styles['Normal'])],
            [Paragraph("<b>House Ownership / Vehicles</b>", styles['Normal']), Paragraph(f"House: {app_data.get('own_house', 'N/A')} | Vehicles: {app_data.get('vehicles', 'N/A')}", styles['Normal'])],
        ]
        t1 = Table(applicant_info, colWidths=[180, 360])
        t1.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f9f9f9")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e0e0e0")),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t1)
        story.append(Spacer(1, 18))

        story.append(Paragraph("<b>AI Risk Assessment Cards</b>", styles['Heading2']))
        story.append(Spacer(1, 8))

        key_factors = app_data.get("key_factors", [])
        factors_text = "<br/>• " + "<br/>• ".join(key_factors) if isinstance(key_factors, list) else str(key_factors)

        cards_data = [
            [
                Paragraph(f"<b>RISK LEVEL</b><br/><br/><font size=13 color='{badge_text.hexval()}'><b>{risk_level}</b></font>", styles['Normal']),
                Paragraph(f"<b>CREDIT SCORE</b><br/><br/><font size=13><b>{app_data.get('credit_score', 'N/A')}</b></font>", styles['Normal'])
            ],
            [
                Paragraph(f"<b>KEY FACTORS</b><br/>{factors_text}", styles['Normal']),
                Paragraph(f"<b>RECOMMENDATION</b><br/><br/><font size=11 color='{badge_text.hexval()}'><b>{app_data.get('recommendation', 'N/A')}</b></font>", styles['Normal'])
            ]
        ]

        cards_table = Table(cards_data, colWidths=[270, 270])
        cards_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), badge_bg),
            ('BOX', (0, 0), (0, 0), 1.5, badge_border),
            ('BACKGROUND', (1, 0), (1, 0), colors.white),
            ('BOX', (1, 0), (1, 0), 1, colors.HexColor("#dcdcdc")),
            ('BACKGROUND', (0, 1), (0, 1), colors.white),
            ('BOX', (0, 1), (0, 1), 1, colors.HexColor("#dcdcdc")),
            ('BACKGROUND', (1, 1), (1, 1), badge_bg),
            ('BOX', (1, 1), (1, 1), 1.5, badge_border),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(cards_table)

        doc.build(story)
        buffer.seek(0)
        return buffer