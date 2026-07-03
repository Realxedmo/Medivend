"""
Pydantic schemas for MediVend API request/response validation.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import date, datetime


# ── AUTH ────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: str
    role: str = "patient"   # patient | pharmacist | admin

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    username: str


# ── DRUGS ───────────────────────────────────────────────
class DrugCreate(BaseModel):
    brand_names: str
    classification: Optional[str] = None
    dosage_form: Optional[str] = None
    strengths: Optional[str] = None
    contraindications: Optional[str] = None
    side_effects: Optional[str] = None
    drug_interactions: Optional[str] = None
    usage_instructions: Optional[str] = None
    source_url: Optional[str] = None
    last_validated_date: Optional[date] = None

class DrugUpdate(BaseModel):
    brand_names: Optional[str] = None
    classification: Optional[str] = None
    dosage_form: Optional[str] = None
    strengths: Optional[str] = None
    contraindications: Optional[str] = None
    side_effects: Optional[str] = None
    drug_interactions: Optional[str] = None
    usage_instructions: Optional[str] = None
    source_url: Optional[str] = None
    last_validated_date: Optional[date] = None

class DrugResponse(DrugCreate):
    drug_id: int


# ── INVENTORY ────────────────────────────────────────────
class InventoryUpdate(BaseModel):
    quantity_in_stock: Optional[int] = None
    expiry_date: Optional[date] = None
    reorder_threshold: Optional[int] = None

class InventoryCreate(BaseModel):
    drug_id: int
    quantity_in_stock: int
    expiry_date: Optional[date] = None
    reorder_threshold: int = 10

class StockAddRequest(BaseModel):
    drug_id: int
    quantity_to_add: int
    expiry_date: Optional[date] = None
    batch_number: Optional[str] = None


# ── PRESCRIPTIONS ────────────────────────────────────────
class PrescriptionCreate(BaseModel):
    image_base64: Optional[str] = None     # Base64 encoded image
    ocr_raw_text: Optional[str] = None
    notes: Optional[str] = None

class PrescriptionReview(BaseModel):
    validation_status: str   # approved | rejected
    rejection_reason: Optional[str] = None
    alternative_drug_id: Optional[int] = None
    pharmacist_notes: Optional[str] = None

class PrescriptionResponse(BaseModel):
    prescription_id: int
    user_id: int
    validation_status: str
    uploaded_at: datetime
    parsed_data: Optional[dict] = None
    rejection_reason: Optional[str] = None


# ── PREDICTIONS ──────────────────────────────────────────
class PredictionResponse(BaseModel):
    drug_id: int
    drug_name: str
    trade_name: str
    category: str
    current_stock: int
    predicted_daily_usage: float
    days_remaining: float
    stock_out_date: str
    alert_level: str        # CRITICAL | WARNING | LOW | OK
    model_mae: float
    model_r2: float
    forecast_30d: List[float]

class PredictionsListResponse(BaseModel):
    predictions: List[PredictionResponse]
    critical_count: int
    warning_count: int
    model_version: str
    generated_at: datetime


# ── ANALYTICS ────────────────────────────────────────────
class RevenueStats(BaseModel):
    today_revenue: float
    month_revenue: float
    total_orders: int
    today_orders: int

class AuditLogEntry(BaseModel):
    log_id: int
    timestamp: datetime
    user_id: Optional[int]
    action_type: str
    details: Optional[dict]

class SalesDataPoint(BaseModel):
    date: str
    drug_name: str
    quantity_sold: int
    revenue: float
