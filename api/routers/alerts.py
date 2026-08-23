from typing import Optional

from fastapi import APIRouter

from app import db


router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(uuid: Optional[str] = None, limit: int = 100):
    return await db.list_alerts(uuid, limit)


@router.post("/{alert_id}/ack")
async def ack_alert(alert_id: int):
    await db.set_alert_status(alert_id=alert_id, status=1)
    return {"ok": True}
