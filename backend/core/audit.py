from core.db import db
from core.utils import now_iso, new_id


async def log_audit(actor: str, action: str, entity_type: str, entity_id: str = None, details: dict = None,
                    batch_id: str = None, category: str = "system"):
    doc = {"id": new_id(), "actor": actor, "action": action, "entity_type": entity_type, "entity_id": entity_id,
           "batch_id": batch_id, "category": category, "details": details or {}, "created_at": now_iso()}
    await db.audit_logs.insert_one(doc)


async def notify(ntype: str, title: str, message: str, link: str = None, roles=None, batch_id: str = None,
                 severity: str = "info", user_id: str = None):
    doc = {"id": new_id(), "type": ntype, "title": title, "message": message, "link": link,
           "roles": roles or ["admin", "ops"], "user_id": user_id, "batch_id": batch_id, "severity": severity,
           "read_by": [], "created_at": now_iso(), "channels": {"in_app": "sent", "email": "inactive", "whatsapp": "inactive"}}
    await db.notifications.insert_one(doc)
