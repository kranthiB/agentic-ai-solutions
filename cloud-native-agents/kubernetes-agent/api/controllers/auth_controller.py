# api/controllers/auth_controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
# Import models and services
from api.models.auth import Token, UserCreate, UserResponse
from services.auth.auth_service import AuthService

from monitoring.agent_logger import get_logger
logger = get_logger(__name__)

# Initialize router
router = APIRouter()

# Initialize services
auth_service = AuthService()

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = await auth_service.authenticate_user(
        form_data.username, 
        form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login time
    await auth_service.update_last_login(form_data.username)
    
    # Create access token
    token_data = {
        "sub": user["id"],
        "username": user["username"],
        "is_admin": user.get("is_admin", False)
    }
    
    access_token = auth_service.create_access_token(token_data)
    
    return Token(
        access_token=access_token,
        token_type="bearer"
    )

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate):
    """
    Register a new user
    """
    try:
        user = await auth_service.create_user(
            username=user_data.username,
            password=user_data.password,
            email=user_data.email,
            full_name=user_data.full_name,
            is_admin=False  # New users are never admins by default
        )
        
        return UserResponse(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            full_name=user["full_name"],
            is_admin=user["is_admin"],
            created_at=user["created_at"]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )