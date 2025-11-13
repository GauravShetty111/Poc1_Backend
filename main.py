from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.connect import supabase

app =FastAPI()

@app.get("/health-check")
async def root():
    # addedData = supabase.table('users').insert({"user_id":20,"username": "gaurav","profile_id":20, "table_name": "nothing"}).execute()
    response =  supabase.table('users').select("*").execute()
    
    return response.data



