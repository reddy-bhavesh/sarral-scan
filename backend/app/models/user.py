from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    full_name: str | None = None
    organization: str | None = None

class UserLogin(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    full_name: str | None = None
    organization: str | None = None
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
