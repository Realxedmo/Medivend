"""Doctor dashboard routes: prescriptions + chats inbox."""
from datetime import datetime
from fastapi import APIRouter, HTTPException

from supabase_client import get_supabase
from models import PrescriptionReview

router = APIRouter()


def _resolve_image_url(sb, image_path: str | None) -> str | None:
    if not image_path:
        return None
    p = str(image_path).strip()
    if not p:
        return None
    if p.startswith("http://") or p.startswith("https://"):
        return p
    try:
        signed = sb.storage.from_("prescriptions").create_signed_url(p, 60 * 60)
        if isinstance(signed, dict):
            u = signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")
            if u:
                if u.startswith("http://") or u.startswith("https://"):
                    return u
                return f"{sb.supabase_url}{u}"
    except Exception:
        pass
    try:
        pub = sb.storage.from_("prescriptions").get_public_url(p)
        if isinstance(pub, dict):
            u = pub.get("publicURL") or pub.get("publicUrl")
            if u:
                return u
        if isinstance(pub, str):
            return pub
    except Exception:
        pass
    return None


@router.get("/prescriptions", summary="Doctor: list prescriptions with patient label")
def doctor_prescriptions(status: str | None = None, limit: int = 100):
    sb = get_supabase()
    try:
        q = sb.table("prescriptions").select("*").order("uploaded_at", desc=True).limit(limit)
        if status:
            q = q.eq("validation_status", status)
        rows = q.execute().data
        # Resolve patient names from users when possible.
        users = sb.table("users").select("user_id, username").limit(5000).execute().data
        by_uid = {u.get("user_id"): u.get("username") for u in (users or [])}
        out = []
        for r in rows or []:
            p = r.get("parsed_data") or {}
            pname = by_uid.get(r.get("user_id")) or p.get("patient_name") or p.get("patient_username") or p.get("patient_email") or "Unknown patient"
            out.append({**r, "patient_name": pname, "image_url": _resolve_image_url(sb, r.get("image_storage_path"))})
        return out
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/prescriptions/{prescription_id}/review", summary="Doctor: approve/reject prescription")
def doctor_review_prescription(prescription_id: int, review: PrescriptionReview):
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
        try:
            sb.table("auditlogs").insert(
                {
                    "action_type": f"DOCTOR_{review.validation_status.upper()}",
                    "details": {
                        "prescription_id": prescription_id,
                        "reason": review.rejection_reason,
                        "alternative_drug": review.alternative_drug_id,
                        "pharmacist_notes": review.pharmacist_notes,
                    },
                }
            ).execute()
        except Exception:
            pass
        return {"success": True, "status": review.validation_status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/chats", summary="Doctor: inbox conversations")
def doctor_chats(doctor_id: str = "doctor", limit: int = 200):
    sb = get_supabase()
    try:
        rows = (
            sb.table("auditlogs")
            .select("*")
            .in_("action_type", ["CHAT_MESSAGE", "CHAT_REQUEST", "CHAT_REQUEST_STATUS", "CHAT_DELETED"])
            .order("timestamp", desc=False)
            .limit(max(limit, 200))
            .execute()
            .data
        )
        # Group by patient + thread for sidebar list.
        chats = {}
        req_status = {}
        has_doctor_msg = {}
        has_patient_msg = {}
        deleted_keys = set()
        for r in rows or []:
            d = r.get("details") or {}
            if str(d.get("doctor_id") or "doctor") != doctor_id:
                continue
            patient_email = str(d.get("patient_email") or "").strip().lower() or "unknown@patient"
            thread_id = str(d.get("thread_id") or "general")
            key = f"{patient_email}::{thread_id}"
            if r.get("action_type") == "CHAT_DELETED":
                deleted_keys.add(key)
                chats.pop(key, None)
                req_status.pop(key, None)
                has_doctor_msg.pop(key, None)
                has_patient_msg.pop(key, None)
                continue
            if key in deleted_keys:
                # New activity after delete re-opens the chat thread.
                deleted_keys.remove(key)
            if r.get("action_type") == "CHAT_REQUEST":
                req_status[key] = d.get("request_status") or req_status.get(key) or "pending"
            if r.get("action_type") == "CHAT_REQUEST_STATUS":
                req_status[key] = d.get("request_status") or req_status.get(key) or "pending"
            if key not in chats:
                chats[key] = {
                    "chat_key": key,
                    "doctor_id": doctor_id,
                    "patient_email": patient_email,
                    "patient_name": d.get("patient_name") or patient_email,
                    "thread_id": thread_id,
                    "last_message": "",
                    "last_at": r.get("timestamp"),
                    "request_status": "pending",
                    "has_request": False,
                }
            if r.get("action_type") == "CHAT_MESSAGE":
                chats[key]["last_message"] = d.get("text") or chats[key]["last_message"]
                chats[key]["last_at"] = r.get("timestamp") or chats[key]["last_at"]
                chats[key]["last_sender_role"] = str(d.get("sender_role") or "")
                if str(d.get("sender_role") or "") == "doctor":
                    has_doctor_msg[key] = True
                if str(d.get("sender_role") or "") == "patient":
                    has_patient_msg[key] = True
            if r.get("action_type") == "CHAT_REQUEST":
                chats[key]["has_request"] = True
                if not chats[key]["last_message"]:
                    chats[key]["last_message"] = (d.get("symptoms") or "New chat request")[:120]
        out = []
        for key, chat in chats.items():
            if key in deleted_keys:
                continue
            if key in req_status:
                chat["request_status"] = req_status[key]
            elif has_doctor_msg.get(key):
                chat["request_status"] = "approved"
            elif has_patient_msg.get(key) or chat.get("has_request"):
                chat["request_status"] = "pending"
            else:
                chat["request_status"] = "pending"
            latest_sender = str(chat.get("last_sender_role") or "")
            chat["needs_attention"] = bool(
                chat["request_status"] == "pending"
                or (chat["request_status"] == "approved" and latest_sender == "patient")
            )
            out.append(chat)
        return sorted(out, key=lambda x: x.get("last_at") or "", reverse=True)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/chats/messages", summary="Doctor: chat messages for selected conversation")
def doctor_chat_messages(doctor_id: str = "doctor", patient_email: str = "", thread_id: str = "general", limit: int = 200):
    sb = get_supabase()
    try:
        rows = (
            sb.table("auditlogs")
            .select("*")
            .eq("action_type", "CHAT_MESSAGE")
            .order("timestamp", desc=False)
            .limit(max(limit, 200))
            .execute()
            .data
        )
        pe = patient_email.strip().lower()
        key = f"{pe}::{thread_id}"
        req_rows = (
            sb.table("auditlogs")
            .select("*")
            .in_("action_type", ["CHAT_REQUEST", "CHAT_REQUEST_STATUS", "CHAT_DELETED", "CHAT_MESSAGE"])
            .order("timestamp", desc=False)
            .limit(500)
            .execute()
            .data
        )
        status = "pending"
        explicit_status = False
        doctor_msg_seen = False
        patient_msg_seen = False
        deleted = False
        for rr in req_rows or []:
            dd = rr.get("details") or {}
            if str(dd.get("doctor_id") or "doctor") != doctor_id:
                continue
            rk = f"{str(dd.get('patient_email') or '').strip().lower()}::{str(dd.get('thread_id') or 'general')}"
            if rk != key:
                continue
            if rr.get("action_type") == "CHAT_DELETED":
                deleted = True
                status = "pending"
                explicit_status = False
                doctor_msg_seen = False
                patient_msg_seen = False
                continue
            if deleted and rr.get("action_type") in ("CHAT_REQUEST", "CHAT_REQUEST_STATUS", "CHAT_MESSAGE"):
                deleted = False
            if rr.get("action_type") == "CHAT_REQUEST":
                status = dd.get("request_status") or status
            if rr.get("action_type") == "CHAT_REQUEST_STATUS":
                status = dd.get("request_status") or status
                explicit_status = True
            if rr.get("action_type") == "CHAT_MESSAGE":
                sr = str(dd.get("sender_role") or "")
                if sr == "doctor":
                    doctor_msg_seen = True
                if sr == "patient":
                    patient_msg_seen = True
        if status == "pending" and doctor_msg_seen:
            status = "approved"
        if (not explicit_status) and status == "approved" and (not doctor_msg_seen) and patient_msg_seen:
            status = "pending"
        if deleted:
            return {"request_status": "pending", "messages": []}
        out = []
        for r in rows or []:
            d = r.get("details") or {}
            if str(d.get("doctor_id") or "doctor") != doctor_id:
                continue
            if str(d.get("patient_email") or "").strip().lower() != pe:
                continue
            if str(d.get("thread_id") or "general") != thread_id:
                continue
            out.append(
                {
                    "sender": d.get("sender_role") or "patient",
                    "sender_name": d.get("sender_name") or "User",
                    "message": d.get("text") or "",
                    "timestamp": r.get("timestamp") or datetime.utcnow().isoformat(),
                }
            )
        return {"request_status": status, "messages": out}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/chats/messages", summary="Doctor: send chat message")
def doctor_send_message(payload: dict):
    sb = get_supabase()
    try:
        text = str(payload.get("message") or payload.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "message is required")
        doctor_id = str(payload.get("doctor_id") or "doctor")
        patient_email = str(payload.get("patient_email") or "").strip().lower()
        if not patient_email:
            raise HTTPException(400, "patient_email is required")
        thread_id = str(payload.get("thread_id") or "general")
        key = f"{patient_email}::{thread_id}"
        req_rows = (
            sb.table("auditlogs")
            .select("*")
            .in_("action_type", ["CHAT_REQUEST", "CHAT_REQUEST_STATUS", "CHAT_DELETED", "CHAT_MESSAGE"])
            .order("timestamp", desc=False)
            .limit(500)
            .execute()
            .data
        )
        status = "pending"
        explicit_status = False
        doctor_msg_seen = False
        patient_msg_seen = False
        deleted = False
        for rr in req_rows or []:
            dd = rr.get("details") or {}
            if str(dd.get("doctor_id") or "doctor") != doctor_id:
                continue
            rk = f"{str(dd.get('patient_email') or '').strip().lower()}::{str(dd.get('thread_id') or 'general')}"
            if rk != key:
                continue
            if rr.get("action_type") == "CHAT_DELETED":
                deleted = True
                status = "pending"
                explicit_status = False
                doctor_msg_seen = False
                patient_msg_seen = False
                continue
            if deleted and rr.get("action_type") in ("CHAT_REQUEST", "CHAT_REQUEST_STATUS", "CHAT_MESSAGE"):
                deleted = False
            if rr.get("action_type") == "CHAT_REQUEST":
                status = dd.get("request_status") or status
            if rr.get("action_type") == "CHAT_REQUEST_STATUS":
                status = dd.get("request_status") or status
                explicit_status = True
            if rr.get("action_type") == "CHAT_MESSAGE":
                sr = str(dd.get("sender_role") or "")
                if sr == "doctor":
                    doctor_msg_seen = True
                if sr == "patient":
                    patient_msg_seen = True
        if status == "pending" and doctor_msg_seen:
            status = "approved"
        if (not explicit_status) and status == "approved" and (not doctor_msg_seen) and patient_msg_seen:
            status = "pending"
        if status != "approved":
            raise HTTPException(400, f"chat request is {status}; approve first")
        details = {
            "doctor_id": doctor_id,
            "patient_email": patient_email,
            "patient_name": str(payload.get("patient_name") or patient_email),
            "thread_id": thread_id,
            "sender_role": "doctor",
            "sender_name": str(payload.get("sender_name") or "Doctor"),
            "text": text,
            "time": datetime.utcnow().strftime("%I:%M %p"),
            "created_at": datetime.utcnow().isoformat(),
        }
        sb.table("auditlogs").insert(
            {"action_type": "CHAT_MESSAGE", "details": details, "timestamp": datetime.utcnow().isoformat()}
        ).execute()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/chats/request", summary="Doctor: approve or decline chat request")
def doctor_decide_chat_request(payload: dict):
    sb = get_supabase()
    try:
        doctor_id = str(payload.get("doctor_id") or "doctor")
        patient_email = str(payload.get("patient_email") or "").strip().lower()
        thread_id = str(payload.get("thread_id") or "general")
        decision = str(payload.get("decision") or "").strip().lower()
        if decision not in ("approved", "declined"):
            raise HTTPException(400, "decision must be approved or declined")
        sb.table("auditlogs").insert(
            {
                "action_type": "CHAT_REQUEST_STATUS",
                "details": {
                    "doctor_id": doctor_id,
                    "patient_email": patient_email,
                    "thread_id": thread_id,
                    "request_status": decision,
                    "note": str(payload.get("note") or "").strip() or None,
                    "changed_at": datetime.utcnow().isoformat(),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        ).execute()
        return {"success": True, "request_status": decision}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/chats/delete", summary="Doctor: delete chat thread from inbox")
def doctor_delete_chat(payload: dict):
    sb = get_supabase()
    try:
        doctor_id = str(payload.get("doctor_id") or "doctor")
        patient_email = str(payload.get("patient_email") or "").strip().lower()
        thread_id = str(payload.get("thread_id") or "general")
        sb.table("auditlogs").insert(
            {
                "action_type": "CHAT_DELETED",
                "details": {
                    "doctor_id": doctor_id,
                    "patient_email": patient_email,
                    "thread_id": thread_id,
                    "deleted_at": datetime.utcnow().isoformat(),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        ).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
