# backend/ingestion/parquet_pipeline.py
"""
Unified Ingestion Pipeline for Causal Inference

Pipeline:
1. Upload -> 2. Load & Validate -> 3. Causal Prep & Quality Gates -> 4. Packetize
"""
import logging
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, Tuple, Any
import json
import magic
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# Use the newly centralized contract library
from backend.common.contracts import load_contract, validate_dataframe

logger = logging.getLogger(__name__)

# --- Causal Preparation Logic (from prepare_causal.py) ---

def _compute_smd(X_t, X_c):
    """Compute Standardized Mean Difference (SMD)."""
    mean_t = np.mean(X_t, axis=0)
    mean_c = np.mean(X_c, axis=0)
    var_t = np.var(X_t, axis=0, ddof=1)
    var_c = np.var(X_c, axis=0, ddof=1)
    pooled_std = np.sqrt((var_t + var_c) / 2)
    pooled_std = np.where(pooled_std < 1e-8, 1.0, pooled_std)
    smd = (mean_t - mean_c) / pooled_std
    return smd

# --- Main Pipeline Class ---

class ParquetPipeline:
    """Unified ingestion and causal preparation pipeline."""

    def __init__(self, data_dir: Path, contract_path: str = None):
        self.data_dir = data_dir
        self.contract_path = contract_path
        self.uploads_dir = data_dir / "uploads"
        self.parquet_dir = data_dir / "parquet"
        self.packets_dir = data_dir / "packets"
        self.quarantine_dir = data_dir / "quarantine"

        for d in [self.uploads_dir, self.parquet_dir, self.packets_dir, self.quarantine_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Contract is optional - if not provided, skip validation (schema-free mode)
        self.contract = load_contract(self.contract_path) if self.contract_path else None

    def process_upload(self, file_path: Path, dataset_id: str, mapping: Dict[str, str] = None, skip_validation: bool = True) -> Dict[str, Any]:
        """
        Process an uploaded file through the full validation and causal prep pipeline.
        
        Args:
            file_path: Path to uploaded file
            dataset_id: Unique dataset identifier
            mapping: Optional column mapping (e.g., {"y": "sales", "treatment": "treatment", "unit_id": "user_id"})
            skip_validation: If True, skip contract validation (schema-free mode for flexible uploads)
        """
        logger.info(f"[Ingestion] Processing {file_path.name} for dataset {dataset_id} (skip_validation={skip_validation})")

        try:
            # 1. Load file from various formats
            df = self._load_file(file_path)
            original_shape = df.shape
            logger.info(f"[Ingestion] Loaded {original_shape[0]} rows, {original_shape[1]} columns")

            # 2. Validate against contract (optional - skip for flexible uploads)
            prep_metrics = {}
            if not skip_validation and self.contract_path:
                df = validate_dataframe(df, self.contract_path)
                logger.info(f"[Ingestion] Contract validation passed.")

                # 3. Causal Preparation & Quality Gates
                df_processed, prep_metrics = self._prepare_causal(df)
                logger.info(f"[Ingestion] Causal preparation finished. Max |SMD|: {prep_metrics['max_smd']:.3f}")

                # 4. Check Quality Gates
                self._check_quality_gates(prep_metrics)
                logger.info(f"[Ingestion] All quality gates passed.")
            else:
                # Schema-free mode: just save the data as-is
                df_processed = df
                logger.info(f"[Ingestion] Schema-free mode: skipping validation and causal prep")

            # 5. Packetize: Save data and metadata
            packet_info = self._create_packet(df_processed, dataset_id, file_path, original_shape, prep_metrics, mapping)
            logger.info(f"[Ingestion] Packet created successfully: {packet_info['packet_path']}")
            
            return packet_info

        except Exception as e:
            logger.error(f"[Ingestion] FAILED for {dataset_id}: {e}")
            self._quarantine_file(file_path, dataset_id, str(e))
            raise

    def _load_file(self, path: Path) -> pd.DataFrame:
        """Load a single file with magic number validation (from convert_any_to_parquet.py)."""
        mime = magic.from_file(str(path), mime=True)
        p_lower = str(path).lower()

        if "csv" in mime or p_lower.endswith((".csv", ".csv.gz", ".csv.bz2")):
            return pd.read_csv(path)
        if "tsv" in mime or p_lower.endswith((".tsv", ".tsv.gz", ".tsv.bz2")):
            return pd.read_csv(path, sep="\t")
        if "json" in mime or p_lower.endswith((".jsonl", ".jsonl.gz", ".ndjson")):
            return pd.read_json(path, lines=True)
        if "excel" in mime or "openxmlformats-officedocument" in mime or p_lower.endswith(".xlsx"):
            return pd.read_excel(path)
        if "parquet" in mime or p_lower.endswith(".parquet"):
            return pd.read_parquet(path)
        if "feather" in mime or p_lower.endswith(".feather"):
            return pd.read_feather(path)

        raise ValueError(f"Unsupported file type: {path} (mime={mime})")

    def _prepare_causal(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Run causal safety preparation (from prepare_causal.py)."""
        X_cols = self.contract["covariate_cols"]
        t_col = self.contract["treatment_col"]
        
        X_numeric = df[X_cols].select_dtypes(include=[np.number])
        if X_numeric.shape[1] == 0:
            raise ValueError("No numeric covariates found for propensity score estimation.")

        imputer = SimpleImputer(strategy="median")
        X_imputed = imputer.fit_transform(X_numeric)
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_imputed)

        lr = LogisticRegression(max_iter=1000, random_state=42)
        lr.fit(X_scaled, df[t_col].values)
        ps_hat = lr.predict_proba(X_scaled)[:, 1]
        df["propensity_score"] = ps_hat

        overlap_mask = (ps_hat > 0.05) & (ps_hat < 0.95)
        overlap_ratio = float(overlap_mask.mean())

        treated_mask = df[t_col] == 1
        control_mask = df[t_col] == 0
        smd = _compute_smd(X_scaled[treated_mask.to_numpy()], X_scaled[control_mask.to_numpy()])
        max_smd_value = float(np.max(np.abs(smd)))
        smd_dict = {col: float(val) for col, val in zip(X_numeric.columns, smd)}

        metrics = {
            "overlap_ratio": overlap_ratio,
            "smd_by_covariate": smd_dict,
            "max_smd": max_smd_value,
            "propensity_score_summary": {
                "mean": float(ps_hat.mean()),
                "std": float(ps_hat.std()),
                "min": float(ps_hat.min()),
                "max": float(ps_hat.max()),
            }
        }
        return df, metrics

    def _check_quality_gates(self, metrics: Dict):
        """Check metrics against quality gates from the contract."""
        gates = self.contract.get("quality_gates", {})
        overlap_threshold = gates.get("overlap_threshold", 0.1)
        max_smd = gates.get("max_smd", 0.1)
        
        violations = []
        if metrics["overlap_ratio"] < overlap_threshold:
            violations.append(f"Overlap ratio {metrics['overlap_ratio']:.3f} is below threshold {overlap_threshold}")
        if metrics["max_smd"] > max_smd:
            violations.append(f"Max |SMD| {metrics['max_smd']:.3f} is above threshold {max_smd}")

        if violations:
            raise ValueError(f"Quality gate(s) failed: {'; '.join(violations)}")

    def _create_packet(self, df: pd.DataFrame, dataset_id: str, original_path: Path, original_shape: tuple, prep_metrics: dict, mapping: Dict[str, str] = None) -> Dict:
        """Save the processed data and metadata into a packet."""
        packet_path = self.packets_dir / dataset_id
        packet_path.mkdir(parents=True, exist_ok=True)
        packet_data_path = packet_path / "data.parquet"
        packet_meta_path = packet_path / "metadata.json"

        self._save_parquet(df, packet_data_path)

        metadata = {
            "dataset_id": dataset_id,
            "original_file": str(original_path.name),
            "original_shape": {"rows": original_shape[0], "cols": original_shape[1]},
            "processed_shape": {"rows": df.shape[0], "cols": df.shape[1]},
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "causal_prep_metrics": prep_metrics if prep_metrics else {},
            "mapping": mapping if mapping else {},
            "packet_format": "parquet+json",
            "size_bytes": packet_data_path.stat().st_size,
            "contract_path": self.contract_path if self.contract_path else None
        }

        with open(packet_meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "dataset_id": dataset_id,
            "packet_path": str(packet_path),
            "rows": df.shape[0],
            "cols": df.shape[1],
            "columns": list(df.columns),
            "quality_gates_status": "PASSED" if prep_metrics else "SKIPPED",
            "preprocessing": {
                "validation_performed": bool(prep_metrics),
                "missing_filled": 0,  # TODO: track this properly
            },
            **prep_metrics
        }

    def _quarantine_file(self, file_path: Path, dataset_id: str, reason: str):
        """Move a failed file to quarantine with a reason."""
        quarantine_path = self.quarantine_dir / dataset_id
        quarantine_path.mkdir(parents=True, exist_ok=True)
        
        # Move the original file
        file_path.rename(quarantine_path / file_path.name)

        # Write reason to a metadata file
        meta = {
            "dataset_id": dataset_id,
            "failed_at": pd.Timestamp.utcnow().isoformat(),
            "reason": reason,
            "original_file": file_path.name
        }
        with open(quarantine_path / "failure_metadata.json", "w") as f:
            json.dump(meta, f, indent=2)
        logger.warning(f"[Ingestion] File {file_path.name} moved to quarantine: {quarantine_path}")

    def _save_parquet(self, df: pd.DataFrame, path: Path):
        """Save DataFrame to Parquet with efficient settings (UTF-8 compatible for Japanese)."""
        # Ensure all string columns are properly encoded
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str)
        
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(
            table, 
            path, 
            compression='snappy', 
            use_dictionary=True,
            # Explicitly use default UTF-8 encoding
            coerce_timestamps='ms',
            allow_truncated_timestamps=False
        )

    def load_packet(self, dataset_id: str) -> Tuple[pd.DataFrame, Dict]:
        """Load data and metadata from a packet."""
        packet_path = self.packets_dir / dataset_id
        packet_data_path = packet_path / "data.parquet"
        packet_meta_path = packet_path / "metadata.json"

        if not packet_data_path.exists():
            raise FileNotFoundError(f"Packet not found: {dataset_id}")

        df = pd.read_parquet(packet_data_path)
        with open(packet_meta_path, "r") as f:
            metadata = json.load(f)
        return df, metadata
