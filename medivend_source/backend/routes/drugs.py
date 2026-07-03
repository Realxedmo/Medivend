"""Drug catalog routes (service role — used by SPA for live data)."""
from fastapi import APIRouter, HTTPException
from models import DrugCreate, DrugUpdate
from supabase_client import get_supabase

router = APIRouter()


@router.get("/", summary="List drugs")
def list_drugs(limit: int = 500):
    sb = get_supabase()
    try:
        return sb.table("drugs").select("*").order("drug_id").limit(limit).execute().data
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/", summary="Create drug row")
def create_drug(payload: DrugCreate):
    sb = get_supabase()
    try:
        insert = payload.dict(exclude_unset=True)
        # Convert date objects to ISO format strings for JSON serialization
        if 'last_validated_date' in insert and insert['last_validated_date']:
            insert['last_validated_date'] = insert['last_validated_date'].isoformat()
        result = sb.table("drugs").insert(insert).execute()
        return result.data[0] if result.data else {}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/{drug_id}", summary="Update drug row")
def update_drug(drug_id: int, payload: DrugUpdate):
    sb = get_supabase()
    try:
        update = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
        # Convert date objects to ISO format strings for JSON serialization
        if 'last_validated_date' in update and update['last_validated_date']:
            update['last_validated_date'] = update['last_validated_date'].isoformat()
        result = sb.table("drugs").update(update).eq("drug_id", drug_id).execute()
        if not result.data:
            raise HTTPException(404, "Drug not found")
        return result.data[0]
    except Exception as e:
        raise HTTPException(500, str(e))
