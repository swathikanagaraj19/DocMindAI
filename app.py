import os
import json
import re
from io import BytesIO

from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from jsonschema import validate, ValidationError
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": ["string", "null"]},
        "email": {"type": ["string", "null"]},
        "skills": {"type": "array", "items": {"type": "string"}},
        "education": {"type": "array", "items": {"type": "string"}},
        "work_experience": {"type": "array", "items": {"type": "string"}},
        "key_findings": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["name", "email", "skills", "education", "work_experience", "key_findings"],
    "additionalProperties": False
}

def extract_text(file_storage):
    filename = secure_filename(file_storage.filename or "")
    ext = os.path.splitext(filename)[1].lower()
    raw = file_storage.read()
    if not raw:
        raise ValueError("The uploaded file is empty.")
    if ext == ".txt":
        text = raw.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        try:
            reader = PdfReader(BytesIO(raw))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            raise ValueError("This PDF could not be read. Try another PDF or a text file.") from exc
    else:
        raise ValueError("Unsupported file type. Please upload a PDF or TXT file.")
    text = text.strip()
    if not text:
        raise ValueError("No readable text was found. If this is a scanned PDF, OCR is not included in this demo.")
    return text

def fallback_analysis(source_text, summary_style, analysis_level, focus_fields):
    # Deterministic local fallback so the demo remains testable without an API key.
    lines = [re.sub(r"\s+", " ", line).strip() for line in source_text.splitlines()]
    lines = [line for line in lines if line]
    summary_lines = lines[:3] if analysis_level == "basic" else lines[:6] if analysis_level == "standard" else lines[:10]
    summary = " ".join(summary_lines)
    if summary_style == "bullets":
        summary = "\n".join(f"• {line}" for line in summary_lines)
    elif summary_style == "brief":
        summary = " ".join(summary_lines[:2])
    # Simple conservative extraction: only use patterns/text that appear in source.
    email_match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", source_text, re.I)
    first_line = lines[0] if lines else None
    name = first_line if first_line and len(first_line) < 70 and "@" not in first_line else None
    skill_terms = ["Python", "Java", "JavaScript", "SQL", "HTML", "CSS", "React", "Flask", "FastAPI", "C++", "Excel", "Machine Learning", "Data Analysis"]
    skills = [skill for skill in skill_terms if re.search(r"\b" + re.escape(skill) + r"\b", source_text, re.I)]
    education = [line for line in lines if re.search(r"\b(B\.?E\.?|B\.?Tech|BSc|B\.?Sc|M\.?E\.?|M\.?Tech|MBA|Bachelor|Master|Diploma|University|College|Education)\b", line, re.I)]
    experience = [line for line in lines if re.search(r"\b(Intern|Internship|Experience|Developer|Engineer|Manager|Worked|Employment)\b", line, re.I)]
    available = {
        "name": name,
        "email": email_match.group(0) if email_match else None,
        "skills": skills,
        "education": education,
        "work_experience": experience,
        "key_findings": lines[:min(5, len(lines))]
    }
    if focus_fields:
        allowed = set(focus_fields)
        for key in list(available):
            if key not in allowed and key not in ("key_findings",):
                available[key] = None if key in ("name", "email") else []
    return summary, available, "Local fallback (no AI API key configured)"

def ask_gemini(source_text, summary_style, analysis_level, focus_fields):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    model = genai.GenerativeModel(model_name)
    max_chars = 30000
    source = source_text[:max_chars]
    prompt = f"""
You are a careful resume-document analyst. Use ONLY information supported by the source text.
Never infer or invent missing details. Use null for missing name/email and [] for missing lists.
Return valid JSON only with this exact schema:
{{
 "summary": "string",
 "name": "string or null",
 "email": "string or null",
 "skills": ["string"],
 "education": ["string"],
 "work_experience": ["string"],
 "key_findings": ["string"]
}}
Summary style: {summary_style}. Analysis level: {analysis_level}.
Focus fields selected by the user: {focus_fields or "all fields"}.
If fields are not selected, return all fields. Keep any extracted values grounded in the document.
SOURCE DOCUMENT:
{source}
"""
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json", "temperature": 0.1}
    )
    data = json.loads(response.text)
    validate(instance={k: data.get(k) for k in RESUME_SCHEMA["required"]}, schema=RESUME_SCHEMA)
    summary = data.get("summary", "")
    extracted = {k: data[k] for k in RESUME_SCHEMA["required"]}
    # Respect requested focus by clearing non-selected extraction fields.
    if focus_fields:
        for key in ["name", "email", "skills", "education", "work_experience"]:
            if key not in focus_fields:
                extracted[key] = None if key in ["name", "email"] else []
    return summary, extracted, f"Gemini ({model_name})"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/analyze", methods=["POST"])
def analyze():
    if "document" not in request.files:
        return jsonify({"error": "Please choose a PDF or TXT file."}), 400
    file = request.files["document"]
    try:
        source_text = extract_text(file)
        summary_style = request.form.get("summary_style", "detailed")
        analysis_level = request.form.get("analysis_level", "standard")
        focus_fields = request.form.getlist("focus_fields")
        try:
            summary, extracted, model_used = ask_gemini(source_text, summary_style, analysis_level, focus_fields)
        except Exception as ai_error:
            # The local fallback keeps the demo functional without a configured AI key.
            summary, extracted, model_used = fallback_analysis(source_text, summary_style, analysis_level, focus_fields)
            if os.getenv("GEMINI_API_KEY"):
                model_used += f" (AI unavailable: {str(ai_error)[:120]})"
        total_fields = 6
        filled = sum(1 for key in ["name", "email"] if extracted.get(key)) + sum(
            1 for key in ["skills", "education", "work_experience", "key_findings"] if extracted.get(key)
        )
        completeness = round(filled / total_fields * 100)
        return jsonify({
            "summary": summary,
            "extracted": extracted,
            "completeness": completeness,
            "source_characters": len(source_text),
            "model_used": model_used,
            "notice": "AI-generated results may need human review. Verify all extracted details against the source document."
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Document analysis failed")
        return jsonify({"error": "Something went wrong while processing this file. Please try another document."}), 500

@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "File is too large. Maximum upload size is 10 MB."}), 413

if __name__ == "__main__":
    app.run(debug=True)
