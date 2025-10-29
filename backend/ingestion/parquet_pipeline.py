# backend/ingestion/parquet_pipeline.py
"""
Parquet Auto-Preprocessing Pipeline
アップロードファイルを自動的にParquet化し、前処理してパケット化

Pipeline:
1. Upload → 2. Parquet変換 → 3. 前処理（欠損値、型変換） → 4. パケット保存
"""
import logging
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, Tuple, Any
import json

logger = logging.getLogger(__name__)

class ParquetPipeline:
    """Parquet自動前処理パイプライン"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.uploads_dir = data_dir / "uploads"
        self.parquet_dir = data_dir / "parquet"
        self.packets_dir = data_dir / "packets"

        # Create directories
        for d in [self.uploads_dir, self.parquet_dir, self.packets_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def process_upload(self, file_path: Path, dataset_id: str) -> Dict[str, Any]:
        """
        アップロードファイルを処理してパケット化

        Steps:
        1. Load file (using convert_any_to_parquet.load_one)
        2. Preprocess (handle missing, convert types)
        3. Convert to Parquet
        4. Save as packet with metadata
        5. Return packet info

        Args:
            file_path: アップロードされたファイルパス
            dataset_id: データセットID

        Returns:
            {
                "dataset_id": str,
                "original_path": str,
                "parquet_path": str,
                "packet_path": str,
                "rows": int,
                "cols": int,
                "size_bytes": int,
                "preprocessing": {
                    "missing_filled": int,
                    "types_converted": dict,
                    "outliers_handled": int
                }
            }
        """
        logger.info(f"[ParquetPipeline] Processing {file_path.name} → {dataset_id}")

        # Step 1: Load file
        df = self._load_file(file_path)
        original_shape = df.shape

        # Step 2: Preprocess
        df_processed, preproc_stats = self._preprocess(df)

        # Step 3: Convert to Parquet
        parquet_path = self.parquet_dir / f"{dataset_id}.parquet"
        self._save_parquet(df_processed, parquet_path)

        # Step 4: Create packet (Parquet + metadata JSON)
        packet_path = self.packets_dir / dataset_id
        packet_path.mkdir(parents=True, exist_ok=True)

        packet_data_path = packet_path / "data.parquet"
        packet_meta_path = packet_path / "metadata.json"

        self._save_parquet(df_processed, packet_data_path)

        metadata = {
            "dataset_id": dataset_id,
            "original_file": str(file_path.name),
            "original_shape": {"rows": original_shape[0], "cols": original_shape[1]},
            "processed_shape": {"rows": df_processed.shape[0], "cols": df_processed.shape[1]},
            "columns": list(df_processed.columns),
            "dtypes": {col: str(dtype) for col, dtype in df_processed.dtypes.items()},
            "preprocessing": preproc_stats,
            "packet_format": "parquet+json",
            "size_bytes": packet_data_path.stat().st_size
        }

        with open(packet_meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"[ParquetPipeline] Packet created: {packet_path}")
        logger.info(f"[ParquetPipeline] {original_shape[0]} rows → {df_processed.shape[0]} rows ({preproc_stats['missing_filled']} missing filled)")

        return {
            "dataset_id": dataset_id,
            "original_path": str(file_path),
            "parquet_path": str(parquet_path),
            "packet_path": str(packet_path),
            "rows": df_processed.shape[0],
            "cols": df_processed.shape[1],
            "size_bytes": metadata["size_bytes"],
            "preprocessing": preproc_stats
        }

    def load_packet(self, dataset_id: str) -> Tuple[pd.DataFrame, Dict]:
        """
        パケットからデータとメタデータを読み込み

        Args:
            dataset_id: データセットID

        Returns:
            (DataFrame, metadata_dict)
        """
        packet_path = self.packets_dir / dataset_id
        packet_data_path = packet_path / "data.parquet"
        packet_meta_path = packet_path / "metadata.json"

        if not packet_data_path.exists():
            raise FileNotFoundError(f"Packet not found: {dataset_id}")

        df = pd.read_parquet(packet_data_path)

        with open(packet_meta_path, "r") as f:
            metadata = json.load(f)

        return df, metadata

    def _load_file(self, file_path: Path) -> pd.DataFrame:
        """ファイルをロード（convert_any_to_parquet.load_oneを使用）"""
        from ciq.scripts.convert_any_to_parquet import load_one
        return load_one(file_path)

    def _preprocess(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        前処理パイプライン

        1. 欠損値処理
        2. 型変換
        3. 外れ値処理（将来実装）

        Returns:
            (processed_df, stats)
        """
        stats = {
            "missing_filled": 0,
            "types_converted": {},
            "outliers_handled": 0
        }

        df_processed = df.copy()

        # 1. 欠損値処理
        missing_counts = df_processed.isnull().sum()
        for col in df_processed.columns:
            if missing_counts[col] > 0:
                if df_processed[col].dtype in ['int64', 'float64']:
                    # 数値: 中央値で埋める
                    df_processed[col].fillna(df_processed[col].median(), inplace=True)
                    stats["missing_filled"] += missing_counts[col]
                elif df_processed[col].dtype == 'object':
                    # 文字列: "MISSING"で埋める
                    df_processed[col].fillna("MISSING", inplace=True)
                    stats["missing_filled"] += missing_counts[col]

        # 2. 型変換（stringをcategoryに変換してメモリ削減）
        for col in df_processed.select_dtypes(include=['object']).columns:
            unique_ratio = df_processed[col].nunique() / len(df_processed)
            if unique_ratio < 0.5:  # 50%以下のユニーク値ならcategoryに
                df_processed[col] = df_processed[col].astype('category')
                stats["types_converted"][col] = "object→category"

        # 3. 外れ値処理（将来実装: IQR method等）
        # stats["outliers_handled"] = 0

        return df_processed, stats

    def _save_parquet(self, df: pd.DataFrame, path: Path):
        """DataFrameをParquetに保存"""
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(
            table,
            path,
            compression='snappy',  # 高速圧縮
            use_dictionary=True     # Dictionary encoding for strings
        )


# Convenience function
def process_and_save(file_path: Path, dataset_id: str, data_dir: Path) -> Dict:
    """
    ファイルを処理してパケット化（便利関数）

    Usage:
        from backend.ingestion.parquet_pipeline import process_and_save

        result = process_and_save(
            file_path=Path("uploads/data.csv"),
            dataset_id="abc123",
            data_dir=Path("data")
        )

        print(f"Processed {result['rows']} rows")
        print(f"Packet: {result['packet_path']}")
    """
    pipeline = ParquetPipeline(data_dir)
    return pipeline.process_upload(file_path, dataset_id)
