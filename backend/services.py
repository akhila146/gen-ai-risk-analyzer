import os
import json
from io import BytesIO
from google import genai
from google.genai import types
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

# Primary & Fallback models (traffic lekunda immediate ga execute avvadaniki)
MODELS_TO_TRY = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]

# --- 1. AI Analysis & RAG Service ---
class AIService:
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
        last_error = None
        for model_name in MODELS_TO_TRY:
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                return json.loads(response.text)
            except Exception as e:
                last_error = e
                continue
        raise last_error

    @staticmethod
    async def chat_rag_response(app_doc: dict, chat_history: list, question: str) -> str:
        history_str = "".join([f"User: {h.get('user_msg')}\nAssistant: {h.get('assistant_msg')}\n" for h in chat_history])

        system_prompt = f"""
You are the Dedicated Credit Risk AI Assistant for Application ID: {app_doc.get('application_id') or app_doc.get('applicant_id')}.
Extract directly from this verified data context:
- Applicant ID: {app_doc.get('application_id') or app_doc.get('applicant_id')}
- Applicant Name: {app_doc.get('applicant_name')}
- Contact: {app_doc.get('contact_number')}
- Company & Role: {app_doc.get('company_name')} ({app_doc.get('job_role')})
- Monthly Income: {app_doc.get('monthly_salary')}
- Credit / CIBIL Score: {app_doc.get('credit_score')}
- Existing EMIs: {app_doc.get('existing_emis')}
- Liabilities: {app_doc.get('existing_liabilities')}
- Requested Loan: {app_doc.get('requested_loan_amount')}
- Loan Purpose: {app_doc.get('loan_purpose')}
- House Ownership: {app_doc.get('own_house')}
- Vehicles: {app_doc.get('vehicles')}
- Risk Assessment: {app_doc.get('risk_level')}
- Recommendation: {app_doc.get('recommendation')}
- Key Factors: {', '.join(app_doc.get('key_factors', []))}
- Overall Summary: {app_doc.get('summary')}

Raw Document:
\"\"\"{app_doc.get('raw_text', '')}\"\"\"

Conversation History:
{history_str}

Rules:
1. Only answer based on this context.
2. If asked specific values (e.g. 'cibil score', 'applicant name', 'salary'), state the exact value directly.
3. If asked for 'summary', give a concise executive summary covering the applicant's financials and final decision.
4. Do not speculate or invent unmentioned facts.
"""
        last_error = None
        for model_name in MODELS_TO_TRY:
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=f"{system_prompt}\nUser Question: {question}\nAssistant Answer:",
                    config=types.GenerateContentConfig(temperature=0.2)
                )
                return response.text.strip()
            except Exception as e:
                last_error = e
                continue
        raise last_error


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