"""
API endpoints for PDF Financial Analysis
"""
import os
import re
import tempfile
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.pdf_analyzer import FinancialAnalyzer, analyze_pdf_file

router = APIRouter()
logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Strip path separators and limit filename to safe characters."""
    if not name:
        return "unnamed"
    # Strip directory components
    safe = Path(name).name
    # Whitelist a..z A..Z 0..9 . _ - and replace the rest
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", safe)
    # Limit length
    return safe[:200] or "unnamed"


def _validate_path_inside(path: str, base_dir: str) -> Path:
    """
    Resolve a path and ensure it stays inside base_dir.
    Raises HTTPException(400) on traversal attempts.
    """
    try:
        base = Path(base_dir).resolve()
        target = (base / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Python 3.9+ supports is_relative_to; fallback via str check for safety
    try:
        if not target.is_relative_to(base):
            raise HTTPException(status_code=400, detail="Path traversal denied")
    except AttributeError:
        if not str(target).startswith(str(base) + os.sep) and str(target) != str(base):
            raise HTTPException(status_code=400, detail="Path traversal denied")
    return target


@router.post("/analyze")
async def analyze_pdf(
    file: UploadFile = File(...),
    use_ai: bool = Query(True, description="Use Ollama AI for analysis summary"),
    anonymize: bool = Query(True, description="Anonymize personal data")
):
    """
    Analyze uploaded PDF bank statement

    - Extracts transactions from Kaspi Bank PDF
    - Anonymizes personal data (names, IINs, phone numbers)
    - Detects fraud patterns (gaming/gambling, money laundering, P2P anomalies)
    - Builds social profile
    - Generates AI summary (if Ollama is available)
    """
    # Validate file type — sanitize filename first
    safe_name = _sanitize_filename(file.filename or "")
    if not safe_name.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        logger.info(f"Analyzing uploaded PDF: {safe_name}")

        # Run analysis
        analyzer = FinancialAnalyzer(use_ai=use_ai)
        result = analyzer.analyze_pdf(tmp_path, anonymize=anonymize)

        # Add original (sanitized) filename
        result["original_filename"] = safe_name

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed")

    finally:
        # Cleanup temp file
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/analyze-path")
async def analyze_pdf_by_path(
    pdf_path: str,
    use_ai: bool = Query(True),
    anonymize: bool = Query(True)
):
    """
    Analyze PDF by file path inside the configured UPLOAD_DIR (for local testing).

    SECURITY: `pdf_path` is resolved against `settings.UPLOAD_DIR` and rejected
    if it escapes that directory. Absolute paths outside UPLOAD_DIR are also
    rejected to prevent reading arbitrary files like .env or /etc/passwd.
    """
    # Reject early on extension mismatch
    if not pdf_path.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # SECURITY: resolve and validate path lives inside UPLOAD_DIR
    safe_path = _validate_path_inside(pdf_path, settings.UPLOAD_DIR)

    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="PDF file not found")

    try:
        analyzer = FinancialAnalyzer(use_ai=use_ai)
        result = analyzer.analyze_pdf(str(safe_path), anonymize=anonymize)
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed")


@router.get("/ollama-status")
async def check_ollama_status():
    """Check if Ollama is available for AI analysis"""
    from app.services.pdf_analyzer import OllamaAnalyzerSync

    ollama = OllamaAnalyzerSync()
    is_available = ollama.check_connection()

    return {
        "available": is_available,
        "host": ollama.host,
        "model": ollama.model
    }


@router.get("/supported-formats")
async def get_supported_formats():
    """Get information about supported PDF formats"""
    return {
        "supported_banks": [
            {
                "name": "Kaspi Bank",
                "country": "Kazakhstan",
                "format": "PDF statement export"
            }
        ],
        "detection_capabilities": [
            "Gaming/Gambling transactions",
            "Money laundering patterns",
            "P2P transfer analysis",
            "Social profiling"
        ],
        "anonymization": [
            "Customer names",
            "IIN (Individual Identification Number)",
            "Phone numbers",
            "Card numbers",
            "Account numbers"
        ]
    }
