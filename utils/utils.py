import os
from datetime import datetime, timedelta,timezone
from typing import Union
from jose import jwt,JWTError
from  dotenv import load_dotenv
from fastapi import HTTPException
from pydantic import BaseModel,ValidationError
load_dotenv()




SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 50
REFRESH_TOKEN_EXPIRE_DAYS = 4


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, model):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = model.model_validate(payload)
        return token_data
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())





