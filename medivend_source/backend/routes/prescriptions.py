"""
Prescription management routes — approval queue, review, status.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import json, base64
from datetime import datetime, date

from supabase_client import get_supabase
from models import PrescriptionCreate, PrescriptionReview, PrescriptionResponse

router = APIRouter()

def _ensure_prescriptions_bucket(sb):
    """Create storage bucket if missing (idempotent best effort)."""
    try:
        sb.storage.get_bucket("prescriptions")
        return
    except Exception:
        pass
    try:
        # Default is private bucket; doctor view uses signed URLs.
        sb.storage.create_bucket("prescriptions")
    except Exception:
        # If race/already exists/permission issue, let upload path handle it.
        pass


@router.get("/", summary="Get all prescriptions (admin/pharmacist)")
def get_prescriptions(status: Optional[str] = None, limit: int = 50):
    sb = get_supabase()
    try:
        q = sb.table("prescriptions").select("*").order("uploaded_at", desc=True).limit(limit)
        if status:
            q = q.eq("validation_status", status)
        return q.execute().data
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/stats/summary", summary="Dashboard: pending RX + uploads today counts")
def prescriptions_stats_summary():
    sb = get_supabase()
    today = date.today().isoformat()
    try:
        pending = sb.table("prescriptions").select("*", count="exact").eq(
            "validation_status", "pending"
        ).execute()
        uploaded = sb.table("prescriptions").select("*", count="exact").gte(
            "uploaded_at", today + "T00:00:00"
        ).execute()
        return {
            "pending_count": pending.count or 0,
            "uploaded_today_count": uploaded.count or 0,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/pending", summary="Get pending queue count")
def get_pending_count():
    sb = get_supabase()
    try:
        result = sb.table("prescriptions").select("*", count="exact").eq("validation_status", "pending").execute()
        return {"pending_count": result.count}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/patient/{user_id}", summary="Get prescriptions for a patient")
def get_patient_prescriptions(user_id: int):
    sb = get_supabase()
    try:
        return sb.table("prescriptions").select("*").eq("user_id", user_id).order("uploaded_at", desc=True).execute().data
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{prescription_id}/image-url", summary="Get signed URL for prescription image")
def get_prescription_image_url(prescription_id: int):
    """Generate a signed URL for viewing the prescription image."""
    sb = get_supabase()
    try:
        prescription = sb.table("prescriptions").select("image_storage_path").eq("prescription_id", prescription_id).execute().data
        if not prescription or not prescription[0].get("image_storage_path"):
            raise HTTPException(404, "No image found for this prescription")
        
        path = prescription[0]["image_storage_path"]
        # Generate signed URL valid for 1 hour
        signed_url_obj = sb.storage.from_("prescriptions").create_signed_url(path, expires_in=3600)
        # Extract the actual URL string from the response
        signed_url = signed_url_obj.get("signedURL") if isinstance(signed_url_obj, dict) else str(signed_url_obj)
        return {"url": signed_url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/mine", summary="Get prescriptions for current patient by email/username")
def get_my_prescriptions(email: Optional[str] = None, username: Optional[str] = None, limit: int = 30):
    sb = get_supabase()
    try:
        if not email and not username:
            raise HTTPException(400, "Provide email or username")
        user = _resolve_user_row(sb, email=email, username=username, create_if_missing=False)
        if user:
            return (
                sb.table("prescriptions")
                .select("*")
                .eq("user_id", user["user_id"])
                .order("uploaded_at", desc=True)
                .limit(limit)
                .execute()
                .data
            )
        # Fallback for deployments where users table is not writable/linked to auth.
        rows = (
            sb.table("prescriptions")
            .select("*")
            .order("uploaded_at", desc=True)
            .limit(max(limit * 4, 100))
            .execute()
            .data
        )
        em = (email or "").strip().lower()
        un = (username or "").strip().lower()
        out = []
        for r in rows:
            p = r.get("parsed_data") or {}
            pe = str(p.get("patient_email") or "").strip().lower()
            pu = str(p.get("patient_username") or "").strip().lower()
            if (em and pe == em) or (un and pu == un):
                out.append(r)
            if len(out) >= limit:
                break
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/", summary="Upload new prescription")
def create_prescription(
    user_id: Optional[int] = Form(None),
    user_email: Optional[str] = Form(None),
    user_name: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    sb = get_supabase()
    try:
        uid = _resolve_or_create_user_id(sb, user_id=user_id, email=user_email, username=user_name)
        # Simulate AI OCR extraction
        ocr_text = notes or ""
        parsed = ai_extract_drug(ocr_text)

        parsed = {
            **parsed,
            "patient_email": (user_email or "").strip().lower(),
            "patient_username": (user_name or "").strip().lower(),
        }

        payload = {
            "user_id": uid,
            "ocr_raw_text": ocr_text,
            "parsed_data": parsed,
            "validation_status": "pending",
            "uploaded_at": datetime.utcnow().isoformat()
        }

        # Upload image to Supabase Storage if provided
        if file:
            try:
                contents = file.file.read()
                storage_owner = uid if uid is not None else (user_name or "anonymous")
                path = f"prescriptions/{storage_owner}/{datetime.utcnow().timestamp()}_{file.filename}"
                try:
                    sb.storage.from_("prescriptions").upload(path, contents)
                    print(f"✅ Image uploaded successfully to: {path}")
                except Exception as up_err:
                    msg = str(up_err).lower()
                    print(f"⚠️ Storage upload error: {up_err}")
                    if "bucket not found" in msg or "not found" in msg:
                        _ensure_prescriptions_bucket(sb)
                        sb.storage.from_("prescriptions").upload(path, contents)
                        print(f"✅ Image uploaded after bucket creation: {path}")
                    else:
                        raise
                payload["image_storage_path"] = path
            except Exception as e:
                # Keep upload functional even if storage bucket is missing/misconfigured.
                print(f"❌ Image upload failed: {e}")
                payload["image_storage_path"] = None

        result = sb.table("prescriptions").insert(payload).execute()

        # Log audit
        sb.table("auditlogs").insert({
            "action_type": "PRESCRIPTION_UPLOADED",
            "details": {"user_id": uid, "drug_detected": parsed.get("drug"), "patient_email": (user_email or "").strip().lower()},
        }).execute()

        return {"success": True, "prescription_id": result.data[0]["prescription_id"], "ai_result": parsed}
    except Exception as e:
        raise HTTPException(500, str(e))


def _resolve_or_create_user_id(sb, user_id: Optional[int], email: Optional[str], username: Optional[str]) -> Optional[int]:
    if user_id is not None:
        return int(user_id)
    user = _resolve_user_row(sb, email=email, username=username, create_if_missing=False)
    if not user:
        # Some deployments only expose anon-level DB access; keep upload path working.
        return None
    return int(user["user_id"])


def _resolve_user_row(sb, email: Optional[str], username: Optional[str], create_if_missing: bool):
    uname = (username or "").strip()
    if not uname and email:
        uname = email.split("@")[0].strip()
    if not uname:
        return None
    # Schema uses unique username as primary patient identity.
    existing = sb.table("users").select("user_id, username, role").eq("username", uname).limit(1).execute().data
    if existing:
        return existing[0]
    if not create_if_missing:
        return None
    created = (
        sb.table("users")
        .insert({"username": uname, "password_hash": "***", "role": "patient"})
        .execute()
        .data
    )
    return created[0] if created else None


@router.patch("/{prescription_id}/review", summary="Approve or reject prescription")
def review_prescription(prescription_id: int, review: PrescriptionReview):
    sb = get_supabase()
    try:
        update = {
            "validation_status": review.validation_status,
            "rejection_reason": review.rejection_reason,
            "alternative_drug_id": review.alternative_drug_id,
            "pharmacist_notes": review.pharmacist_notes,
        }
        result = sb.table("prescriptions").update(update).eq("prescription_id", prescription_id).execute()

        if not result.data:
            raise HTTPException(404, "Prescription not found")

        # Audit log should never block medical workflow if FK/user mapping is unavailable.
        try:
            sb.table("auditlogs").insert({
                "action_type": review.validation_status.upper(),
                "details": {
                    "prescription_id": prescription_id,
                    "reason": review.rejection_reason,
                    "alternative_drug": review.alternative_drug_id,
                    "pharmacist_notes": review.pharmacist_notes
                }
            }).execute()
        except Exception:
            pass

        return {"success": True, "status": review.validation_status}
    except Exception as e:
        raise HTTPException(500, str(e))


def ai_extract_drug(text: str) -> dict:
    """
    Simple rule-based drug extraction.
    In production: replace with an actual OCR + NLP model (e.g. Amazon Textract, or a fine-tuned BERT).
    """
    drug_keywords = {
        "desloratadine": "Desloratadine 5mg",
        "panadol": "Panadol 500mg", "paracetamol": "Panadol 500mg",
        "amoxicillin": "Amoxicillin 500mg", "amoxil": "Amoxicillin 500mg",
        "ibuprofen": "Ibuprofen 400mg", "brufen": "Ibuprofen 400mg",
        "urea": "Urea 10% Cream",
        "calamine": "Calamine Lotion 8%",
        "diosmin": "Diosmin 500mg", "capillo": "Diosmin 500mg",
        "perampanel": "Perampanel 2mg", "fycompa": "Perampanel 2mg",
        "multivitamin": "Multivitamins Syrup",
        "freestyle": "FreeStyle Libre 2 Sensor",
        "insulin": "BD Insulin Pen Needle 4mm",
        "zinc oxide": "Zinc Oxide 15% Cream",
        "accu-chek": "Accu-Chek Test Strips",
        "charcoal": "Activated Charcoal Powder",
    }

    text_lower = text.lower()
    detected = None
    confidence = 0.0

    for keyword, drug in drug_keywords.items():
        if keyword in text_lower:
            detected = drug
            confidence = 0.91
            break

    return {
        "drug": detected or "Unknown — Manual review required",
        "confidence": confidence,
        "raw_text": text[:200],
        "extraction_method": "keyword_matching_v1",
        "requires_manual_review": detected is None
    }
