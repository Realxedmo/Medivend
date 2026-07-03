"""Chat and patient request routes backed by audit logs.

This keeps runtime simple without requiring extra DB tables.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from supabase_client import get_supabase

router = APIRouter()


@router.get("/messages", summary="Get chat messages for a patient thread")
def get_messages(patient_email: str, thread_id: str = "ahmed", limit: int = 100):
    sb = get_supabase()
    try:
        rows = (
            sb.table("auditlogs")
            .select("*")
            .eq("action_type", "CHAT_MESSAGE")
            .order("timestamp", desc=False)
            .limit(max(limit * 5, 200))
            .execute()
            .data
        )
        pe = patient_email.strip().lower()
        out = []
        for r in rows:
            d = r.get("details") or {}
            if str(d.get("patient_email") or "").strip().lower() != pe:
                continue
            if str(d.get("thread_id") or "ahmed") != thread_id:
                continue
            out.append(
                {
                    "side": "sent" if d.get("sender_role") == "patient" else "recv",
                    "text": d.get("text") or "",
                    "time": d.get("time") or "",
                }
            )
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/messages", summary="Post a chat message")
def post_message(payload: dict):
    sb = get_supabase()
    try:
        text = str(payload.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "text is required")
        details = {
            "doctor_id": str(payload.get("doctor_id") or "doctor").strip(),
            "patient_email": str(payload.get("patient_email") or "").strip().lower(),
            "patient_name": str(payload.get("patient_name") or "").strip(),
            "thread_id": str(payload.get("thread_id") or "ahmed").strip(),
            "sender_role": str(payload.get("sender_role") or "patient").strip(),
            "sender_name": str(payload.get("sender_name") or "User").strip(),
            "text": text,
            "time": datetime.utcnow().strftime("%I:%M %p"),
            "created_at": datetime.utcnow().isoformat(),
        }
        sb.table("auditlogs").insert(
            {
                "action_type": "CHAT_MESSAGE",
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ).execute()

        # Auto-open request as pending on first patient-initiated chat thread.
        if details["sender_role"] == "patient":
            req_rows = (
                sb.table("auditlogs")
                .select("*")
                .in_("action_type", ["CHAT_REQUEST", "CHAT_REQUEST_STATUS"])
                .order("timestamp", desc=False)
                .limit(500)
                .execute()
                .data
            )
            found = False
            pe = details["patient_email"]
            th = details["thread_id"]
            did = details["doctor_id"]
            for r in req_rows or []:
                d = r.get("details") or {}
                if str(d.get("doctor_id") or "doctor") != did:
                    continue
                if str(d.get("patient_email") or "").strip().lower() != pe:
                    continue
                if str(d.get("thread_id") or "general") != th:
                    continue
                found = True
                break
            if not found:
                sb.table("auditlogs").insert(
                    {
                        "action_type": "CHAT_REQUEST",
                        "details": {
                            "doctor_id": did,
                            "patient_name": details["patient_name"],
                            "patient_email": pe,
                            "thread_id": th,
                            "request_status": "pending",
                            "symptoms": "Chat message request",
                            "created_at": datetime.utcnow().isoformat(),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ).execute()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/requests", summary="Submit patient chat/symptom request")
def post_request(payload: dict):
    sb = get_supabase()
    try:
        patient_name = str(payload.get("patient_name") or "").strip()
        details = {
            "doctor_id": str(payload.get("doctor_id") or "doctor").strip(),
            "patient_name": patient_name,
            "patient_email": str(payload.get("patient_email") or "").strip().lower(),
            "thread_id": str(payload.get("thread_id") or "general").strip(),
            "request_status": "pending",
            "age": payload.get("age"),
            "symptoms": str(payload.get("symptoms") or "").strip(),
            "duration": str(payload.get("duration") or "").strip(),
            "allergies": str(payload.get("allergies") or "").strip(),
            "preferred_contact": str(payload.get("preferred_contact") or "chat").strip(),
            "created_at": datetime.utcnow().isoformat(),
        }
        if not details["symptoms"]:
            raise HTTPException(400, "symptoms is required")
        sb.table("auditlogs").insert(
            {
                "action_type": "CHAT_REQUEST",
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ).execute()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
