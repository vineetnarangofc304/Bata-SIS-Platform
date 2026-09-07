import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response
from pydantic import BaseModel
from core.db import db
from core.auth import get_current_user, ops_or_admin
from core.utils import now_iso, new_id, paginate
from core.audit import log_audit, notify
from core.storage import load_file
from services import pipeline
from services.recognition import CANONICAL_FIELDS
from services.parser import parse_file, detect_header_row, extract_rows
from services.recognition import normalize, build_alias_index

router = APIRouter()
MAX_SIZE = 50 * 1024 * 1024


@router.get("/fields")
async def fields(user=Depends(get_current_user)):
    return CANONICAL_FIELDS


@router.post("/uploads/preview")
async def preview(file: UploadFile = File(...), user=Depends(ops_or_admin)):
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50MB limit")
    try:
        sheets = await asyncio.to_thread(parse_file, file.filename, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")
    alias_idx = await build_alias_index(None)
    out = []
    for s in sheets:
        hidx, hconf = detect_header_row(s["rows"], set(alias_idx), normalize)
        headers, rows, skipped = extract_rows(s["rows"], hidx)
        out.append({"name": s["name"], "n_rows": s["n_rows"], "n_cols": s["n_cols"], "header_row": hidx, "header_confidence": hconf,
                    "headers": headers, "data_rows": len(rows), "skipped": skipped, "preview": s["rows"][:15]})
    return {"file_name": file.filename, "size": len(data), "sheets": out}


@router.post("/uploads")
async def upload(file: UploadFile = File(...), partner_code: Optional[str] = Form(None), notes: Optional[str] = Form(None), user=Depends(ops_or_admin)):
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50MB limit")
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ("xlsx", "xls", "csv", "xlsm"):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls and .csv files are accepted")
    return await pipeline.create_batch(data, file.filename, user, partner_code or None, "upload", notes)


@router.get("/batches")
async def list_batches(page: int = 1, page_size: int = 25, status: Optional[str] = None, partner_code: Optional[str] = None,
                       search: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if status:
        q["status"] = {"$in": status.split(",")}
    if partner_code:
        q["partner_code"] = partner_code
    if search:
        q["$or"] = [{"file_name": {"$regex": search, "$options": "i"}}, {"id": {"$regex": search, "$options": "i"}}]
    if date_from:
        q["created_at"] = {"$gte": date_from}
    if date_to:
        q.setdefault("created_at", {})["$lte"] = date_to + "T23:59:59"
    proj = {"column_mappings": 0, "preview_rows": 0, "status_history": 0, "sheets": 0, "headers": 0}
    return await paginate(db.batches, q, page, page_size, ("created_at", -1), proj)


@router.get("/batches/summary")
async def batch_summary(user=Depends(get_current_user)):
    pipe = [{"$group": {"_id": "$status", "n": {"$sum": 1}, "rows": {"$sum": "$counts.total"}, "accepted": {"$sum": "$counts.accepted"},
                        "warning": {"$sum": "$counts.warning"}, "rejected": {"$sum": "$counts.rejected"}, "duplicate": {"$sum": "$counts.duplicate"}}}]
    by_status = {g["_id"]: g async for g in db.batches.aggregate(pipe)}
    for g in by_status.values():
        g.pop("_id", None)
    open_exc = await db.exceptions.count_documents({"status": "open"})
    return {"by_status": by_status, "total_batches": sum(g["n"] for g in by_status.values()), "open_exceptions": open_exc,
            "awaiting_review": by_status.get("Awaiting Review", {}).get("n", 0),
            "processing": sum(by_status.get(s, {}).get("n", 0) for s in ("Received", "Analysing", "Validating"))}


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: str, user=Depends(get_current_user)):
    b = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found")
    b["open_exceptions"] = await db.exceptions.count_documents({"batch_id": batch_id, "status": "open"})
    return b


@router.get("/batches/{batch_id}/rows")
async def batch_rows(batch_id: str, page: int = 1, page_size: int = 50, status: Optional[str] = None, layer: str = "standardized", user=Depends(get_current_user)):
    if layer == "raw":
        return await paginate(db.raw_rows, {"batch_id": batch_id}, page, page_size, ("row_index", 1))
    if layer == "reporting":
        return await paginate(db.sales, {"batch_id": batch_id}, page, page_size, ("sale_date", 1))
    q = {"batch_id": batch_id, "is_current": True}
    if status:
        q["status"] = {"$in": status.split(",")}
    return await paginate(db.std_rows, q, page, page_size, ("row_index", 1))


@router.get("/batches/{batch_id}/rows/{raw_row_id}/history")
async def row_history(batch_id: str, raw_row_id: str, user=Depends(get_current_user)):
    raw = await db.raw_rows.find_one({"id": raw_row_id}, {"_id": 0})
    versions = await db.std_rows.find({"raw_row_id": raw_row_id}, {"_id": 0}).sort("version", 1).to_list(50)
    return {"raw": raw, "versions": versions}


@router.get("/batches/{batch_id}/download")
async def download(batch_id: str, user=Depends(get_current_user)):
    b = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not b or not b.get("storage_path"):
        raise HTTPException(status_code=404, detail="Original file not available")
    data = await asyncio.to_thread(load_file, b["storage_path"], b.get("storage_backend"))
    await log_audit(user["username"], "file.downloaded", "batch", batch_id, {"file_name": b["file_name"]}, batch_id, "ingestion")
    return Response(content=data, media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{b["file_name"]}"'})


class MappingItem(BaseModel):
    source_column: str
    field: Optional[str] = None
    action: str = "map"


class ApproveIn(BaseModel):
    mappings: List[MappingItem]
    remember: bool = True
    partner_code: Optional[str] = None


@router.post("/batches/{batch_id}/approve-mapping")
async def approve_mapping(batch_id: str, body: ApproveIn, user=Depends(ops_or_admin)):
    try:
        return await pipeline.approve_mapping(batch_id, [m.model_dump() for m in body.mappings], body.remember, user, body.partner_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batches/{batch_id}/approve-restatement")
async def approve_restatement(batch_id: str, user=Depends(ops_or_admin)):
    b = await db.batches.find_one({"id": batch_id}, {"_id": 0, "status": 1})
    if not b or b["status"] != "Awaiting Review":
        raise HTTPException(status_code=400, detail="Batch is not awaiting review")
    return await pipeline.approve_restatement(batch_id, user)


@router.post("/batches/{batch_id}/reprocess")
async def reprocess(batch_id: str, user=Depends(ops_or_admin)):
    try:
        return await pipeline.reprocess_batch(batch_id, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class RejectIn(BaseModel):
    reason: str = "Rejected by operator"


@router.post("/batches/{batch_id}/reject")
async def reject(batch_id: str, body: RejectIn, user=Depends(ops_or_admin)):
    return await pipeline.reject_batch(batch_id, user, body.reason)


@router.get("/exceptions")
async def list_exceptions(page: int = 1, page_size: int = 25, status: Optional[str] = "open", batch_id: Optional[str] = None,
                          partner_code: Optional[str] = None, rule_code: Optional[str] = None, severity: Optional[str] = None,
                          assigned_to: Optional[str] = None, search: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if status and status != "all":
        q["status"] = {"$in": status.split(",")}
    for k, v in (("batch_id", batch_id), ("partner_code", partner_code), ("rule_code", rule_code), ("severity", severity), ("assigned_to", assigned_to)):
        if v:
            q[k] = v
    if search:
        q["$or"] = [{"message": {"$regex": search, "$options": "i"}}, {"original_value": {"$regex": search, "$options": "i"}}, {"file_name": {"$regex": search, "$options": "i"}}]
    res = await paginate(db.exceptions, q, page, page_size, ("created_at", -1))
    facets = {}
    for key in ("rule_code", "severity", "partner_code", "status"):
        facets[key] = [{"value": g["_id"], "count": g["n"]} async for g in db.exceptions.aggregate([{"$match": {k: v for k, v in q.items() if k != key}}, {"$group": {"_id": f"${key}", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}])]
    res["facets"] = facets
    return res


@router.get("/exceptions/{exc_id}")
async def get_exception(exc_id: str, user=Depends(get_current_user)):
    e = await db.exceptions.find_one({"id": exc_id}, {"_id": 0})
    if not e:
        raise HTTPException(status_code=404, detail="Exception not found")
    e["row"] = await db.std_rows.find_one({"raw_row_id": e["raw_row_id"], "is_current": True}, {"_id": 0})
    e["raw"] = await db.raw_rows.find_one({"id": e["raw_row_id"]}, {"_id": 0})
    e["versions"] = await db.std_rows.count_documents({"raw_row_id": e["raw_row_id"]})
    e["siblings"] = await db.exceptions.find({"raw_row_id": e["raw_row_id"], "id": {"$ne": exc_id}}, {"_id": 0, "id": 1, "rule_code": 1, "status": 1, "message": 1}).to_list(20)
    return e


class ActionIn(BaseModel):
    action: str
    value: Optional[str] = None
    comment: Optional[str] = None
    assignee: Optional[str] = None
    master_payload: Optional[dict] = None


async def _push_history(exc_id, action, user, note, status=None, extra=None):
    upd = {"$push": {"history": {"action": action, "by": user["username"], "at": now_iso(), "note": note}}, "$set": {"updated_at": now_iso(), **(extra or {})}}
    if status:
        upd["$set"]["status"] = status
    await db.exceptions.update_one({"id": exc_id}, upd)


@router.post("/exceptions/{exc_id}/action")
async def exception_action(exc_id: str, body: ActionIn, user=Depends(ops_or_admin)):
    e = await db.exceptions.find_one({"id": exc_id}, {"_id": 0})
    if not e:
        raise HTTPException(status_code=404, detail="Exception not found")
    row = await db.std_rows.find_one({"raw_row_id": e["raw_row_id"], "is_current": True}, {"_id": 0})
    a = body.action
    field = e["field"]
    try:
        if a == "accept":
            if e.get("proposed_value") is None:
                raise HTTPException(status_code=400, detail="No proposed value to accept")
            val = e["proposed_value"]
            await pipeline.revise_row(row["id"], {field: _coerce(field, val)}, user, f"Accepted proposed value for {field}: {val}")
            await _push_history(exc_id, "accept", user, f"Proposed value '{val}' accepted", "accepted", {"resolved_value": val})
        elif a == "correct":
            if body.value is None:
                raise HTTPException(status_code=400, detail="Value required")
            await pipeline.revise_row(row["id"], {field: _coerce(field, body.value)}, user, f"Manual correction of {field} → {body.value}. {body.comment or ''}")
            await _push_history(exc_id, "correct", user, f"Manually corrected to '{body.value}'", "corrected", {"resolved_value": body.value})
        elif a == "map_to_master":
            target = body.value
            if not target:
                raise HTTPException(status_code=400, detail="Target master code required")
            coll = db.stores if field == "store_code" else db.skus
            q = {"code": target, **({"partner_code": e["partner_code"]} if field == "store_code" else {})}
            m = await coll.find_one(q, {"_id": 0})
            if not m:
                raise HTTPException(status_code=404, detail="Master record not found")
            await coll.update_one({"id": m["id"]}, {"$addToSet": {"aliases": e["original_value"]}, "$set": {"updated_at": now_iso()}, "$inc": {"version": 1}})
            await log_audit(user["username"], "master.alias_added", "store" if field == "store_code" else "sku", m["id"], {"alias": e["original_value"], "code": target}, e["batch_id"], "masters")
            await pipeline.revise_row(row["id"], {field: target}, user, f"Mapped '{e['original_value']}' to master {target} (alias remembered)")
            await _push_history(exc_id, "map_to_master", user, f"Mapped to master '{target}', alias saved", "corrected", {"resolved_value": target})
        elif a == "add_master":
            p = body.master_payload or {}
            code = p.get("code") or e["original_value"]
            if field == "store_code":
                doc = {"id": new_id(), "partner_code": e["partner_code"], "code": code, "name": p.get("name") or code, "city": p.get("city"), "region": p.get("region"),
                       "state": p.get("state"), "active": True, "aliases": [], "version": 1, "created_at": now_iso(), "created_by": user["username"], "origin": "exception"}
                await db.stores.insert_one(dict(doc))
            else:
                doc = {"id": new_id(), "code": code, "name": p.get("name") or code, "category": p.get("category") or "Unclassified", "sub_category": p.get("sub_category"),
                       "brand": p.get("brand") or "Bata", "gender": p.get("gender"), "mrp": p.get("mrp"), "active": True, "aliases": [], "version": 1,
                       "created_at": now_iso(), "created_by": user["username"], "origin": "exception"}
                await db.skus.insert_one(dict(doc))
            await log_audit(user["username"], "master.created", "store" if field == "store_code" else "sku", doc["id"], {"code": code, "from_exception": exc_id}, e["batch_id"], "masters")
            await pipeline.revise_row(row["id"], {field: code}, user, f"Added new master {code} and revalidated")
            await _push_history(exc_id, "add_master", user, f"Master '{code}' created", "corrected", {"resolved_value": code})
        elif a == "ignore":
            await db.std_rows.update_one({"id": row["id"]}, {"$pull": {"issues": {"rule_code": e["rule_code"]}}})
            row2 = await db.std_rows.find_one({"id": row["id"]}, {"_id": 0})
            new_status = "rejected" if any(i["blocking"] for i in row2["issues"]) else "warning" if row2["issues"] else "accepted"
            await db.std_rows.update_one({"id": row["id"]}, {"$set": {"status": new_status}})
            await pipeline.revise_row(row["id"], {}, user, f"Issue {e['rule_code']} ignored by operator: {body.comment or ''}") if False else None
            await _push_history(exc_id, "ignore", user, body.comment or "Ignored by operator", "ignored")
            batch = await db.batches.find_one({"id": e["batch_id"]}, {"_id": 0})
            if batch["status"] in pipeline.PROCESSED and new_status in ("accepted", "warning"):
                partner = await db.partners.find_one({"code": batch["partner_code"]}, {"_id": 0})
                row2["status"] = new_status
                await db.sales.replace_one({"id": row2["raw_row_id"]}, pipeline.sales_doc(row2, batch, partner), upsert=True)
            await pipeline.recount_batch(e["batch_id"])
        elif a == "reject_row":
            await db.std_rows.update_one({"id": row["id"]}, {"$set": {"status": "rejected", "rejected_by": user["username"], "rejected_at": now_iso()}})
            await db.sales.delete_many({"id": e["raw_row_id"]})
            await db.exceptions.update_many({"raw_row_id": e["raw_row_id"], "status": "open"}, {"$set": {"status": "rejected", "updated_at": now_iso()},
                                                                                              "$push": {"history": {"action": "reject_row", "by": user["username"], "at": now_iso(), "note": body.comment or "Row rejected"}}})
            await pipeline.recount_batch(e["batch_id"])
        elif a == "reject_file":
            await pipeline.reject_batch(e["batch_id"], user, body.comment or f"Rejected from exception {exc_id[:8]}")
        elif a == "assign":
            await _push_history(exc_id, "assign", user, f"Assigned to {body.assignee}", None, {"assigned_to": body.assignee})
            await notify("assignment", "Exception assigned to you", f"{user['username']} assigned exception {e['rule_code']} (row {e['row_index']}, {e['file_name']}) to you.",
                         f"/review?exception={exc_id}", roles=[], user_id=body.assignee, batch_id=e["batch_id"])
        elif a == "comment":
            await db.exceptions.update_one({"id": exc_id}, {"$push": {"comments": {"by": user["username"], "at": now_iso(), "text": body.comment}}})
            await _push_history(exc_id, "comment", user, body.comment)
        elif a == "revalidate":
            await pipeline.revise_row(row["id"], {}, user, "Revalidated against current masters and rules")
            await _push_history(exc_id, "revalidate", user, "Row revalidated")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action {a}")
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    await log_audit(user["username"], f"exception.{a}", "exception", exc_id, {"value": body.value, "comment": body.comment, "rule": e["rule_code"], "row": e["row_index"]}, e["batch_id"], "exceptions")
    return await get_exception(exc_id, user)


def _coerce(field, val):
    from services.recognition import FIELD_MAP
    from services.parser import parse_number, parse_date
    t = FIELD_MAP[field]["type"]
    if t == "number":
        n = parse_number(val)
        if n is None:
            raise ValueError(f"'{val}' is not a valid number")
        return n
    if t == "date":
        d = parse_date(val)
        if d is None:
            raise ValueError(f"'{val}' is not a valid date")
        return d
    return str(val).strip()


class BulkIn(BaseModel):
    ids: List[str]
    action: str
    comment: Optional[str] = None
    assignee: Optional[str] = None


@router.post("/exceptions/bulk")
async def bulk(body: BulkIn, user=Depends(ops_or_admin)):
    done, errors = 0, []
    for i in body.ids:
        try:
            await exception_action(i, ActionIn(action=body.action, comment=body.comment, assignee=body.assignee), user)
            done += 1
        except HTTPException as ex:
            errors.append({"id": i, "error": ex.detail})
    return {"done": done, "errors": errors}


@router.get("/review-queue")
async def review_queue(user=Depends(get_current_user)):
    batches = await db.batches.find({"status": "Awaiting Review"}, {"_id": 0, "column_mappings": 0, "preview_rows": 0, "status_history": 0}).sort("created_at", -1).to_list(200)
    exc = await db.exceptions.count_documents({"status": "open"})
    mine = await db.exceptions.count_documents({"status": "open", "assigned_to": user["username"]})
    return {"batches": batches, "open_exceptions": exc, "assigned_to_me": mine}
