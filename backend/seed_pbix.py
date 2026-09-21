"""Loads the SIS Secondary Sales fact table (extracted from the Power BI 'SIS Secondary Dashboard 2026' model) into `sis_sales`.
Row-level finance components are pre-computed once so every report measure becomes a plain aggregation. Runs in the background; progress in `sis_meta`."""
import asyncio
import logging
import math
from pathlib import Path
import pandas as pd
from core.db import db
from core.utils import now_iso

logger = logging.getLogger("seed_pbix")
SRC = Path(__file__).resolve().parent.parent / "data" / "sis" / "pbix_sales_report.csv.gz"
STR_COLS = ["partner", "month", "store_code", "store_name", "art", "size", "cat_name", "article_name", "grpcat", "market", "till_date", "ltl", "cluster_manager", "top_stores", "existing_vs_new", "city", "state"]
_lock = asyncio.Lock()


def _gst_rate_nsv(unit):
    return 0.05 if unit <= 2500 else 0.18


def _f(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def enrich(r: dict):
    qty, nsv = r["qty"] or 0.0, r["nsv"] or 0.0
    mrp, cost, margin = r.get("mrp") or 0.0, r.get("stdcost") or 0.0, r.get("margin") or 0.0
    unit = nsv / qty if qty else 0.0
    r["mrp_val"] = mrp * qty
    r["cost_val"] = cost * qty
    r["gst_val"] = nsv - nsv / (1 + _gst_rate_nsv(unit))
    gst_on_mrp = (mrp - mrp / (1.05 if mrp < 2500 else 1.18)) * qty
    gst_on_nsv = nsv - nsv / (1.05 if unit < 2500 else 1.18)
    r["gst_reversal"] = gst_on_mrp - gst_on_nsv
    r["margin_val"] = mrp * margin * qty
    r["margin_nsv"] = margin * nsv
    r["panel_w"] = 1.4 if r.get("grpcat") == "HP MEN" else 1.0
    r["ltl_nsv"] = nsv if r.get("ltl") == "LTL" else 0.0
    r["ltl_qty"] = qty if r.get("ltl") == "LTL" else 0.0
    return r


async def _status(**kw):
    await db.sis_meta.update_one({"key": "sis_sales"}, {"$set": {"key": "sis_sales", "updated_at": now_iso(), **kw}}, upsert=True)


async def get_status():
    m = await db.sis_meta.find_one({"key": "sis_sales"}, {"_id": 0}) or {"key": "sis_sales", "status": "empty"}
    m["rows"] = await db.sis_sales.estimated_document_count()
    return m


async def seed_pbix(force=False):
    """Idempotent loader. Chunked CSV read keeps memory low; safe to call at startup or from the reload endpoint."""
    if _lock.locked():
        return
    async with _lock:
        if not SRC.exists():
            logger.warning("pbix sales file missing: %s", SRC)
            await _status(status="failed", error=f"source file missing: {SRC.name}")
            return
        if not force and await db.sis_sales.estimated_document_count() > 0:
            return
        logger.info("Loading SIS secondary sales from %s", SRC)
        await _status(status="loading", loaded_rows=0, error=None)
        try:
            await db.sis_sales.delete_many({})
            now, n = now_iso(), 0
            for chunk in pd.read_csv(SRC, dtype={c: str for c in STR_COLS}, low_memory=False, chunksize=10000):
                docs = []
                for rec in chunk.to_dict("records"):
                    r = {k: (v.strip() if isinstance(v, str) else (None if isinstance(v, float) and math.isnan(v) else v)) for k, v in rec.items()}
                    for k in ("qty", "nsv", "mrp", "stdcost", "margin", "sec_prim", "target"):
                        r[k] = _f(r.get(k))
                    r["week"], r["year"], r["bmonth"] = int(r["week"]), int(r["year"]), int(r["bmonth"])
                    r["has_sale"] = (r["nsv"] or 0) > 0
                    r["created_at"] = now
                    docs.append(enrich(r))
                await db.sis_sales.insert_many(docs, ordered=False)
                n += len(docs)
                await _status(status="loading", loaded_rows=n)
                await asyncio.sleep(0)
            for idx in (["year", "week"], ["partner"], ["cluster_manager"], ["store_code"], ["market"], ["grpcat"], ["till_date"], ["ltl"], ["state"], ["bmonth"]):
                await db.sis_sales.create_index([(k, 1) for k in idx])
            await refresh_meta()
            await _status(status="ready", loaded_rows=n, error=None)
            logger.info("sis_sales loaded: %d rows", n)
        except Exception as e:
            logger.exception("sis_sales load failed")
            await _status(status="failed", error=str(e)[:300])


async def refresh_meta():
    """Latest week / month = max period that has sales in BOTH years (TILL DATE = Yes), matching the Power BI calculated columns."""
    agg = [g async for g in db.sis_sales.aggregate([{"$match": {"till_date": "Yes"}}, {"$group": {"_id": None, "wk": {"$max": "$week"}, "bm": {"$max": "$bmonth"}}}])]
    meta = {"latest_week": agg[0]["wk"] if agg else None, "latest_bmonth": agg[0]["bm"] if agg else None}
    if meta["latest_bmonth"]:
        m = await db.sis_sales.find_one({"bmonth": meta["latest_bmonth"]}, {"_id": 0, "month": 1})
        meta["latest_month"] = m["month"] if m else None
    meta["years"] = sorted(await db.sis_sales.distinct("year"))
    meta["rows"] = await db.sis_sales.count_documents({})
    await _status(**meta)
    return await get_status()
