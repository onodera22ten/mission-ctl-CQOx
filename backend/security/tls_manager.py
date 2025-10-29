# backend/security/tls_manager.py
"""
TLS/mTLS Certificate Manager
証明書の自動生成・管理・更新

Features:
- Self-signed certificate generation (development)
- Let's Encrypt integration (production)
- mTLS mutual authentication
- Certificate rotation
"""
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple
import subprocess

logger = logging.getLogger(__name__)

class TLSManager:
    """TLS証明書マネージャー"""

    def __init__(self, certs_dir: Path):
        self.certs_dir = certs_dir
        self.certs_dir.mkdir(parents=True, exist_ok=True)

    def generate_self_signed_cert(
        self,
        domain: str = "localhost",
        validity_days: int = 365
    ) -> Tuple[Path, Path]:
        """
        自己署名証明書を生成（開発環境用）

        Args:
            domain: ドメイン名
            validity_days: 有効期限（日数）

        Returns:
            (cert_path, key_path)
        """
        cert_path = self.certs_dir / f"{domain}.crt"
        key_path = self.certs_dir / f"{domain}.key"

        if cert_path.exists() and key_path.exists():
            logger.info(f"[TLS] Certificate already exists: {cert_path}")
            return cert_path, key_path

        logger.info(f"[TLS] Generating self-signed certificate for {domain}")

        # OpenSSL command for self-signed certificate
        cmd = [
            "openssl", "req",
            "-x509",
            "-newkey", "rsa:4096",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", str(validity_days),
            "-nodes",  # No passphrase
            "-subj", f"/CN={domain}/O=CQOx/C=US"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"[TLS] Certificate generated: {cert_path}")
            logger.info(f"[TLS] Key generated: {key_path}")
            return cert_path, key_path
        except subprocess.CalledProcessError as e:
            logger.error(f"[TLS] Failed to generate certificate: {e.stderr}")
            raise RuntimeError(f"Failed to generate TLS certificate: {e.stderr}")

    def generate_ca_and_client_cert(self) -> Tuple[Path, Path, Path, Path]:
        """
        mTLS用のCA証明書とクライアント証明書を生成

        Returns:
            (ca_cert, ca_key, client_cert, client_key)
        """
        ca_cert = self.certs_dir / "ca.crt"
        ca_key = self.certs_dir / "ca.key"
        client_cert = self.certs_dir / "client.crt"
        client_key = self.certs_dir / "client.key"
        client_csr = self.certs_dir / "client.csr"

        # 1. Generate CA certificate
        if not (ca_cert.exists() and ca_key.exists()):
            logger.info("[TLS] Generating CA certificate")
            subprocess.run([
                "openssl", "req",
                "-x509",
                "-newkey", "rsa:4096",
                "-keyout", str(ca_key),
                "-out", str(ca_cert),
                "-days", "3650",  # 10 years
                "-nodes",
                "-subj", "/CN=CQOx CA/O=CQOx/C=US"
            ], check=True, capture_output=True)

        # 2. Generate client key
        if not client_key.exists():
            logger.info("[TLS] Generating client key")
            subprocess.run([
                "openssl", "genrsa",
                "-out", str(client_key),
                "4096"
            ], check=True, capture_output=True)

        # 3. Generate client CSR
        if not client_csr.exists():
            logger.info("[TLS] Generating client CSR")
            subprocess.run([
                "openssl", "req",
                "-new",
                "-key", str(client_key),
                "-out", str(client_csr),
                "-subj", "/CN=CQOx Client/O=CQOx/C=US"
            ], check=True, capture_output=True)

        # 4. Sign client certificate with CA
        if not client_cert.exists():
            logger.info("[TLS] Signing client certificate")
            subprocess.run([
                "openssl", "x509",
                "-req",
                "-in", str(client_csr),
                "-CA", str(ca_cert),
                "-CAkey", str(ca_key),
                "-CAcreateserial",
                "-out", str(client_cert),
                "-days", "365"
            ], check=True, capture_output=True)

        logger.info("[TLS] mTLS certificates generated")
        return ca_cert, ca_key, client_cert, client_key

    def check_cert_expiration(self, cert_path: Path) -> int:
        """
        証明書の有効期限を確認

        Returns:
            残り日数
        """
        if not cert_path.exists():
            return -1

        try:
            result = subprocess.run([
                "openssl", "x509",
                "-in", str(cert_path),
                "-noout",
                "-enddate"
            ], capture_output=True, text=True, check=True)

            # Parse: notAfter=Jan  1 00:00:00 2025 GMT
            date_str = result.stdout.strip().replace("notAfter=", "")
            expiration = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
            remaining = (expiration - datetime.now()).days

            logger.info(f"[TLS] Certificate {cert_path.name} expires in {remaining} days")
            return remaining
        except Exception as e:
            logger.error(f"[TLS] Failed to check certificate expiration: {e}")
            return -1

# Convenience functions
def setup_dev_tls(certs_dir: Path = Path("certs")) -> Tuple[Path, Path]:
    """
    開発環境用TLS証明書をセットアップ

    Usage:
        from backend.security.tls_manager import setup_dev_tls

        cert, key = setup_dev_tls()
        # Use with uvicorn --ssl-keyfile {key} --ssl-certfile {cert}
    """
    manager = TLSManager(certs_dir)
    return manager.generate_self_signed_cert()

def setup_mtls(certs_dir: Path = Path("certs")) -> Tuple[Path, Path, Path, Path]:
    """
    mTLS証明書をセットアップ

    Returns:
        (ca_cert, ca_key, client_cert, client_key)
    """
    manager = TLSManager(certs_dir)
    return manager.generate_ca_and_client_cert()
