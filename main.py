from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db.connect import supabase
from services.emailService import sendOTPEmail
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, EmailStr
from utils.utils import create_access_token, create_refresh_token, verify_token
from dotenv import load_dotenv
import os
import random
import string
import csv
import io
import pandas as pd
import json
from passlib.context import CryptContext

load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = 15
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_expiry():
    return datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

def generate_otp():
    return "".join(random.choices(string.digits, k=6))

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
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token_data = verify_token(credentials.credentials, UserModel)
    return token_data

@app.get("/health-check")
async def root():
    return {"status": "healthy", "message": "API is running"}

@app.post("/register")
async def register(request: RegisterRequest):
    try:
        existing_user = supabase.table("users").select("*").eq("email", request.email).execute()
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
            "is_verified": False,
        }

        supabase.table("users").insert(user_data).execute()
        sendOTPEmail(request.email, otp)

        return {"message": "Registration initiated. Please check your email for OTP verification."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest):
    try:
        user_response = supabase.table("users").select("*").eq("email", request.email).execute()

        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = user_response.data[0]
        if user["is_verified"]:
            raise HTTPException(status_code=400, detail="User already verified")

        otp_expiry = datetime.fromisoformat(user["otp_expiry"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > otp_expiry:
            raise HTTPException(status_code=400, detail="OTP expired")

        if user["otp"] != request.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        supabase.table("users").update({"is_verified": True, "otp": None, "otp_expiry": None}).eq("email", request.email).execute()

        return {"message": "Email verified successfully. You can now login."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    try:
        user_response = supabase.table("users").select("*").eq("email", request.email).execute()

        if not user_response.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user = user_response.data[0]

        if not user["is_verified"]:
            raise HTTPException(status_code=401, detail="Email not verified")

        if not verify_password(request.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = user.get("id") or user.get("user_id") or user.get("uuid")
        if not user_id:
            raise HTTPException(status_code=500, detail="User ID not found")

        user_data = {"user_id": user_id, "email": user["email"]}
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token(user_data)

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    try:
        token_data = verify_token(request.refresh_token, UserModel)

        user_response = None
        for id_field in ["user_id"]:
            try:
                user_response = supabase.table("users").select("*").eq(id_field, token_data.user_id).execute()
                if user_response.data:
                    break
            except:
                continue

        if not user_response.data:
            raise HTTPException(status_code=401, detail="User not found")

        user = user_response.data[0]

        user_id = user.get("id") or user.get("user_id") or user.get("uuid")
        if not user_id:
            raise HTTPException(status_code=500, detail="User ID not found")

        user_data = {"user_id": user_id, "email": user["email"]}
        new_access_token = create_access_token(user_data)
        new_refresh_token = create_refresh_token(user_data)

        return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.post("/upload-csv")
async def upload_csv(
    table_name: str = Form(...),
    column_names: str = Form(...),
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="File must be CSV")

        os.makedirs("data", exist_ok=True)
        file_path = f"data/{table_name}_{current_user.user_id}.csv"
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        metadata_path = f"data/{table_name}_{current_user.user_id}.json"
        metadata = {
            "table_name": table_name,
            "column_names": column_names,
            "filename": file.filename,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)
        
        return {
            "message": "Successfully stored CSV file locally",
            "table_name": table_name,
            "filename": file.filename
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-data/{table_name}")
async def get_data(
    table_name: str,
    limit: int = 100,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user)
):
    try:
        file_path = f"data/{table_name}_{current_user.user_id}.csv"
        metadata_path = f"data/{table_name}_{current_user.user_id}.json"
        
        if not os.path.exists(file_path) or not os.path.exists(metadata_path):
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        columns = [col.strip() for col in metadata["column_names"].split(",")]
        
        df = pd.read_csv(file_path)
        df_filtered = df[columns] if all(col in df.columns for col in columns) else df
        
        start = offset
        end = offset + limit
        data_slice = df_filtered.iloc[start:end]
        
        return {
            "data": data_slice.to_dict(orient="records"),
            "total_rows": len(df_filtered),
            "returned_rows": len(data_slice),
            "columns": list(df_filtered.columns)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/get-columns/{table_name}")
async def get_columns(
    table_name: str,
    current_user: UserModel = Depends(get_current_user)
):
    try:
        file_path = f"data/{table_name}_{current_user.user_id}.csv"
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        df = pd.read_csv(file_path)
        
        return {
            "table_name": table_name,
            "columns": list(df.columns),
            "total_columns": len(df.columns)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
class ChartRequest(BaseModel):
    table_name: str
    chart_type: str  # "bar", "line", "pie", "scatter"
    x_column: str
    y_column: str = None
    
@app.post("/generate-chart")
async def generate_chart(
    request: ChartRequest,
    current_user: UserModel = Depends(get_current_user)
):
    try:
        file_path = f"data/{request.table_name}_{current_user.user_id}.csv"
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        df = pd.read_csv(file_path)
        
        if request.x_column not in df.columns:
            raise HTTPException(status_code=400, detail="X column not found")
        
        if request.chart_type == "pie":
            data = df[request.x_column].value_counts().to_dict()
            return {
                "chart_type": "pie",
                "data": [{"label": k, "value": v} for k, v in data.items()]
            }
        
        if request.y_column and request.y_column not in df.columns:
            raise HTTPException(status_code=400, detail="Y column not found")
        
        if request.chart_type in ["bar", "line", "scatter"]:
            if not request.y_column:
                raise HTTPException(status_code=400, detail="Y column required")
            
            chart_data = df[[request.x_column, request.y_column]].to_dict(orient="records")
            return {
                "chart_type": request.chart_type,
                "data": chart_data,
                "x_column": request.x_column,
                "y_column": request.y_column
            }
        
        raise HTTPException(status_code=400, detail="Invalid chart type")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))