# api/middleware/auth_middleware.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
import os
from datetime import datetime, timedelta
from typing import Dict

# OAuth2 password bearer token scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

# Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development_secret_key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60 * 24  # 24 hours

def create_access_token(data: Dict) -> str:
    """
    Create a new JWT access token
    """
    to_encode = data.copy()
    expires = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    to_encode.update({"exp": expires})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict:
    """
    Verify a JWT token and return its payload
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    """
    Dependency to get the current authenticated user
    """
    payload = verify_token(token)
    # Ensure the token has a subject (user identifier)
    if "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload