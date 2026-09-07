import asyncio
import hashlib
import logging
from core.db import db
from core.utils import now_iso, new_id
from core.audit import log_audit, notify
from core.storage import save_file, load_file
from services.parser import parse_file, detect_header_row, extract_rows
from services.recognition import (build_alias_index, load_learned, detect_partner, map_columns, compute_overall,
                                  normalize, CANONICAL_FIELDS)
from services.validation import standardize_row, validate_row, ValidationContext

logger = logging.getLogger("pipeline")
PROCESSED = ("Successfully Processed", "Partially Processed")


async def get_settings():
    s = await db.settings.find_one({"key": "global"}, {"_id": 0})
    return s or {"thresholds": {"high": 90, "medium": 70}, "medium_behavior": "review"}


async def set_status(batch_id, status, by="system", reason=None, extra=None):
    entry = {"status": status, "at": now_iso(), "by": by}
    if reason:
        entry["reason"] = reason
    upd = {"$set": {"status": status, "updated_at": now_iso(), **(extra or {})}, "$push": {"status_history": entry}}
    await db.batches.update_one({"id": batch_id}, upd)


def _strip(doc):
    doc.pop("_id", None)
    return doc


async def create_batch(data: bytes, filename: str, user: dict, partner_code=None, source="upload", notes=None, run_async=True):
    file_hash = hashlib.sha256(data).hexdigest()
    existing = await db.batches.find_one({"file_hash": file_hash, "status": {"$nin": ["Rejected", "Failed"]}}, {"_id": 0})
    now = now_iso()
    batch = {"id": new_id(), "file_name": filename, "file_size": len(data), "file_hash": file_hash, "source": source,
             "uploaded_by": user["username"], "partner_code": partner_code, "partner_selected": partner_code, "status": "Received",
             "status_history": [{"status": "Received", "at": now, "by": user["username"]}],
             "counts": {"total": 0, "accepted": 0, "warning": 0, "rejected": 0, "duplicate": 0},
             "confidence": None, "confidence_level": None, "notes": notes, "created_at": now, "updated_at": now,
             "storage_path": None, "storage_backend": None, "reprocessed": False, "review_reason": None}
    if existing:
        batch.update({"status": "Rejected", "duplicate_of": existing["id"], "partner_code": existing.get("partner_code"), "partner_name": existing.get("partner_name"),
                      "rejection_reason": f"Duplicate file: identical content already received as batch {existing['id'][:8]} ({existing['file_name']})"})
        batch["counts"]["duplicate"] = existing.get("counts", {}).get("total", 0)
        batch["status_history"].append({"status": "Rejected", "at": now, "by": "system", "reason": "file hash already ingested"})
        await db.batches.insert_one(dict(batch))
        await log_audit(user["username"], "batch.rejected_duplicate", "batch", batch["id"],
                        {"file_name": filename, "duplicate_of": existing["id"]}, batch["id"], "ingestion")
        await notify("duplicate", "Duplicate file blocked", f"{filename} is identical to an already ingested file and was rejected.",
                     f"/batches/{batch['id']}", batch_id=batch["id"], severity="warning")
        return _strip(batch)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    ctype = {"csv": "text/csv", "xls": "application/vnd.ms-excel"}.get(ext, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    stored = await asyncio.to_thread(save_file, f"uploads/{batch['id']}.{ext}", data, ctype)
    batch["storage_path"], batch["storage_backend"] = stored["path"], stored["backend"]
    await db.batches.insert_one(dict(batch))
    await db.raw_files.insert_one({"id": new_id(), "batch_id": batch["id"], "file_name": filename, "file_hash": file_hash,
                                   "size": len(data), "content_type": ctype, "storage_path": stored["path"],
                                   "storage_backend": stored["backend"], "is_deleted": False, "created_at": now})
    await log_audit(user["username"], "batch.received", "batch", batch["id"], {"file_name": filename, "size": len(data), "source": source},
                    batch["id"], "ingestion")
    await notify("file_received", "File received", f"{filename} received from {user['username']} and queued for analysis.",
                 f"/batches/{batch['id']}", batch_id=batch["id"])
    if run_async:
        asyncio.create_task(run_job(analyse_batch, batch["id"]))
    else:
        await analyse_batch(batch["id"])
    return _strip(batch)


async def run_job(fn, batch_id):
    for attempt in range(2):
        try:
            await fn(batch_id)
            return
        except Exception as e:
            logger.exception(f"job {fn.__name__} failed for {batch_id} (attempt {attempt + 1}): {e}")
            if attempt == 1:
                await set_status(batch_id, "Failed", reason=str(e)[:300], extra={"failure_reason": str(e)[:300]})
                await notify("critical_failure", "Processing failed", f"Batch {batch_id[:8]} failed: {str(e)[:120]}",
                             f"/batches/{batch_id}", batch_id=batch_id, severity="critical")


async def analyse_batch(batch_id):
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch or batch["status"] not in ("Received",):
        return
    await set_status(batch_id, "Analysing")
    data = await asyncio.to_thread(load_file, batch["storage_path"], batch["storage_backend"])
    sheets = await asyncio.to_thread(parse_file, batch["file_name"], data)
    partners = await db.partners.find({"active": True}, {"_id": 0}).to_list(100)
    settings = await get_settings()
    learned_all = {p["code"]: await load_learned(p["code"]) for p in partners}
    pdet = detect_partner(batch["file_name"], sheets, partners, batch.get("partner_selected"), learned_all)
    partner_code = pdet["partner_code"]
    alias_idx = await build_alias_index(partner_code)
    learned = learned_all.get(partner_code, {}) if partner_code else {}
    known = set(alias_idx) | set(learned)
    analysed = []
    for s in sheets:
        hidx, hconf = detect_header_row(s["rows"], known, normalize)
        headers, rows, skipped = extract_rows(s["rows"], hidx)
        cols = map_columns(headers, rows, alias_idx, learned)
        mapped = sum(1 for c in cols if c["proposed_field"])
        analysed.append({"name": s["name"], "n_rows": s["n_rows"], "n_cols": s["n_cols"], "header_row": hidx, "header_confidence": hconf,
                         "data_rows": len(rows), "skipped": skipped, "mapped_columns": mapped, "columns": cols, "_rows": rows,
                         "headers": headers, "score": mapped * 10 + min(len(rows), 2000) / 100, "preview": s["rows"][:12]})
    best = max(analysed, key=lambda a: a["score"]) if analysed else None
    if not best or not best["data_rows"]:
        await set_status(batch_id, "Failed", reason="No tabular data found", extra={"failure_reason": "No data rows found in any sheet"})
        await notify("critical_failure", "Empty file", f"{batch['file_name']} contained no data rows.", f"/batches/{batch_id}",
                     batch_id=batch_id, severity="critical")
        return
    rows = best.pop("_rows")
    await db.raw_rows.delete_many({"batch_id": batch_id})
    docs = [{"id": new_id(), "batch_id": batch_id, "row_index": i + 1, "source_row": r.pop("__source_row", None), "sheet": best["name"],
             "data": {k: v for k, v in r.items()}} for i, r in enumerate(rows)]
    for i in range(0, len(docs), 2000):
        await db.raw_rows.insert_many(docs[i:i + 2000])
    conf = compute_overall(pdet["confidence"], best["header_confidence"], best["columns"], settings["thresholds"])
    sheets_summary = [{k: v for k, v in a.items() if k not in ("columns", "_rows", "preview", "headers")} for a in analysed]
    partner = next((p for p in partners if p["code"] == partner_code), None)
    await db.batches.update_one({"id": batch_id}, {"$set": {
        "partner_code": partner_code, "partner_name": partner["name"] if partner else None, "partner_detection": pdet,
        "sheets": sheets_summary, "selected_sheet": best["name"], "header_row": best["header_row"], "headers": best["headers"],
        "column_mappings": best["columns"], "confidence": conf["overall"], "confidence_level": conf["level"],
        "confidence_breakdown": conf, "counts.total": len(rows), "preview_rows": best["preview"], "skipped_rows": best["skipped"],
        "updated_at": now_iso()}})
    await log_audit("system", "batch.analysed", "batch", batch_id, {"partner": partner_code, "confidence": conf, "sheet": best["name"],
                                                                     "header_row": best["header_row"], "rows": len(rows)}, batch_id, "recognition")
    if not partner_code:
        await set_status(batch_id, "Awaiting Review", reason="Partner could not be identified",
                         extra={"review_reason": "Partner could not be identified automatically. Select the partner and confirm mappings."})
        await notify("review_required", "Review required: unknown partner", f"{batch['file_name']} needs a partner assignment.",
                     f"/batches/{batch_id}", batch_id=batch_id, severity="warning")
        return
    level = conf["level"]
    if level == "high" or (level == "medium" and settings.get("medium_behavior") == "proceed"):
        await db.batches.update_one({"id": batch_id}, {"$set": {"mapping_approved_by": "system (auto-accept)", "mapping_approved_at": now_iso(),
                                                                "proceeded_with_warning": level == "medium"}})
        await log_audit("system", "mapping.auto_accepted", "batch", batch_id, {"confidence": conf["overall"], "level": level}, batch_id, "recognition")
        await validate_batch(batch_id)
    else:
        why = f"Overall confidence {conf['overall']}% is {level}. " + (f"Missing required fields: {', '.join(conf['missing_required'])}." if conf["missing_required"] else "Confirm proposed column mappings.")
        await set_status(batch_id, "Awaiting Review", reason=why, extra={"review_reason": why})
        await notify("review_required", "Mapping review required", f"{batch['file_name']}: {why}", f"/batches/{batch_id}",
                     batch_id=batch_id, severity="warning")


async def approve_mapping(batch_id, mappings, remember, user, partner_code=None, sheet=None):
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise ValueError("Batch not found")
    if partner_code and partner_code != batch.get("partner_code"):
        partner = await db.partners.find_one({"code": partner_code}, {"_id": 0})
        await db.batches.update_one({"id": batch_id}, {"$set": {"partner_code": partner_code, "partner_name": partner["name"],
                                                                "partner_detection.partner_code": partner_code, "partner_detection.partner_name": partner["name"],
                                                                "partner_detection.confidence": 100, "partner_detection.reason": f"Assigned by {user['username']}"}})
        batch["partner_code"] = partner_code
    cols = batch["column_mappings"]
    by_src = {m["source_column"]: m for m in mappings}
    changes = []
    for c in cols:
        m = by_src.get(c["source_column"])
        if not m:
            continue
        new_field = m.get("field") if m.get("action", "map") != "ignore" else None
        if new_field != c["proposed_field"] or m.get("action") != c.get("action"):
            changes.append({"column": c["source_column"], "from": c["proposed_field"], "to": new_field})
        c["proposed_field"] = new_field
        c["action"] = "ignore" if not new_field else "map"
        c["confidence"] = 100
        c["reason"] = f"Confirmed by {user['username']}" if not changes or changes[-1].get("column") != c["source_column"] else f"Overridden by {user['username']}"
    used = {}
    for c in cols:
        if c["proposed_field"]:
            if c["proposed_field"] in used:
                raise ValueError(f"Field {c['proposed_field']} mapped twice ({used[c['proposed_field']]} and {c['source_column']})")
            used[c["proposed_field"]] = c["source_column"]
    version = None
    if remember and batch["partner_code"]:
        last = await db.partner_mappings.find_one({"partner_code": batch["partner_code"]}, {"_id": 0}, sort=[("version", -1)])
        version = (last["version"] + 1) if last else 1
        await db.partner_mappings.update_many({"partner_code": batch["partner_code"], "active": True}, {"$set": {"active": False}})
        await db.partner_mappings.insert_one({"id": new_id(), "partner_code": batch["partner_code"], "version": version, "active": True,
                                              "mapping": {c["source_column"]: c["proposed_field"] for c in cols if c["proposed_field"]},
                                              "ignored_columns": [c["source_column"] for c in cols if not c["proposed_field"]],
                                              "created_by": user["username"], "source_batch_id": batch_id, "created_at": now_iso()})
        for c in cols:
            if c["proposed_field"]:
                await db.aliases.update_one({"alias_norm": normalize(c["source_column"]), "partner_code": batch["partner_code"]},
                                            {"$setOnInsert": {"id": new_id(), "created_at": now_iso()},
                                             "$set": {"alias": c["source_column"], "field": c["proposed_field"], "source": "learned", "active": True,
                                                      "learned_from_batch": batch_id, "learned_by": user["username"]}}, upsert=True)
    await db.batches.update_one({"id": batch_id}, {"$set": {"column_mappings": cols, "mapping_approved_by": user["username"],
                                                            "mapping_approved_at": now_iso(), "mapping_version": version, "confidence": 100,
                                                            "confidence_level": "high", "confidence_breakdown.overall": 100,
                                                            "confidence_breakdown.level": "high", "confidence_breakdown.missing_required": [],
                                                            "review_reason": None}})
    await log_audit(user["username"], "mapping.approved", "batch", batch_id, {"changes": changes, "remembered": remember, "version": version},
                    batch_id, "mapping")
    await set_status(batch_id, "Validating", by=user["username"])
    await validate_batch(batch_id, by=user["username"])
    return await db.batches.find_one({"id": batch_id}, {"_id": 0})


async def build_context(batch):
    partner = await db.partners.find_one({"code": batch["partner_code"]}, {"_id": 0})
    rules = await db.validation_rules.find({"enabled": True}, {"_id": 0}).to_list(None)
    stores = await db.stores.find({"partner_code": partner["code"], "active": True}, {"_id": 0}).to_list(None)
    skus = await db.skus.find({"active": True}, {"_id": 0, "code": 1, "name": 1, "aliases": 1, "category": 1, "brand": 1}).to_list(None)
    keys = await db.sales.distinct("business_key", {"partner_code": partner["code"], "batch_id": {"$ne": batch["id"]}})
    return ValidationContext(partner, rules, stores, skus, keys)


def _mapping_dict(batch):
    return {c["source_column"]: c["proposed_field"] for c in batch.get("column_mappings", []) if c.get("proposed_field") and c.get("action", "map") != "ignore"}


def _exception_doc(batch, row, issue):
    return {"id": new_id(), "batch_id": batch["id"], "partner_code": batch["partner_code"], "partner_name": batch.get("partner_name"),
            "file_name": batch["file_name"], "raw_row_id": row["raw_row_id"], "std_row_id": row["id"], "row_index": row["row_index"],
            "source_row": row.get("source_row"), "rule_code": issue["rule_code"], "severity": issue["severity"], "blocking": issue["blocking"],
            "field": issue["field"], "message": issue["message"], "original_value": issue["original_value"],
            "proposed_value": issue["proposed_value"], "status": "open", "assigned_to": None, "comments": [],
            "history": [{"action": "created", "by": "system", "at": now_iso(), "note": issue["message"]}], "created_at": now_iso(), "updated_at": now_iso()}


async def validate_batch(batch_id, by="system"):
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if batch["status"] != "Validating":
        await set_status(batch_id, "Validating", by=by)
    ctx = await build_context(batch)
    mapping = _mapping_dict(batch)
    raw_rows = await db.raw_rows.find({"batch_id": batch_id}, {"_id": 0}).sort("row_index", 1).to_list(None)
    await db.std_rows.delete_many({"batch_id": batch_id})
    await db.exceptions.delete_many({"batch_id": batch_id})
    std_docs, exc_docs = [], []
    counts = {"total": len(raw_rows), "accepted": 0, "warning": 0, "rejected": 0, "duplicate": 0}
    for r in raw_rows:
        values, originals = standardize_row(r["data"], mapping)
        row = {"id": new_id(), "batch_id": batch_id, "raw_row_id": r["id"], "row_index": r["row_index"], "source_row": r.get("source_row"),
               "partner_code": batch["partner_code"], "version": 1, "is_current": True, "values": values, "original_values": originals,
               "issues": [], "status": "accepted", "created_at": now_iso(), "created_by": by, "change_note": "initial standardization"}
        issues = validate_row(row, ctx)
        counts[row["status"]] += 1
        std_docs.append(row)
        exc_docs.extend(_exception_doc(batch, row, i) for i in issues)
    for i in range(0, len(std_docs), 2000):
        await db.std_rows.insert_many(std_docs[i:i + 2000])
    for i in range(0, len(exc_docs), 2000):
        await db.exceptions.insert_many(exc_docs[i:i + 2000])
    dates = [d["values"]["sale_date"] for d in std_docs if d["status"] in ("accepted", "warning") and d["values"].get("sale_date")]
    period = {"from": min(dates), "to": max(dates)} if dates else None
    await db.batches.update_one({"id": batch_id}, {"$set": {"counts": counts, "period": period, "exception_count": len(exc_docs), "updated_at": now_iso()}})
    await log_audit(by, "batch.validated", "batch", batch_id, {"counts": counts, "exceptions": len(exc_docs)}, batch_id, "validation")
    unknown = {i["rule_code"] for i in [e for e in exc_docs] if i["rule_code"] in ("UNKNOWN_STORE", "UNKNOWN_SKU")}
    for code in unknown:
        n = sum(1 for e in exc_docs if e["rule_code"] == code)
        await notify(code.lower(), f"{n} row(s) with {code.replace('_', ' ').lower()}", f"{batch['file_name']} has {n} row(s) referencing an unknown {'store' if 'STORE' in code else 'article'}.",
                     f"/review?batch={batch_id}", batch_id=batch_id, severity="warning")
    await _check_row_count_anomaly(batch, counts, ctx)
    if period and not batch.get("restatement_approved"):
        overlap = await db.batches.find_one({"partner_code": batch["partner_code"], "id": {"$ne": batch_id}, "status": {"$in": PROCESSED},
                                             "period.from": {"$lte": period["to"]}, "period.to": {"$gte": period["from"]}}, {"_id": 0, "id": 1, "file_name": 1, "period": 1})
        if overlap:
            why = f"Restatement: period {period['from']} → {period['to']} overlaps already-processed batch {overlap['id'][:8]} ({overlap['file_name']}). Approve to supersede."
            await set_status(batch_id, "Awaiting Review", by=by, reason=why, extra={"review_reason": why, "restatement_of": overlap["id"]})
            await notify("review_required", "Restatement needs approval", why, f"/batches/{batch_id}", batch_id=batch_id, severity="warning")
            return
    await load_to_reporting(batch_id, by)


async def _check_row_count_anomaly(batch, counts, ctx):
    rule = ctx.rules.get("ROW_COUNT_ANOMALY")
    if not rule:
        return
    hist = await db.batches.find({"partner_code": batch["partner_code"], "id": {"$ne": batch["id"]}, "status": {"$in": PROCESSED}},
                                 {"_id": 0, "counts.total": 1}).sort("created_at", -1).limit(10).to_list(10)
    if len(hist) < 3:
        return
    avg = sum(h["counts"]["total"] for h in hist) / len(hist)
    dev = abs(counts["total"] - avg) / avg * 100 if avg else 0
    if dev > rule["params"].get("deviation_pct", 50):
        msg = f"Batch has {counts['total']} rows vs partner average {avg:.0f} ({dev:.0f}% deviation)"
        await db.batches.update_one({"id": batch["id"]}, {"$set": {"row_count_anomaly": msg}})
        await notify("anomaly", "Row count anomaly", f"{batch['file_name']}: {msg}", f"/batches/{batch['id']}", batch_id=batch["id"], severity="info")


async def load_to_reporting(batch_id, by="system"):
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    partner = await db.partners.find_one({"code": batch["partner_code"]}, {"_id": 0})
    counts = batch["counts"]
    loadable = counts["accepted"] + counts["warning"]
    await db.sales.delete_many({"batch_id": batch_id})
    if loadable == 0:
        await set_status(batch_id, "Failed", by=by, reason="No valid rows", extra={"failure_reason": "All rows were rejected or duplicates"})
        await notify("critical_failure", "Batch failed", f"{batch['file_name']}: every row was rejected.", f"/batches/{batch_id}", batch_id=batch_id, severity="critical")
        return
    if counts["rejected"] and not partner.get("partial_ingestion", True):
        await set_status(batch_id, "Failed", by=by, reason="Partial ingestion disabled", extra={"failure_reason": f"{counts['rejected']} rows rejected and partner does not allow partial ingestion"})
        await notify("critical_failure", "Batch failed (strict partner)", f"{batch['file_name']} has rejected rows and {partner['name']} disallows partial ingestion.",
                     f"/batches/{batch_id}", batch_id=batch_id, severity="critical")
        return
    rows = await db.std_rows.find({"batch_id": batch_id, "is_current": True, "status": {"$in": ["accepted", "warning"]}}, {"_id": 0}).to_list(None)
    docs = [sales_doc(r, batch, partner) for r in rows]
    for i in range(0, len(docs), 2000):
        await db.sales.insert_many(docs[i:i + 2000])
    status = "Partially Processed" if (counts["rejected"] or counts["duplicate"]) else "Successfully Processed"
    await set_status(batch_id, status, by=by, extra={"processed_at": now_iso(), "loaded_rows": len(docs)})
    await log_audit(by, "batch.processed", "batch", batch_id, {"status": status, "loaded": len(docs)}, batch_id, "ingestion")
    await notify("processing_done", f"Batch {status.lower()}", f"{batch['file_name']}: {len(docs)} rows loaded, {counts['rejected']} rejected, {counts['duplicate']} duplicates.",
                 f"/batches/{batch_id}", batch_id=batch_id, roles=["admin", "ops", "management"], severity="success" if status == "Successfully Processed" else "warning")


def sales_doc(r, batch, partner):
    v, st, sk = r["values"], r.get("resolved_store") or {}, r.get("resolved_sku") or {}
    q, p = v.get("quantity") or 0, v.get("unit_price") or 0
    disc = v.get("discount") or 0
    return {"id": r["raw_row_id"], "std_row_id": r["id"], "batch_id": batch["id"], "partner_code": partner["code"], "partner_name": partner["name"],
            "store_code": st.get("code") or v.get("store_code"), "store_name": st.get("name") or v.get("store_name"), "city": st.get("city") or v.get("city"),
            "region": st.get("region") or v.get("region"), "sale_date": v.get("sale_date"), "month": (v.get("sale_date") or "")[:7],
            "sku": sk.get("code") or v.get("sku"), "article_name": sk.get("name") or v.get("article_name"), "category": sk.get("category") or v.get("category"),
            "brand": sk.get("brand"), "quantity": q, "mrp": v.get("mrp"), "unit_price": p, "gross_amount": round(q * p, 2), "discount": disc,
            "discount_pct": round(disc / (q * p) * 100, 2) if q * p else 0, "tax": v.get("tax") or 0, "net_amount": v.get("net_amount") or 0,
            "invoice_no": v.get("invoice_no"), "data_quality": r["status"], "business_key": r.get("business_key"), "row_version": r["version"],
            "created_at": now_iso()}


async def approve_restatement(batch_id, user):
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    prev_id = batch.get("restatement_of")
    if prev_id:
        prev = await db.batches.find_one({"id": prev_id}, {"_id": 0, "status": 1})
        await db.sales.delete_many({"batch_id": prev_id})
        await set_status(prev_id, "Superseded", by=user["username"], reason=f"Superseded by batch {batch_id[:8]}",
                         extra={"superseded_by": batch_id, "status_before_supersede": prev["status"]})
        await log_audit(user["username"], "batch.superseded", "batch", prev_id, {"superseded_by": batch_id}, prev_id, "ingestion")
    await db.batches.update_one({"id": batch_id}, {"$set": {"restatement_approved": True, "restatement_approved_by": user["username"], "review_reason": None}})
    await log_audit(user["username"], "restatement.approved", "batch", batch_id, {"supersedes": prev_id}, batch_id, "ingestion")
    await load_to_reporting(batch_id, user["username"])
    return await db.batches.find_one({"id": batch_id}, {"_id": 0})


async def reprocess_batch(batch_id, user):
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch or not batch.get("column_mappings"):
        raise ValueError("Batch cannot be reprocessed before analysis")
    await db.sales.delete_many({"batch_id": batch_id})
    await db.batches.update_one({"id": batch_id}, {"$set": {"reprocessed": True, "restatement_approved": batch.get("restatement_approved", False)},
                                                   "$inc": {"reprocess_count": 1}})
    await log_audit(user["username"], "batch.reprocess", "batch", batch_id, {}, batch_id, "ingestion")
    await set_status(batch_id, "Reprocessed", by=user["username"], reason="Reprocess requested")
    await set_status(batch_id, "Validating", by=user["username"])
    await validate_batch(batch_id, by=user["username"])
    return await db.batches.find_one({"id": batch_id}, {"_id": 0})


async def reject_batch(batch_id, user, reason):
    await db.sales.delete_many({"batch_id": batch_id})
    await db.exceptions.update_many({"batch_id": batch_id, "status": "open"}, {"$set": {"status": "rejected", "updated_at": now_iso()},
                                                                                "$push": {"history": {"action": "reject_file", "by": user["username"], "at": now_iso(), "note": reason}}})
    await set_status(batch_id, "Rejected", by=user["username"], reason=reason, extra={"rejection_reason": reason})
    await log_audit(user["username"], "batch.rejected", "batch", batch_id, {"reason": reason}, batch_id, "ingestion")
    return await db.batches.find_one({"id": batch_id}, {"_id": 0})


async def recount_batch(batch_id):
    pipe = [{"$match": {"batch_id": batch_id, "is_current": True}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    counts = {"total": 0, "accepted": 0, "warning": 0, "rejected": 0, "duplicate": 0}
    async for g in db.std_rows.aggregate(pipe):
        counts[g["_id"]] = g["n"]
        counts["total"] += g["n"]
    exc = await db.exceptions.count_documents({"batch_id": batch_id, "status": "open"})
    await db.batches.update_one({"id": batch_id}, {"$set": {"counts": counts, "open_exceptions": exc, "updated_at": now_iso()}})
    return counts


async def revise_row(std_row_id, new_values: dict, user, note: str, extra_alias=None):
    """Create a new version of a standardized row, revalidate it, sync reporting + exceptions. Never overwrites."""
    old = await db.std_rows.find_one({"id": std_row_id, "is_current": True}, {"_id": 0})
    if not old:
        raise ValueError("Row version not current")
    batch = await db.batches.find_one({"id": old["batch_id"]}, {"_id": 0})
    ctx = await build_context(batch)
    ctx.existing_keys.discard(old.get("business_key"))
    new = {**old, "id": new_id(), "version": old["version"] + 1, "values": {**old["values"], **new_values}, "created_at": now_iso(),
           "created_by": user["username"], "change_note": note, "previous_version_id": old["id"], "issues": [], "status": "accepted",
           "changes": [{"field": k, "from": old["values"].get(k), "to": v} for k, v in new_values.items()]}
    new.pop("resolved_store", None)
    new.pop("resolved_sku", None)
    validate_row(new, ctx)
    await db.std_rows.update_one({"id": old["id"]}, {"$set": {"is_current": False, "superseded_by": new["id"], "superseded_at": now_iso()}})
    await db.std_rows.insert_one(dict(new))
    new_codes = {i["rule_code"] for i in new["issues"]}
    open_exc = await db.exceptions.find({"raw_row_id": old["raw_row_id"], "status": "open"}, {"_id": 0}).to_list(None)
    for e in open_exc:
        if e["rule_code"] not in new_codes:
            await db.exceptions.update_one({"id": e["id"]}, {"$set": {"status": "resolved", "updated_at": now_iso(), "std_row_id": new["id"]},
                                                             "$push": {"history": {"action": "resolved", "by": user["username"], "at": now_iso(), "note": note}}})
        else:
            await db.exceptions.update_one({"id": e["id"]}, {"$set": {"std_row_id": new["id"], "updated_at": now_iso()}})
    existing_codes = {e["rule_code"] for e in open_exc}
    for i in new["issues"]:
        if i["rule_code"] not in existing_codes:
            await db.exceptions.insert_one(_exception_doc(batch, new, i))
    partner = await db.partners.find_one({"code": batch["partner_code"]}, {"_id": 0})
    if batch["status"] in PROCESSED and new["status"] in ("accepted", "warning"):
        await db.sales.replace_one({"id": new["raw_row_id"]}, sales_doc(new, batch, partner), upsert=True)
    else:
        await db.sales.delete_many({"id": new["raw_row_id"]})
    counts = await recount_batch(batch["id"])
    if batch["status"] in PROCESSED + ("Failed",):
        if counts["accepted"] + counts["warning"] > 0:
            status = "Partially Processed" if (counts["rejected"] or counts["duplicate"]) else "Successfully Processed"
            if status != batch["status"]:
                await set_status(batch["id"], status, by=user["username"], reason="Recomputed after correction")
    await log_audit(user["username"], "row.corrected", "std_row", new["id"], {"batch_id": batch["id"], "changes": new["changes"], "note": note,
                                                                             "new_status": new["status"]}, batch["id"], "correction")
    return new
