from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.connect import supabase
from services.emailService import sendEmail
from pydantic import BaseModel


class UserModel(BaseModel):
    user_id:int
    username:str
    password:str



app =FastAPI()

@app.get("/health-check")
async def root():
    # addedData = supabase.table('users').insert({"user_id":20,"username": "gaurav","profile_id":20, "table_name": "nothing"}).execute()
    sendEmail("gaurav.shetty@gleecus.com","Registration")
    response =  supabase.table('users').select("*").execute()
    
    return response.data




@app.post("/register")
async def registerRoute(user:UserModel):
    return user
    


















@app.post("/login")
async def loginRoute():
    return {"message": "Login "}

@app.post("/refresh")
async def refreshRoute():
    return {"message": "Refresh Token"}