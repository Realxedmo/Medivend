"""Analytics routes — revenue, audit logs, sales history."""
from fastapi import APIRouter, HTTPException, Query
from supabase_client import get_supabase
from datetime import datetime, date, timedelta
from typing import Optional

router = APIRouter()

@router.get("/revenue", summary="Revenue statistics")
def get_revenue():
    sb = get_supabase()
    try:
        today = date.today().isoformat()
        month_start = date.today().replace(day=1).isoformat()
        today_tx = sb.table("transactions").select("total_price").gte("transaction_time", today+"T00:00:00").execute().data
        month_tx = sb.table("transactions").select("total_price").gte("transaction_time", month_start+"T00:00:00").execute().data
        all_tx   = sb.table("transactions").select("*", count="exact").execute()
        return {
            "today_revenue":  round(sum(r.get("total_price", 0) for r in today_tx), 2),
            "month_revenue":  round(sum(r.get("total_price", 0) for r in month_tx), 2),
            "today_orders":   len(today_tx),
            "total_orders":   all_tx.count or 0,
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/transactions", summary="Recent transactions")
def get_transactions(limit: int = 20):
    sb = get_supabase()
    try:
        return sb.table("transactions").select("*, drugs(brand_names)").order("transaction_time", desc=True).limit(limit).execute().data
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/audit", summary="Audit log")
def get_audit(action_type: Optional[str] = None, limit: int = 50):
    sb = get_supabase()
    try:
        q = sb.table("auditlogs").select("*, users(username)").order("timestamp", desc=True).limit(limit)
        if action_type:
            q = q.eq("action_type", action_type)
        return q.execute().data
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/sales-history", summary="Sales history for charts")
def get_sales_history(drug_id: Optional[int] = None, days: int = 30):
    sb = get_supabase()
    try:
        start = (date.today() - timedelta(days=days)).isoformat()
        q = sb.table("sales_history").select("*").gte("sale_date", start).order("sale_date")
        if drug_id:
            q = q.eq("drug_id", drug_id)
        return q.execute().data
    except Exception as e:
        raise HTTPException(500, str(e))
