from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from db.connect import supabase
from services.emailService import sendOTPEmail
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, EmailStr
from utils.utils import create_access_token, create_refresh_token, verify_token
from dotenv import load_dotenv
import os
import random
import string
from passlib.context import CryptContext

load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = 15
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_expiry():
    return datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserModel(BaseModel):
    user_id: int
    email: str
    exp: datetime = Field(default_factory=get_expiry)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health-check")
async def root():
    return {"status": "healthy", "message": "API is running"}

@app.post("/register")
async def register(request: RegisterRequest):
    try:
        existing_user = supabase.table('users').select("*").eq('email', request.email).execute()
        if existing_user.data:
            raise HTTPException(status_code=400, detail="User already exists")
        
        otp = generate_otp()
        otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        hashed_password = hash_password(request.password)
        
        user_data = {
            "email": request.email,
            "password": hashed_password,
            "otp": otp,
            "otp_expiry": otp_expiry.isoformat(),
            "is_verified": False
        }
        
        supabase.table('users').insert(user_data).execute()
        sendOTPEmail(request.email, otp)
        
        return {"message": "Registration initiated. Please check your email for OTP verification."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest):
    try:
        user_response = supabase.table('users').select("*").eq('email', request.email).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = user_response.data[0]
        if user['is_verified']:
            raise HTTPException(status_code=400, detail="User already verified")
        
        otp_expiry = datetime.fromisoformat(user['otp_expiry'].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > otp_expiry:
            raise HTTPException(status_code=400, detail="OTP expired")
        
        if user['otp'] != request.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")
        
        supabase.table('users').update({
            "is_verified": True,
            "otp": None,
            "otp_expiry": None
        }).eq('email', request.email).execute()
        
        return {"message": "Email verified successfully. You can now login."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    try:
        user_response = supabase.table('users').select("*").eq('email', request.email).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user = user_response.data[0]
        
        if not user['is_verified']:
            raise HTTPException(status_code=401, detail="Email not verified")
        
        if not verify_password(request.password, user['password']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_id = user.get('id') or user.get('user_id') or user.get('uuid')
        if not user_id:
            raise HTTPException(status_code=500, detail="User ID not found")
        
        user_data = {"user_id": user_id, "email": user['email']}
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token(user_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    try:
        token_data = verify_token(request.refresh_token, UserModel)
        
        user_response = None
        for id_field in ['user_id']:
            try:
                user_response = supabase.table('users').select("*").eq(id_field, token_data.user_id).execute()
                if user_response.data:
                    break
            except:
                continue
        
        if not user_response.data:
            raise HTTPException(status_code=401, detail="User not found")
        
        user = user_response.data[0]
        
        user_id = user.get('id') or user.get('user_id') or user.get('uuid')
        if not user_id:
            raise HTTPException(status_code=500, detail="User ID not found")
        
        user_data = {"user_id": user_id, "email": user['email']}
        new_access_token = create_access_token(user_data)
        new_refresh_token = create_refresh_token(user_data)
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


