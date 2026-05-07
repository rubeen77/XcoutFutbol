import os
import logging
from datetime import datetime, timezone

import resend
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from database.supabase_client import supabase

router = APIRouter()
log    = logging.getLogger(__name__)

resend.api_key = os.getenv("RESEND_API_KEY", "")


class WaitlistEntry(BaseModel):
    email: EmailStr


def _send_confirmation(email: str) -> None:
    if not resend.api_key:
        log.warning("RESEND_API_KEY no configurado — email omitido.")
        return
    try:
        resend.Emails.send({
            "from":    "Xcout <info@xcoutfutbol.com>",
            "to":      [email],
            "subject": "¡Ya estás en la lista de espera de Xcout! 🚀",
            "html": f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#080C10;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#ffffff;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#080C10;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#0d1520;border:1px solid rgba(255,255,255,0.08);border-radius:16px;overflow:hidden;">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#0d1f30 0%,#080C10 100%);padding:36px 40px 28px;border-bottom:1px solid rgba(0,229,255,0.15);">
          <p style="margin:0;font-size:26px;font-weight:900;letter-spacing:-0.04em;">
            <span style="color:#00E5FF;">X</span><span style="color:#ffffff;font-weight:600;">cout</span>
          </p>
          <p style="margin:8px 0 0;font-size:11px;color:rgba(255,255,255,0.3);letter-spacing:0.12em;text-transform:uppercase;">Football Analytics</p>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:36px 40px;">
          <p style="margin:0 0 8px;font-size:22px;font-weight:800;letter-spacing:-0.03em;">¡Ya estás en la lista! 🎉</p>
          <p style="margin:0 0 24px;font-size:14px;color:rgba(255,255,255,0.45);line-height:1.7;">
            Hola, gracias por apuntarte a la lista de espera de Xcout.<br>
            Te avisaremos en cuanto abramos el acceso.
          </p>

          <!-- Launch badge -->
          <div style="background:rgba(0,229,255,0.06);border:1px solid rgba(0,229,255,0.2);border-radius:10px;padding:16px 20px;margin-bottom:28px;">
            <p style="margin:0;font-size:13px;color:#00E5FF;font-weight:700;">🚀 Lanzamiento previsto: junio 2026</p>
          </div>

          <!-- Features -->
          <p style="margin:0 0 14px;font-size:12px;font-weight:700;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:0.1em;">Qué encontrarás en Xcout</p>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                <span style="color:#00E5FF;font-size:16px;">📊</span>&nbsp;&nbsp;
                <span style="font-size:13px;color:rgba(255,255,255,0.7);">Estadísticas avanzadas con IA — xG, xA, radar charts</span>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                <span style="color:#00E5FF;font-size:16px;">🔍</span>&nbsp;&nbsp;
                <span style="font-size:13px;color:rgba(255,255,255,0.7);">Scouting inteligente con algoritmos de similitud</span>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 0;">
                <span style="color:#00E5FF;font-size:16px;">🤖</span>&nbsp;&nbsp;
                <span style="font-size:13px;color:rgba(255,255,255,0.7);">Análisis narrativo automático de cada jornada</span>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:20px 40px;border-top:1px solid rgba(255,255,255,0.06);">
          <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.2);line-height:1.6;">
            ✕ Xcout · xcoutfutbol.com<br>
            Contacto: <a href="mailto:info@xcoutfutbol.com" style="color:rgba(255,255,255,0.3);">info@xcoutfutbol.com</a><br>
            Sin spam, te lo prometemos. Solo te avisaremos cuando haya novedades importantes.
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
""",
        })
        log.info("Email de confirmación enviado a %s", email)
    except Exception as e:
        log.warning("Error enviando email a %s: %s", email, e)


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

    _send_confirmation(entry.email)

    return {"ok": True, "message": "¡Registrado correctamente!"}
