"""
HashiCorp Vault統合（NASA/Googleレベル）

【日本語サマリ】
このモジュールはHashiCorp Vaultとの統合を行い、シークレット管理を提供します。

- なぜ必要か: NASA/Googleレベルのセキュリティでは、シークレット（DB パスワード、暗号鍵）を
  コードやコンフィグファイルに直書きせず、専用のシークレット管理システムで管理する必要があります。
- 何をするか: Vault APIを介したシークレットの読み書き、自動ローテーション、動的シークレット生成
- どう検証するか: Vaultサーバーとの通信テスト、シークレット読み書きの成功確認、ローテーション動作確認

【Inputs】
- Vault URL (環境変数 VAULT_ADDR)
- Vault Token (環境変数 VAULT_TOKEN または VAULT_ROLE_ID + VAULT_SECRET_ID)

【Outputs】
- シークレット取得: dict形式のシークレットデータ
- ローテーション: 新しいシークレット値
"""

import os
import logging
from typing import Dict, Any, Optional
import hvac
from hvac.exceptions import VaultError, InvalidPath

logger = logging.getLogger(__name__)


class VaultClient:
    """
    HashiCorp Vault統合クライアント（NASA/Googleレベル）
    
    機能:
    - KV v2シークレットエンジンからの読み書き
    - 動的データベース認証情報生成
    - シークレットの自動ローテーション
    - 監査ログ統合
    """
    
    def __init__(self, 
                 url: Optional[str] = None,
                 token: Optional[str] = None,
                 role_id: Optional[str] = None,
                 secret_id: Optional[str] = None):
        """
        Vaultクライアントの初期化
        
        Args:
            url: Vault URL (デフォルト: $VAULT_ADDR)
            token: Vault Token (デフォルト: $VAULT_TOKEN)
            role_id: AppRole ID (デフォルト: $VAULT_ROLE_ID)
            secret_id: AppRole Secret ID (デフォルト: $VAULT_SECRET_ID)
        """
        self.url = url or os.getenv('VAULT_ADDR', 'http://localhost:8200')
        self.token = token or os.getenv('VAULT_TOKEN')
        self.role_id = role_id or os.getenv('VAULT_ROLE_ID')
        self.secret_id = secret_id or os.getenv('VAULT_SECRET_ID')
        
        self.client = hvac.Client(url=self.url)
        
        # 認証
        if self.token:
            self.client.token = self.token
        elif self.role_id and self.secret_id:
            self._login_approle()
        else:
            raise ValueError("Vault authentication credentials not provided")
        
        # 認証確認
        if not self.client.is_authenticated():
            raise ValueError("Vault authentication failed")
        
        logger.info(f"Vault client initialized: {self.url}")
    
    def _login_approle(self):
        """AppRole認証（本番環境推奨）"""
        try:
            response = self.client.auth.approle.login(
                role_id=self.role_id,
                secret_id=self.secret_id
            )
            self.client.token = response['auth']['client_token']
            logger.info("Vault AppRole authentication successful")
        except VaultError as e:
            logger.error(f"Vault AppRole authentication failed: {e}")
            raise
    
    def read_secret(self, path: str, mount_point: str = 'secret') -> Dict[str, Any]:
        """
        シークレット読み込み（KV v2）
        
        Args:
            path: シークレットパス (例: "cqox/db/credentials")
            mount_point: マウントポイント (デフォルト: "secret")
        
        Returns:
            シークレットデータ (dict)
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=mount_point
            )
            data = response['data']['data']
            logger.info(f"Read secret from Vault: {path}")
            return data
        except InvalidPath:
            logger.warning(f"Secret not found: {path}")
            return {}
        except VaultError as e:
            logger.error(f"Failed to read secret {path}: {e}")
            raise
    
    def write_secret(self, path: str, data: Dict[str, Any], mount_point: str = 'secret'):
        """
        シークレット書き込み（KV v2）
        
        Args:
            path: シークレットパス
            data: 保存するデータ
            mount_point: マウントポイント
        """
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point=mount_point
            )
            logger.info(f"Wrote secret to Vault: {path}")
        except VaultError as e:
            logger.error(f"Failed to write secret {path}: {e}")
            raise
    
    def rotate_secret(self, path: str, mount_point: str = 'secret') -> str:
        """
        シークレットローテーション
        
        Args:
            path: シークレットパス
            mount_point: マウントポイント
        
        Returns:
            新しいシークレット値
        """
        import secrets
        
        # 新しいシークレット生成（32バイト = 256bit）
        new_secret = secrets.token_urlsafe(32)
        
        # Vault更新
        self.write_secret(path, {'value': new_secret}, mount_point)
        
        logger.info(f"Rotated secret: {path}")
        return new_secret
    
    def get_database_credentials(self, role: str = 'cqox-app') -> Dict[str, str]:
        """
        動的データベース認証情報取得（NASA/Googleレベル）
        
        Vaultが自動的に一時的なDB認証情報を生成
        
        Args:
            role: データベースロール名
        
        Returns:
            {"username": "v-...", "password": "..."}
        """
        try:
            response = self.client.secrets.database.generate_credentials(role)
            creds = {
                'username': response['data']['username'],
                'password': response['data']['password'],
                'lease_duration': response['lease_duration']
            }
            logger.info(f"Generated dynamic DB credentials for role: {role}")
            return creds
        except VaultError as e:
            logger.error(f"Failed to generate DB credentials: {e}")
            raise
    
    def get_encryption_key(self, key_name: str = 'cqox-encryption-key') -> bytes:
        """
        データ暗号化鍵取得
        
        Args:
            key_name: 鍵名
        
        Returns:
            AES-256鍵（32バイト）
        """
        import base64
        
        secret = self.read_secret(f'cqox/data/{key_name}')
        
        if 'key' not in secret:
            raise ValueError(f"Encryption key not found: {key_name}")
        
        # Base64デコード
        key_b64 = secret['key']
        key = base64.b64decode(key_b64)
        
        if len(key) != 32:
            raise ValueError(f"Invalid key length: {len(key)} (expected 32)")
        
        return key
    
    def health_check(self) -> bool:
        """Vaultヘルスチェック"""
        try:
            health = self.client.sys.read_health_status(method='GET')
            return health.status_code == 200
        except Exception as e:
            logger.error(f"Vault health check failed: {e}")
            return False


# グローバルVaultクライアント（シングルトン）
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """
    Vaultクライアント取得（シングルトン）
    
    Returns:
        VaultClientインスタンス
    """
    global _vault_client
    
    if _vault_client is None:
        _vault_client = VaultClient()
    
    return _vault_client


def get_secret(path: str, key: Optional[str] = None) -> Any:
    """
    シークレット取得ヘルパー
    
    Args:
        path: Vaultシークレットパス
        key: 特定のキー（指定しない場合は全体を返す）
    
    Returns:
        シークレット値
    """
    vault = get_vault_client()
    data = vault.read_secret(path)
    
    if key:
        return data.get(key)
    return data

