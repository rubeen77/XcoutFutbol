import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from database.supabase_client import supabase

router = APIRouter()
log    = logging.getLogger(__name__)


class WaitlistEntry(BaseModel):
    email: EmailStr


@router.post("")
def join_waitlist(entry: WaitlistEntry):
    existing = (
        supabase.table("lista_espera")
        .select("id")
        .eq("email", entry.email)
        .execute()
    )
    if existing.data:
        return {"ok": True, "message": "Ya estás en la lista."}

    supabase.table("lista_espera").insert({
        "email":  entry.email,
        "fecha":  datetime.now(timezone.utc).isoformat(),
        "origen": "landing",
    }).execute()

    return {"ok": True, "message": "¡Registrado correctamente!"}
