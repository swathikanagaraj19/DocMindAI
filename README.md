# DocuMind AI — AI-Powered Document Intelligence

A responsive resume/document analysis demo built with Flask, PDF text extraction, optional Gemini API integration, structured JSON validation, and a skills chart.

## Features

- Upload PDF or TXT files (10 MB maximum).
- Extract readable text from PDFs and text documents.
- Generate brief, detailed, or bullet-style summaries.
- Select Basic, Standard, or Detailed analysis.
- Choose specific extraction fields: name, email, skills, education, work experience.
- Extract structured information and validate the expected fields.
- Use `null` / empty lists for missing information rather than intentionally inventing values.
- Show an information-completeness indicator.
- Visualize extracted skills and download extracted JSON.
- Graceful errors for empty, unsupported, unreadable, or textless documents.
- Local fallback mode keeps the demo testable without a Gemini API key.

## Technology

- Python 3.10+
- Flask
- pypdf
- Google Gemini API (`google-generativeai`)
- jsonschema
- Chart.js
- HTML / CSS / JavaScript

## Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`.
5. Optional: add a Gemini API key to `.env`:

   ```env
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-2.5-flash
   ```

   If no API key is configured, the app uses a basic local fallback. The fallback is only a demo convenience and is less capable than an LLM.

6. Start the application:

   ```bash
   python app.py
   ```

7. Open `http://127.0.0.1:5000`.

## Deploy to Render

1. Push this folder to a GitHub repository.
2. Create a new Web Service in Render and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. In Render's Environment settings, add `GEMINI_API_KEY` and optionally `GEMINI_MODEL`.
6. Deploy and test the public URL.

Do not commit `.env`, API keys, passwords, or other secrets.

## Sample document

A fictional sample resume is included in `sample_documents/sample_resume.txt`. It contains illustrative, made-up candidate details for testing only.

## API behaviour

`POST /api/analyze` accepts multipart form fields:

- `document`: PDF or TXT file
- `summary_style`: `brief`, `detailed`, or `bullets`
- `analysis_level`: `basic`, `standard`, or `detailed`
- `focus_fields`: optional repeated fields from `name`, `email`, `skills`, `education`, `work_experience`

The response contains `summary`, `extracted`, `completeness`, `source_characters`, `model_used`, and a review notice.

## Limitations and responsible use

- This prototype is designed primarily for resume-style documents.
- Scanned PDFs need OCR; OCR is not included.
- The local fallback uses simple heuristics and should not be treated as reliable semantic extraction.
- AI output can be wrong or incomplete. Always compare it with the source document.
- The completeness percentage measures whether the six output categories contain information; it is not a measure of resume quality.
- The app does not save uploaded files or create a user account.
- Before production use, add authentication if needed, stronger privacy controls, rate limiting, logging policies, and more automated tests.
- AI provider/model availability and free-tier quotas may change.
