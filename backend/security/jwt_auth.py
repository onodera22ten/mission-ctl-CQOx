# backend/security/jwt_auth.py
"""
OAuth2/JWT Authentication
JWT token generation, validation, and FastAPI dependency

Features:
- JWT token generation with expiration
- Token validation
- FastAPI dependency for protected endpoints
- Refresh token support
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_deadbeef")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()

class JWTAuth:
    """JWT認証マネージャー"""

    def __init__(
        self,
        secret_key: str = SECRET_KEY,
        algorithm: str = ALGORITHM,
        access_token_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes

    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        JWTアクセストークンを生成

        Args:
            data: トークンに含めるペイロード（例: {"sub": "user_id"}）
            expires_delta: 有効期限（デフォルト: 30分）

        Returns:
            JWT token string
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        to_encode.update({"exp": expire, "iat": datetime.utcnow()})

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, data: Dict) -> str:
        """
        JWTリフレッシュトークンを生成（7日間有効）

        Args:
            data: トークンに含めるペイロード

        Returns:
            JWT refresh token string
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_token(self, token: str) -> Dict:
        """
        JWTトークンをデコード・検証

        Args:
            token: JWT token string

        Returns:
            Decoded payload

        Raises:
            JWTError: Invalid token
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"[JWT] Token validation failed: {e}")
            raise

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """パスワード検証"""
        return pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        """パスワードハッシュ化"""
        return pwd_context.hash(password)


# Global instance
jwt_auth = JWTAuth()


# FastAPI dependency for protected endpoints
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    FastAPI dependency: 保護されたエンドポイントでJWT検証

    Usage:
        @app.get("/protected")
        async def protected_endpoint(user: Dict = Depends(get_current_user)):
            return {"user_id": user["sub"]}

    Raises:
        HTTPException: 401 if token is invalid
    """
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt_auth.decode_token(token)
        user_id: str = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except JWTError:
        raise credentials_exception


# Optional dependency (allows both authenticated and unauthenticated access)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[Dict]:
    """
    FastAPI dependency: オプショナル認証（認証なしでもアクセス可）

    Usage:
        @app.get("/api/data")
        async def get_data(user: Optional[Dict] = Depends(get_current_user_optional)):
            if user:
                # Authenticated user
                return {"message": "Hello", "user_id": user["sub"]}
            else:
                # Anonymous user
                return {"message": "Hello, guest"}
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


# Convenience functions
def create_user_token(user_id: str, additional_claims: Optional[Dict] = None) -> str:
    """
    ユーザーIDからアクセストークンを生成

    Args:
        user_id: ユーザーID
        additional_claims: 追加のクレーム（例: {"role": "admin"}）

    Returns:
        JWT token
    """
    data = {"sub": user_id}
    if additional_claims:
        data.update(additional_claims)

    return jwt_auth.create_access_token(data)


def create_api_key(service_name: str, scopes: list[str]) -> str:
    """
    サービス間通信用APIキー（JWT）を生成

    Args:
        service_name: サービス名（例: "gateway", "engine"）
        scopes: アクセススコープ（例: ["read", "write"]）

    Returns:
        Long-lived JWT API key (7 days)
    """
    data = {
        "sub": f"service:{service_name}",
        "scopes": scopes,
        "type": "api_key"
    }

    return jwt_auth.create_access_token(
        data,
        expires_delta=timedelta(days=7)
    )
