import io
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
import pandas as pd
from core.db import db
from core.auth import get_current_user, admin_only, ops_or_admin
from core.utils import now_iso, new_id, paginate
from core.audit import log_audit
from services.recognition import normalize, CANONICAL_FIELDS
from services.validation import DEFAULT_RULES

router = APIRouter()

MASTERS = {
    "partners": {"coll": "partners", "key": "code", "label": "Partner"},
    "stores": {"coll": "stores", "key": "code", "label": "Store / SIS"},
    "skus": {"coll": "skus", "key": "code", "label": "SKU / Article"},
    "aliases": {"coll": "aliases", "key": "alias", "label": "Alias"},
    "rules": {"coll": "validation_rules", "key": "code", "label": "Validation Rule"},
    "sender_rules": {"coll": "sender_rules", "key": "pattern", "label": "Sender Rule"},
    "hierarchy": {"coll": "product_hierarchy", "key": "code", "label": "Product Hierarchy"},
    "geo": {"coll": "geo_mapping", "key": "city", "label": "Geo Mapping"},
}


def _coll(name):
    if name not in MASTERS:
        raise HTTPException(status_code=404, detail="Unknown master")
    return db[MASTERS[name]["coll"]]


@router.get("/masters/{name}")
async def list_master(name: str, page: int = 1, page_size: int = 50, search: Optional[str] = None, partner_code: Optional[str] = None,
                      active: Optional[bool] = None, user=Depends(get_current_user)):
    coll = _coll(name)
    q = {}
    if search:
        q["$or"] = [{k: {"$regex": search, "$options": "i"}} for k in ("code", "name", "alias", "field", "pattern", "category", "city", "region")]
    if partner_code:
        q["partner_code"] = partner_code
    if active is not None:
        q["active"] = active
    return await paginate(coll, q, page, page_size, (MASTERS[name]["key"], 1))


@router.post("/masters/{name}")
async def create_master(name: str, body: dict, user=Depends(admin_only)):
    coll = _coll(name)
    key = MASTERS[name]["key"]
    if not body.get(key):
        raise HTTPException(status_code=400, detail=f"{key} is required")
    q = {key: body[key]}
    if name == "stores":
        q["partner_code"] = body.get("partner_code")
    if name == "aliases":
        body["alias_norm"] = normalize(body["alias"])
        body["partner_code"] = body.get("partner_code") or None
        body["source"] = body.get("source", "manual")
        q = {"alias_norm": body["alias_norm"], "partner_code": body["partner_code"]}
        if body.get("field") not in {f["key"] for f in CANONICAL_FIELDS}:
            raise HTTPException(status_code=400, detail="Invalid target field")
    if await coll.find_one(q):
        raise HTTPException(status_code=409, detail=f"{MASTERS[name]['label']} with this {key} already exists")
    doc = {**body, "id": new_id(), "active": body.get("active", True), "version": 1, "created_at": now_iso(), "created_by": user["username"]}
    doc.pop("_id", None)
    await coll.insert_one(dict(doc))
    await log_audit(user["username"], f"master.{name}.created", name, doc["id"], {key: body[key]}, category="masters")
    return doc


@router.put("/masters/{name}/{item_id}")
async def update_master(name: str, item_id: str, body: dict, user=Depends(admin_only)):
    coll = _coll(name)
    old = await coll.find_one({"id": item_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Not found")
    body.pop("id", None)
    body.pop("_id", None)
    if name == "aliases" and body.get("alias"):
        body["alias_norm"] = normalize(body["alias"])
    body["updated_at"] = now_iso()
    body["updated_by"] = user["username"]
    await coll.update_one({"id": item_id}, {"$set": body, "$inc": {"version": 1}})
    await db.master_versions.insert_one({"id": new_id(), "master": name, "item_id": item_id, "version": old.get("version", 1), "snapshot": old, "replaced_at": now_iso(), "by": user["username"]})
    changes = {k: {"from": old.get(k), "to": v} for k, v in body.items() if old.get(k) != v and k not in ("updated_at", "updated_by")}
    await log_audit(user["username"], f"master.{name}.updated", name, item_id, {"changes": changes}, category="masters")
    return await coll.find_one({"id": item_id}, {"_id": 0})


@router.get("/masters/{name}/{item_id}/versions")
async def master_versions(name: str, item_id: str, user=Depends(get_current_user)):
    return await db.master_versions.find({"master": name, "item_id": item_id}, {"_id": 0}).sort("version", -1).to_list(50)


@router.get("/masters/{name}/export/file")
async def export_master(name: str, fmt: str = "csv", user=Depends(get_current_user)):
    coll = _coll(name)
    rows = await coll.find({}, {"_id": 0, "password_hash": 0}).to_list(50000)
    df = pd.DataFrame(rows)
    return _stream_df(df, f"{name}_master", fmt)


@router.post("/masters/{name}/import")
async def import_master(name: str, file: UploadFile = File(...), user=Depends(admin_only)):
    coll = _coll(name)
    key = MASTERS[name]["key"]
    data = await file.read()
    df = pd.read_csv(io.BytesIO(data), dtype=str) if file.filename.lower().endswith(".csv") else pd.read_excel(io.BytesIO(data), dtype=str)
    df = df.where(pd.notnull(df), None)
    created, updated = 0, 0
    for rec in df.to_dict(orient="records"):
        rec = {k.strip(): v for k, v in rec.items() if k and not str(k).startswith("Unnamed")}
        if not rec.get(key):
            continue
        for k in ("aliases", "keywords", "sender_domains", "sender_emails", "subject_patterns"):
            if isinstance(rec.get(k), str):
                rec[k] = [x.strip() for x in rec[k].strip("[]").replace("'", "").split(",") if x.strip()]
        if "active" in rec and isinstance(rec["active"], str):
            rec["active"] = rec["active"].lower() in ("true", "1", "yes")
        if name == "aliases":
            rec["alias_norm"] = normalize(rec["alias"])
        q = {key: rec[key], **({"partner_code": rec.get("partner_code")} if name == "stores" else {})}
        existing = await coll.find_one(q)
        if existing:
            await coll.update_one(q, {"$set": {**rec, "updated_at": now_iso(), "updated_by": user["username"]}, "$inc": {"version": 1}})
            updated += 1
        else:
            await coll.insert_one({**rec, "id": new_id(), "active": rec.get("active", True), "version": 1, "created_at": now_iso(), "created_by": user["username"]})
            created += 1
    await log_audit(user["username"], f"master.{name}.imported", name, None, {"created": created, "updated": updated, "file": file.filename}, category="masters")
    return {"created": created, "updated": updated}


def _stream_df(df, base, fmt):
    buf = io.BytesIO()
    if fmt == "xlsx":
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="data")
        media, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        buf.write(df.to_csv(index=False).encode("utf-8"))
        media, ext = "text/csv", "csv"
    buf.seek(0)
    return StreamingResponse(buf, media_type=media, headers={"Content-Disposition": f'attachment; filename="{base}.{ext}"'})


@router.get("/partners")
async def partners(user=Depends(get_current_user)):
    return await db.partners.find({}, {"_id": 0}).sort("name", 1).to_list(100)


@router.get("/partners/{code}/mappings")
async def partner_mappings(code: str, user=Depends(get_current_user)):
    return await db.partner_mappings.find({"partner_code": code}, {"_id": 0}).sort("version", -1).to_list(100)


@router.get("/partners/{code}/stats")
async def partner_stats(code: str, user=Depends(get_current_user)):
    batches = await db.batches.count_documents({"partner_code": code})
    last = await db.batches.find_one({"partner_code": code}, {"_id": 0, "created_at": 1, "status": 1, "file_name": 1}, sort=[("created_at", -1)])
    stores = await db.stores.count_documents({"partner_code": code, "active": True})
    aliases = await db.aliases.count_documents({"partner_code": code, "active": True})
    return {"batches": batches, "last_batch": last, "stores": stores, "learned_aliases": aliases}


@router.get("/settings")
async def get_settings(user=Depends(get_current_user)):
    s = await db.settings.find_one({"key": "global"}, {"_id": 0})
    return s


@router.put("/settings")
async def update_settings(body: dict, user=Depends(admin_only)):
    body.pop("_id", None)
    body["key"] = "global"
    body["updated_at"] = now_iso()
    old = await db.settings.find_one({"key": "global"}, {"_id": 0})
    await db.settings.update_one({"key": "global"}, {"$set": body}, upsert=True)
    await log_audit(user["username"], "settings.updated", "settings", "global", {"before": old, "after": body}, category="config")
    return await db.settings.find_one({"key": "global"}, {"_id": 0})


@router.get("/rules/defaults")
async def rule_defaults(user=Depends(get_current_user)):
    return DEFAULT_RULES


@router.get("/email-config")
async def email_config(user=Depends(get_current_user)):
    connectors = await db.email_connectors.find({}, {"_id": 0, "credentials_encrypted": 0}).to_list(20)
    rules = await db.sender_rules.find({}, {"_id": 0}).sort("partner_code", 1).to_list(200)
    return {"connectors": connectors, "sender_rules": rules,
            "status": "awaiting_credentials", "note": "Email ingestion connector interface is ready. Provide mailbox credentials (Graph / Gmail / IMAP) to activate; credentials are stored encrypted and never returned to the UI."}


@router.put("/email-config/connector")
async def save_connector(body: dict, user=Depends(admin_only)):
    from cryptography.fernet import Fernet
    import base64, hashlib, os
    key = base64.urlsafe_b64encode(hashlib.sha256(os.environ["JWT_SECRET"].encode()).digest())
    f = Fernet(key)
    creds = body.pop("credentials", None)
    doc = {k: v for k, v in body.items() if k != "_id"}
    doc["updated_at"] = now_iso()
    doc["provider"] = doc.get("provider", "imap")
    doc["status"] = "awaiting_credentials"
    if creds and any(creds.values()):
        doc["credentials_encrypted"] = f.encrypt(str(creds).encode()).decode()
        doc["credentials_present"] = True
        doc["status"] = "configured_inactive"
    await db.email_connectors.update_one({"provider": doc["provider"]}, {"$set": doc, "$setOnInsert": {"id": new_id(), "created_at": now_iso()}}, upsert=True)
    await log_audit(user["username"], "email_connector.updated", "email_connector", doc["provider"], {"fields": [k for k in doc if k != "credentials_encrypted"]}, category="config")
    return await db.email_connectors.find_one({"provider": doc["provider"]}, {"_id": 0, "credentials_encrypted": 0})


@router.get("/integrations")
async def integrations(user=Depends(get_current_user)):
    s = await db.settings.find_one({"key": "global"}, {"_id": 0}) or {}
    feats = s.get("features", {})
    items = [
        {"key": "email_ingestion", "name": "Email inbox ingestion", "phase": 2, "status": "awaiting_credentials", "detail": "Graph / Gmail / IMAP connector. Partner detection by sender, domain, subject, attachment, content."},
        {"key": "scheduled_reports", "name": "Scheduled report emails", "phase": 2, "status": "awaiting_credentials", "detail": "SMTP / SendGrid / Resend delivery of saved report views."},
        {"key": "whatsapp", "name": "WhatsApp alerts", "phase": 2, "status": "awaiting_credentials", "detail": "Twilio / Meta Cloud API channel for critical notifications."},
        {"key": "erp_pos", "name": "ERP / POS integration", "phase": 2, "status": "interface_ready", "detail": "REST push of reporting rows via /api/reports/records and batch webhooks."},
        {"key": "bi", "name": "BI connector", "phase": 2, "status": "interface_ready", "detail": "Paginated reporting endpoints + Excel/CSV exports ready for Power BI / Tableau."},
        {"key": "llm_insights", "name": "LLM insights & 'Ask Bata Sales Data'", "phase": 2, "status": "deferred", "detail": "Natural-language query module stub. Rule-based insights active today."},
    ]
    for i in items:
        i["enabled"] = bool(feats.get(i["key"], False))
    return items
