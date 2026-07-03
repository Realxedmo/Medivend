"""
Inventory management routes.
"""
from fastapi import APIRouter, HTTPException
from models import InventoryUpdate, InventoryCreate, StockAddRequest
from supabase_client import get_supabase
from datetime import datetime

router = APIRouter()

@router.get("/", summary="Get all inventory records")
def get_inventory():
    sb = get_supabase()
    try:
        return sb.table("inventory").select("*, drugs(brand_names, classification)").order("quantity_in_stock").execute().data
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/stats", summary="Inventory summary statistics")
def inventory_stats():
    sb = get_supabase()
    try:
        data = sb.table("inventory").select("*").execute().data
        from datetime import date, timedelta
        today = date.today()
        expiry_soon = (today + timedelta(days=90)).isoformat()
        return {
            "total_drugs":       len(data),
            "total_units":       sum(r.get("quantity_in_stock", 0) for r in data),
            "critical_count":    sum(1 for r in data if r.get("quantity_in_stock", 0) <= r.get("reorder_threshold", 10)),
            "expiring_soon":     sum(1 for r in data if r.get("expiry_date") and r["expiry_date"] <= expiry_soon),
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@router.patch("/{inventory_id}", summary="Update stock level inline")
def update_inventory(inventory_id: int, update: InventoryUpdate, user_id: int = 1):
    sb = get_supabase()
    try:
        payload = {k: v for k, v in update.dict().items() if v is not None}
        payload["last_updated"] = datetime.utcnow().isoformat()
        # Convert date objects to ISO format strings for JSON serialization
        if 'expiry_date' in payload and payload['expiry_date']:
            payload['expiry_date'] = payload['expiry_date'].isoformat()
        result = sb.table("inventory").update(payload).eq("inventory_id", inventory_id).execute()
        if not result.data:
            raise HTTPException(404, "Inventory record not found")
        sb.table("auditlogs").insert({"user_id": user_id, "action_type": "STOCK_UPDATE", "details": {"inventory_id": inventory_id, **payload}}).execute()
        return {"success": True, "updated": result.data[0]}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/add-stock", summary="Add stock to a drug")
def add_stock(req: StockAddRequest, user_id: int = 1):
    sb = get_supabase()
    try:
        existing = sb.table("inventory").select("*").eq("drug_id", req.drug_id).maybeSingle().execute().data
        expiry_iso = req.expiry_date.isoformat() if req.expiry_date else None
        if existing:
            new_qty = existing["quantity_in_stock"] + req.quantity_to_add
            sb.table("inventory").update({"quantity_in_stock": new_qty, "expiry_date": expiry_iso, "last_updated": datetime.utcnow().isoformat()}).eq("inventory_id", existing["inventory_id"]).execute()
        else:
            sb.table("inventory").insert({"drug_id": req.drug_id, "quantity_in_stock": req.quantity_to_add, "expiry_date": expiry_iso}).execute()
        sb.table("auditlogs").insert({"user_id": user_id, "action_type": "STOCK_UPDATE", "details": {"drug_id": req.drug_id, "qty_added": req.quantity_to_add, "batch": req.batch_number}}).execute()
        return {"success": True, "message": f"Added {req.quantity_to_add} units to drug #{req.drug_id}"}
    except Exception as e:
        raise HTTPException(500, str(e))
