# services/auth/auth_service.py
from datetime import datetime, timedelta
import os
import redis
import json
import secrets
from passlib.context import CryptContext
from typing import Dict, Optional

from monitoring.agent_logger import get_logger
logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    """
    Service for authentication and user management
    
    Uses Redis for simplicity, but could be replaced with a more robust
    database in production environments.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize auth service with Redis connection"""
        self.redis = redis.from_url(redis_url)
        self.jwt_secret = os.getenv("JWT_SECRET_KEY", "development_secret_key")
        self.token_expire_minutes = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
        logger.info("AuthService initialized")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return pwd_context.hash(password)
    
    async def authenticate_user(self, username: str, password: str) -> Dict:
        """
        Authenticate a user with username and password
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            User data if authenticated, None otherwise
        """
        user = await self.get_user(username)
        
        if not user:
            logger.warning(f"Authentication failed: User {username} not found")
            return None
            
        if not self.verify_password(password, user.get("hashed_password", "")):
            logger.warning(f"Authentication failed: Invalid password for {username}")
            return None
            
        # Return user without password hash
        user_data = user.copy()
        user_data.pop("hashed_password", None)
        
        logger.info(f"User {username} authenticated successfully")
        return user_data
    
    async def get_user(self, username: str) -> Optional[Dict]:
        """
        Get user by username
        
        Args:
            username: Username to look up
            
        Returns:
            User data if found, None otherwise
        """
        user_key = f"user:{username}"
        user_json = self.redis.get(user_key)
        
        if not user_json:
            return None
            
        try:
            return json.loads(user_json)
        except json.JSONDecodeError:
            logger.error(f"Error decoding user data for {username}")
            return None
    
    async def create_user(
        self, 
        username: str, 
        password: str, 
        email: str,
        full_name: Optional[str] = None,
        is_admin: bool = False
    ) -> Dict:
        """
        Create a new user
        
        Args:
            username: Username
            password: Plain text password
            email: Email address
            full_name: Optional full name
            is_admin: Whether user is an admin
            
        Returns:
            Created user data
        """
        # Check if user already exists
        existing_user = await self.get_user(username)
        if existing_user:
            logger.warning(f"User creation failed: Username {username} already exists")
            raise ValueError(f"Username {username} already exists")
            
        # Check if email already exists
        email_key = f"email:{email}"
        if self.redis.exists(email_key):
            logger.warning(f"User creation failed: Email {email} already in use")
            raise ValueError(f"Email {email} already in use")
            
        # Create user data
        user_id = secrets.token_hex(16)  # Generate a unique user ID
        now = datetime.now().isoformat()
        
        user_data = {
            "id": user_id,
            "username": username,
            "email": email,
            "hashed_password": self.get_password_hash(password),
            "full_name": full_name,
            "is_admin": is_admin,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        }
        
        # Store user data
        user_key = f"user:{username}"
        self.redis.set(user_key, json.dumps(user_data))
        
        # Store email reference
        self.redis.set(email_key, username)
        
        # Add to users set
        self.redis.sadd("users", username)
        
        logger.info(f"User {username} created successfully")
        
        # Return user without password hash
        user_response = user_data.copy()
        user_response.pop("hashed_password", None)
        return user_response
    
    async def update_last_login(self, username: str) -> None:
        """
        Update user's last login timestamp
        
        Args:
            username: Username to update
        """
        user = await self.get_user(username)
        if not user:
            return
            
        user["last_login"] = datetime.utcnow().isoformat()
        user["updated_at"] = datetime.utcnow().isoformat()
        
        user_key = f"user:{username}"
        self.redis.set(user_key, json.dumps(user))
        
        logger.info(f"Updated last login for user {username}")
    
    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token
        
        Args:
            data: Data to encode in token
            expires_delta: Optional expiration time override
            
        Returns:
            JWT token string
        """
        from jwt import encode
        
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=self.token_expire_minutes))
        to_encode.update({"exp": expire})
        
        jwt_token = encode(to_encode, self.jwt_secret, algorithm="HS256")
        return jwt_token
    
    def verify_token(self, token: str) -> Dict:
        """
        Verify a JWT token
        
        Args:
            token: JWT token to verify
            
        Returns:
            Token payload if valid
            
        Raises:
            ValueError: If token is invalid
        """
        from jwt import decode, PyJWTError
        
        try:
            payload = decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except PyJWTError as e:
            logger.warning(f"Token verification failed: {str(e)}")
            raise ValueError(f"Invalid token: {str(e)}")