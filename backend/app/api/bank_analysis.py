"""Вспомогательные эндпоинты вокруг анализа выписок.

Форматы: PDF (Kaspi, Halyk и др.), XLSX (Binance), CSV.

Здесь НЕТ обработчика анализа. Загрузка файла живёт по одному адресу —
`POST /api/analyses/upload`, откуда работа уходит в Celery. Раньше рядом
существовал синхронный `POST /api/bank/analyze`, который делал ту же работу
собственным кодом: один и тот же файл давал разный результат в зависимости
от того, каким из двух путей его загрузили.
"""
import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse

from app.services.analysis_persistence import (
    UnsupportedFileType, sanitize_filename, validate_file_extension,
)
from app.services.bank_analyzer import BankDetector
from app.services.pdf_export import NtFastPDFReport
from app.services.auth_service import get_current_user
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)



@router.post("/detect")
async def detect_bank_type(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Определить тип банка без полного анализа

    Быстрая проверка какой банк выпустил выписку.
    Поддерживает PDF и XLSX файлы.

    SECURITY: требует аутентификации. Эндпоинт принимает загруженный файл
    и разбирает его pdfplumber/openpyxl — без авторизации это открытый приём
    произвольных файлов и бесплатный расход CPU для любого желающего.
    """
    try:
        ext = validate_file_extension(sanitize_filename(file.filename or ""))
    except UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Для XLSX — автоматически Binance (без детектора)
        if ext in (".xlsx", ".xls"):
            return {
                "bank_type": "binance",
                "bank_name": "Binance",
                "confidence": 0.95,
                "detected_keywords": ["xlsx", "binance"],
                "all_scores": {"binance": 0.95}
            }

        detector = BankDetector(tmp_path)
        result = detector.detect()

        return {
            "bank_type": result.bank_type.value,
            "bank_name": result.bank_name,
            "confidence": result.confidence,
            "detected_keywords": result.detected_keywords,
            "all_scores": result.metadata.get("all_scores", {})
        }

    except Exception as e:
        logger.error(f"Ошибка определения банка: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка: {str(e)}"
        )

    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/supported-banks")
async def get_supported_banks(current_user: User = Depends(get_current_user)):
    """Получить список поддерживаемых банков"""
    return {
        "banks": [
            {
                "type": "kaspi",
                "name": "Kaspi Bank",
                "country": "Казахстан",
                "status": "полная поддержка",
                "formats": ["PDF выписка Gold карты"]
            },
            {
                "type": "binance",
                "name": "Binance",
                "country": "Международный",
                "status": "полная поддержка",
                "formats": ["XLSX история транзакций"]
            },
            {
                "type": "halyk",
                "name": "Halyk Bank",
                "country": "Казахстан",
                "status": "в разработке",
                "formats": ["PDF справка о наличии счёта"]
            },
            {
                "type": "sberbank",
                "name": "Сбербанк",
                "country": "Казахстан/Россия",
                "status": "в разработке",
                "formats": []
            },
            {
                "type": "jusan",
                "name": "Jusan Bank",
                "country": "Казахстан",
                "status": "в разработке",
                "formats": []
            },
            {
                "type": "forte",
                "name": "ForteBank",
                "country": "Казахстан",
                "status": "в разработке",
                "formats": []
            },
            {
                "type": "freedom",
                "name": "Freedom Finance",
                "country": "Казахстан",
                "status": "в разработке",
                "formats": []
            },
            {
                "type": "unknown",
                "name": "Другие банки",
                "country": "Любой",
                "status": "универсальный парсер",
                "formats": ["PDF с таблицами транзакций"]
            }
        ]
    }


@router.post("/export-pdf")
async def export_analysis_pdf(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a PDF report from analysis results.

    Accepts the full analysis JSON (same structure as /analyze response)
    and returns a branded ntFAST PDF report.

    SECURITY: требует аутентификации. Приём произвольного JSON с последующей
    генерацией многостраничного PDF через reportlab — дорогая операция;
    открытый доступ к ней это готовый вектор отказа в обслуживании.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not data or not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Empty or invalid analysis data")

    try:
        report = NtFastPDFReport(data)
        pdf_bytes = report.generate()

        # Build filename — must be pure ASCII for HTTP headers
        import io
        from datetime import datetime as _dt
        ts = _dt.now().strftime('%Y%m%d_%H%M')
        filename = f"ntFAST_report_{ts}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_bytes)),
            }
        )

    except Exception as e:
        logger.error(f"PDF generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(e)}"
        )


@router.get("/categories")
async def get_categories(current_user: User = Depends(get_current_user)):
    """Получить все доступные категории транзакций"""
    from app.services.kaspi_analyzer import TransactionCategorizer

    categorizer = TransactionCategorizer()

    return {
        "expense_categories": [
            {
                "id": cat_id,
                "name": cat_info["name"],
                "keywords_count": len(cat_info["keywords"])
            }
            for cat_id, cat_info in categorizer.EXPENSE_CATEGORIES.items()
        ],
        "transfer_categories": [
            {"id": cat_id, "name": cat_info["name"]}
            for cat_id, cat_info in categorizer.TRANSFER_CATEGORIES.items()
        ],
        "income_categories": [
            {"id": cat_id, "name": cat_info["name"]}
            for cat_id, cat_info in categorizer.INCOME_CATEGORIES.items()
        ]
    }
