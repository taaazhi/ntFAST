from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Float, Numeric, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


# Allowed status values for Analysis.status — kept in sync with frontend types and Celery state transitions.
ANALYSIS_STATUS_VALUES = ("pending", "parsing", "analyzing", "completed", "failed", "cancelled")


class Analysis(Base):
    """
    Analysis model for financial transaction analysis
    Расширенная модель: парсинг, антифрод, AI, ML
    """

    __tablename__ = "analyses"
    __table_args__ = (
        # SECURITY/CORRECTNESS: enforce status values at the DB layer so a bug
        # in services can't write garbage like "processing" or "in_progress"
        # that the frontend doesn't know how to render.
        CheckConstraint(
            "status IN ('pending','parsing','analyzing','completed','failed','cancelled')",
            name="ck_analyses_status_valid",
        ),
    )

    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True, index=True)
    analyst_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Cascade delete: when Analysis is deleted, all its Transactions are deleted too
    transactions = relationship("Transaction", backref="analysis", cascade="all, delete-orphan")

    # Статус и результаты
    status = Column(String(20), default="pending", index=True)  # pending, parsing, analyzing, completed, failed, cancelled
    risk_score = Column(Integer, default=0)  # 0-100
    analyst_notes = Column(Text, nullable=True)
    conclusion = Column(Text, nullable=True)

    # Информация о загруженном файле
    file_name = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(10), nullable=True)
    file_size = Column(Integer, nullable=True)

    # Определённый банк
    bank_type = Column(String(20), nullable=True)  # kaspi, halyk, sberbank, etc.
    bank_name = Column(String(100), nullable=True)
    bank_confidence = Column(Float, nullable=True)

    # Информация о счёте (парсинг)
    account_owner = Column(String(300), nullable=True)
    account_number = Column(String(50), nullable=True)
    account_currency = Column(String(3), default="KZT")
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    balance_start = Column(Numeric(15, 2), nullable=True)
    balance_end = Column(Numeric(15, 2), nullable=True)
    parsed_account_info = Column(JSON, nullable=True)  # Полная информация о счёте

    # Статистика транзакций
    total_transactions = Column(Integer, default=0)
    total_income = Column(Numeric(15, 2), default=0)
    total_expense = Column(Numeric(15, 2), default=0)
    net_flow = Column(Numeric(15, 2), default=0)
    total_amount = Column(Integer, default=0)
    suspicious_count = Column(Integer, default=0)
    anomaly_count = Column(Integer, default=0)
    high_risk_count = Column(Integer, default=0)

    # Антифрод результаты
    fraud_composite_score = Column(Float, nullable=True)
    fraud_risk_level = Column(String(10), nullable=True)  # low, medium, high, critical
    fraud_report = Column(JSON, nullable=True)  # Полный отчёт FraudEngine
    fraud_red_flags = Column(JSON, nullable=True)  # Список красных флагов
    fraud_recommendations = Column(JSON, nullable=True)  # Рекомендации

    # Отдельные модули антифрода (для быстрого доступа)
    velocity_result = Column(JSON, nullable=True)
    graph_result = Column(JSON, nullable=True)
    behavioral_result = Column(JSON, nullable=True)
    structuring_result = Column(JSON, nullable=True)
    cross_reference_result = Column(JSON, nullable=True)
    merchant_risk_result = Column(JSON, nullable=True)

    # Новые модули антифрода v4
    night_transactions_result = Column(JSON, nullable=True)
    duplicate_payments_result = Column(JSON, nullable=True)
    round_amounts_result = Column(JSON, nullable=True)
    profile_mismatch_result = Column(JSON, nullable=True)

    # AI анализ
    ai_provider = Column(String(20), nullable=True)  # claude, ollama
    ai_narrative = Column(Text, nullable=True)  # AI-сгенерированный текст
    ai_risk_assessment = Column(JSON, nullable=True)  # Structured AI output

    # ML обработка
    ml_processed = Column(Boolean, default=False)
    ml_results = Column(JSON, nullable=True)

    # Полные результаты аналитики
    analytics_result = Column(JSON, nullable=True)  # category_breakdown, monthly, contacts, etc.

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Analysis(id={self.id}, file='{self.file_name}', status='{self.status}', risk_score={self.risk_score})>"
