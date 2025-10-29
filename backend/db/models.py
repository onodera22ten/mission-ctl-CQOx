# backend/db/models.py
"""
SQLAlchemy ORM models for CQOx database schema.
Supports both sync and async SQLAlchemy engines.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, Boolean, Text,
    DateTime, ForeignKey, Index, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


# ========================================
# Core Tables
# ========================================

class Dataset(Base):
    """Uploaded CSV datasets metadata"""
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(String(255), unique=True, nullable=False, index=True)
    filename = Column(String(500))
    uploaded_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    rows_count = Column(Integer)
    columns_count = Column(Integer)
    file_size_bytes = Column(BigInteger)
    metadata = Column(JSONB)

    # Relationships
    jobs = relationship("AnalysisJob", back_populates="dataset", cascade="all, delete-orphan")


class AnalysisJob(Base):
    """Causal analysis job tracking"""
    __tablename__ = "analysis_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(255), unique=True, nullable=False, index=True)
    dataset_id = Column(String(255), ForeignKey("datasets.dataset_id"), index=True)
    status = Column(String(50), default="pending", index=True)
    started_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    completed_at = Column(TIMESTAMP)
    duration_seconds = Column(Float)
    mapping = Column(JSONB)
    config = Column(JSONB)
    results = Column(JSONB)
    error_message = Column(Text)

    # Relationships
    dataset = relationship("Dataset", back_populates="jobs")
    estimator_results = relationship("EstimatorResult", back_populates="job", cascade="all, delete-orphan")
    quality_gates = relationship("QualityGate", back_populates="job", cascade="all, delete-orphan")
    cas_scores = relationship("CASScore", back_populates="job", cascade="all, delete-orphan")


class EstimatorResult(Base):
    """Individual estimator execution results"""
    __tablename__ = "estimator_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(255), ForeignKey("analysis_jobs.job_id"), index=True)
    estimator_name = Column(String(100), nullable=False, index=True)
    tau_hat = Column(Float)
    se = Column(Float)
    ci_lower = Column(Float)
    ci_upper = Column(Float)
    p_value = Column(Float)
    execution_time_seconds = Column(Float)
    status = Column(String(50))
    metadata = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    job = relationship("AnalysisJob", back_populates="estimator_results")


class QualityGate(Base):
    """Quality gate evaluation results"""
    __tablename__ = "quality_gates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(255), ForeignKey("analysis_jobs.job_id"), index=True)
    gate_name = Column(String(100), nullable=False, index=True)
    pass_ = Column("pass", Boolean, index=True)
    value = Column(Float)
    threshold = Column(Float)
    message = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    job = relationship("AnalysisJob", back_populates="quality_gates")


class CASScore(Base):
    """Causal Assurance Score (CAS) tracking"""
    __tablename__ = "cas_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(255), ForeignKey("analysis_jobs.job_id"), index=True)
    overall_score = Column(Float, nullable=False, index=True)
    gate_pass_score = Column(Float)
    sign_consensus_score = Column(Float)
    ci_overlap_score = Column(Float)
    data_health_score = Column(Float)
    sensitivity_score = Column(Float)
    grade = Column(String(20))
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    job = relationship("AnalysisJob", back_populates="cas_scores")


# ========================================
# Observability & Monitoring
# ========================================

class ObservabilityMetric(Base):
    """System metrics for 37-panel dashboard"""
    __tablename__ = "observability_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(255), nullable=False, index=True)
    metric_value = Column(Float)
    labels = Column(JSONB)  # GIN index for fast JSONB queries
    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    __table_args__ = (
        Index('idx_metrics_labels', 'labels', postgresql_using='gin'),
    )


class AuditLog(Base):
    """User action audit trail"""
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False, index=True)
    user_id = Column(String(255), index=True)
    dataset_id = Column(String(255))
    job_id = Column(String(255))
    action = Column(String(255))
    details = Column(JSONB)
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)


# ========================================
# Domain Inference
# ========================================

class DomainInferenceCache(Base):
    """Cached domain auto-detection results"""
    __tablename__ = "domain_inference_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(String(255), unique=True, nullable=False, index=True)
    domain_hints = Column(JSONB, nullable=False)
    confidence_scores = Column(JSONB)
    column_patterns = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


# ========================================
# Helper Functions
# ========================================

def create_tables(engine):
    """Create all tables in database"""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """Drop all tables (use with caution!)"""
    Base.metadata.drop_all(engine)
