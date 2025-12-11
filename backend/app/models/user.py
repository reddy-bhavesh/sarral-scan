from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    fullName: str | None = None
    organization: str | None = None

class UserLogin(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    fullName: str | None = None
    organization: str | None = None
    isAdmin: bool = False
    isActive: bool = True
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class UserUpdate(BaseModel):
    fullName: str | None = None
    organization: str | None = None

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str
