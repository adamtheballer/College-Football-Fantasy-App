from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    first_name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    email: str
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    access_token_expires_at: datetime
    token_type: str = "bearer"
    user: UserRead


class RefreshResponse(BaseModel):
    access_token: str
    access_token_expires_at: datetime
    token_type: str = "bearer"


class LogoutResponse(BaseModel):
    success: bool
