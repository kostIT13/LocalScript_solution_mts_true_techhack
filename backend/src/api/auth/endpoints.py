from fastapi import APIRouter, HTTPException, status, Depends
from src.api.auth.schemas import UserLogin, UserRegister, UserResponse, Token 
from src.api.auth.dependencies import UserServiceDependency, CurrentUserDependency
from src.services.auth.auth_service import AuthService
from fastapi.security import OAuth2PasswordRequestForm


router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(service: UserServiceDependency, data: UserRegister):
    try:
        user = await service.create_user(data.model_dump())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)    
        )
    auth_service = AuthService(service)
    access_token = auth_service.create_access_token(data={"sub": user.id})

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(service: UserServiceDependency, data: UserLogin):
    auth_service = AuthService(service)

    user = await auth_service.authenticate_user(data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_access_token(data={"sub": user.id})
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: CurrentUserDependency):
    return current_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    user_service: UserServiceDependency,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = await AuthService(user_service).authenticate_user(
        email=form_data.username, 
        password=form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный username или password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = AuthService(user_service).create_access_token(
        data={"sub": user.id}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

    


