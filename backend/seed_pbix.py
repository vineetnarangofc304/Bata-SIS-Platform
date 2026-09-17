"""Loads the SIS Secondary Sales fact table (extracted from the Power BI 'SIS Secondary Dashboard 2026' model) into `sis_sales`.
Row-level finance components are pre-computed once so every report measure becomes a plain aggregation."""
import logging
import math
from pathlib import Path
import pandas as pd
from core.db import db
from core.utils import now_iso

logger = logging.getLogger("seed_pbix")
SRC = Path(__file__).resolve().parent.parent / "data" / "sis" / "pbix_sales_report.csv.gz"
STR_COLS = ["partner", "month", "store_code", "store_name", "art", "size", "cat_name", "article_name", "grpcat", "market", "till_date", "ltl", "cluster_manager", "top_stores", "existing_vs_new", "city", "state"]


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


async def seed_pbix(force=False):
    if not SRC.exists():
        logger.warning("pbix sales file missing: %s", SRC)
        return
    if not force and await db.sis_sales.estimated_document_count() > 0:
        return
    logger.info("Loading SIS secondary sales from %s", SRC)
    df = pd.read_csv(SRC, dtype={c: str for c in STR_COLS}, low_memory=False)
    df = df.where(pd.notnull(df), None)
    await db.sis_sales.delete_many({})
    now = now_iso()
    docs, n = [], 0
    for rec in df.to_dict("records"):
        r = {k: (v.strip() if isinstance(v, str) else (None if isinstance(v, float) and math.isnan(v) else v)) for k, v in rec.items()}
        for k in ("qty", "nsv", "mrp", "stdcost", "margin", "sec_prim", "target"):
            r[k] = _f(r.get(k))
        r["week"], r["year"], r["bmonth"] = int(r["week"]), int(r["year"]), int(r["bmonth"])
        r["has_sale"] = (r["nsv"] or 0) > 0
        r["created_at"] = now
        docs.append(enrich(r))
        if len(docs) >= 5000:
            await db.sis_sales.insert_many(docs)
            n += len(docs)
            docs = []
    if docs:
        await db.sis_sales.insert_many(docs)
        n += len(docs)
    for idx in (["year", "week"], ["partner"], ["cluster_manager"], ["store_code"], ["market"], ["grpcat"], ["till_date"], ["ltl"], ["state"], ["bmonth"]):
        await db.sis_sales.create_index([(k, 1) for k in idx])
    await refresh_meta()
    logger.info("sis_sales loaded: %d rows", n)


async def refresh_meta():
    """Latest week / month = max period that has sales in BOTH years (TILL DATE = Yes), matching the Power BI calculated columns."""
    agg = [g async for g in db.sis_sales.aggregate([{"$match": {"till_date": "Yes"}}, {"$group": {"_id": None, "wk": {"$max": "$week"}, "bm": {"$max": "$bmonth"}}}])]
    meta = {"key": "sis_sales", "latest_week": agg[0]["wk"] if agg else None, "latest_bmonth": agg[0]["bm"] if agg else None, "updated_at": now_iso()}
    if meta["latest_bmonth"]:
        m = await db.sis_sales.find_one({"bmonth": meta["latest_bmonth"]}, {"_id": 0, "month": 1})
        meta["latest_month"] = m["month"] if m else None
    yrs = await db.sis_sales.distinct("year")
    meta["years"] = sorted(yrs)
    meta["rows"] = await db.sis_sales.count_documents({})
    await db.sis_meta.update_one({"key": "sis_sales"}, {"$set": meta}, upsert=True)
    return meta
