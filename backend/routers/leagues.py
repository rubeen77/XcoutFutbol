from fastapi import APIRouter
from database.supabase_client import supabase

router = APIRouter()


@router.get("")
def get_leagues():
    res = supabase.table("ligas").select("id, nombre, pais").order("id").execute()
    return {"ligas": res.data or []}
