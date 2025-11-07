# backend/provenance/audit_log.py
"""
Provenance and Audit Logging System (Col1 Specification)

Records:
- Mapping history (role inference decisions)
- Dictionary versions (ontology, units, validators)
- Transformation logs (encoding, scaling, imputation)
- Random seeds (for reproducibility)
- Validation results (leakage detection, VIF, missing data)
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field

BASE_DIR = Path(__file__).resolve().parents[2]
AUDIT_DIR = BASE_DIR / "data" / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MappingDecision:
    """Records a single role inference decision"""
    role: str
    column: str
    confidence: float
    reasons: List[str]
    alternatives: List[Dict[str, Any]]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TransformationLog:
    """Records a data transformation"""
    transform_type: str  # "encoding", "scaling", "imputation", "outlier_removal"
    column: str
    method: str
    parameters: Dict[str, Any]
    affected_rows: int
    mapping: Optional[Dict[str, Any]] = None  # for categorical encoding
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class DictionaryVersion:
    """Records ontology dictionary versions"""
    columns_version: str
    units_version: str
    validators_version: str
    columns_hash: str
    units_hash: str
    validators_hash: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RandomSeed:
    """Records random seed for reproducibility"""
    seed: int
    scope: str  # "inference", "validation", "estimation", "bootstrap"
    algorithm: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ValidationResult:
    """Records validation check results"""
    check_type: str  # "leakage", "vif", "missing", "balance", "overlap"
    passed: bool
    severity: str  # "error", "warning", "info"
    details: Dict[str, Any]
    recommendations: List[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ProvenanceLog:
    """
    Complete provenance record for a single analysis job

    Tracks all decisions, transformations, and validations
    to ensure reproducibility and auditability
    """

    def __init__(self, job_id: str, dataset_id: str):
        self.job_id = job_id
        self.dataset_id = dataset_id
        self.created_at = datetime.utcnow().isoformat()

        # Main log sections
        self.mapping_decisions: List[MappingDecision] = []
        self.transformations: List[TransformationLog] = []
        self.dictionary_version: Optional[DictionaryVersion] = None
        self.random_seeds: List[RandomSeed] = []
        self.validations: List[ValidationResult] = []

        # Metadata
        self.metadata: Dict[str, Any] = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "created_at": self.created_at,
            "cqox_version": "1.0.0",
            "python_version": "3.11",
        }

    def add_mapping_decision(self, decision: MappingDecision) -> None:
        """Record a role inference decision"""
        self.mapping_decisions.append(decision)

    def add_transformation(self, transform: TransformationLog) -> None:
        """Record a data transformation"""
        self.transformations.append(transform)

    def set_dictionary_version(self, version: DictionaryVersion) -> None:
        """Record ontology dictionary versions"""
        self.dictionary_version = version

    def add_random_seed(self, seed: RandomSeed) -> None:
        """Record random seed"""
        self.random_seeds.append(seed)

    def add_validation(self, validation: ValidationResult) -> None:
        """Record validation result"""
        self.validations.append(validation)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "metadata": self.metadata,
            "dictionary_version": asdict(self.dictionary_version) if self.dictionary_version else None,
            "mapping_decisions": [asdict(d) for d in self.mapping_decisions],
            "transformations": [asdict(t) for t in self.transformations],
            "random_seeds": [asdict(s) for s in self.random_seeds],
            "validations": [asdict(v) for v in self.validations],
        }

    def save(self) -> Path:
        """Save provenance log to disk"""
        log_path = AUDIT_DIR / f"{self.job_id}_provenance.json"
        log_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))
        return log_path

    @classmethod
    def load(cls, job_id: str) -> Optional['ProvenanceLog']:
        """Load provenance log from disk"""
        log_path = AUDIT_DIR / f"{job_id}_provenance.json"
        if not log_path.exists():
            return None

        data = json.loads(log_path.read_text())
        log = cls(
            job_id=data["metadata"]["job_id"],
            dataset_id=data["metadata"]["dataset_id"]
        )
        log.metadata = data["metadata"]

        # Reconstruct objects
        if data["dictionary_version"]:
            log.dictionary_version = DictionaryVersion(**data["dictionary_version"])

        log.mapping_decisions = [MappingDecision(**d) for d in data["mapping_decisions"]]
        log.transformations = [TransformationLog(**t) for t in data["transformations"]]
        log.random_seeds = [RandomSeed(**s) for s in data["random_seeds"]]
        log.validations = [ValidationResult(**v) for v in data["validations"]]

        return log

    def get_summary(self) -> Dict[str, Any]:
        """Get human-readable summary"""
        return {
            "job_id": self.job_id,
            "dataset_id": self.dataset_id,
            "created_at": self.created_at,
            "roles_mapped": len(self.mapping_decisions),
            "transformations_applied": len(self.transformations),
            "validations_run": len(self.validations),
            "validations_failed": sum(1 for v in self.validations if not v.passed),
            "dictionary_version": self.dictionary_version.columns_version if self.dictionary_version else "unknown",
        }


def create_provenance_log(dataset_id: str, job_id: Optional[str] = None) -> ProvenanceLog:
    """Create a new provenance log"""
    if job_id is None:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
    return ProvenanceLog(job_id, dataset_id)


def get_dictionary_version() -> DictionaryVersion:
    """Get current dictionary versions with hashes"""
    import hashlib

    def file_hash(path: Path) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()[:8] if path.exists() else "missing"

    config_dir = BASE_DIR / "config" / "ontology"
    columns_path = config_dir / "columns.json"
    units_path = config_dir / "units.json"
    validators_path = config_dir / "validators.json"

    return DictionaryVersion(
        columns_version="1.0.0",
        units_version="1.0.0",
        validators_version="1.0.0",
        columns_hash=file_hash(columns_path),
        units_hash=file_hash(units_path),
        validators_hash=file_hash(validators_path),
    )
