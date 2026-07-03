"""
MediVend Backend API — FastAPI
Connects to Supabase PostgreSQL database.

Run: uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from pathlib import Path
import os
from dotenv import load_dotenv

from supabase_client import get_supabase
from routes import auth, prescriptions, inventory, predictions, analytics, drugs, chat, doctor

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

app = FastAPI(
    title="MediVend API",
    description="Smart Pharmacy Management & Tele-Pharmacy Platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS — allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # In production, set to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router,          prefix="/api/auth",          tags=["Auth"])
app.include_router(prescriptions.router, prefix="/api/prescriptions", tags=["Prescriptions"])
app.include_router(inventory.router,     prefix="/api/inventory",     tags=["Inventory"])
app.include_router(predictions.router,   prefix="/api/predictions",   tags=["ML Predictions"])
app.include_router(analytics.router,     prefix="/api/analytics",     tags=["Analytics"])
app.include_router(drugs.router,       prefix="/api/drugs",         tags=["Drugs"])
app.include_router(chat.router,        prefix="/api/chat",          tags=["Chat"])
app.include_router(doctor.router,      prefix="/api/doctor",        tags=["Doctor"])

FRONTEND_INDEX = Path(__file__).resolve().parents[1] / "frontend" / "index.html"

@app.get("/")
def root():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return {
        "app": "MediVend API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/api")
def api_root():
    return {
        "app": "MediVend API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    sb = get_supabase()
    try:
        sb.table("drugs").select("drug_id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    return {"status": "ok", "database": db_status}
