"""SIS Secondary Sales report — replica of the Power BI 'SIS DASHBOARD 2026 / SALES' matrix with dynamic hierarchy, slicers, paging and all DAX measures."""
import io
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import pandas as pd
from core.db import db
from core.auth import get_current_user
from core.audit import log_audit

router = APIRouter(prefix="/sis")

HIER = {"market": "Market", "partner": "Partner", "cluster_manager": "Cluster Manager", "state": "State", "store_code": "Store Code", "store_name": "Store Name", "city": "City",
        "grpcat": "GRPCAT", "cat_name": "Category", "article_name": "Article", "existing_vs_new": "Existing vs New", "top_stores": "Top Stores", "month": "Month", "week": "Week", "ltl": "LTL Status"}
FILTERS = ["partner", "cluster_manager", "market", "store_name", "store_code", "state", "city", "grpcat", "cat_name", "month", "week", "ltl", "top_stores", "existing_vs_new", "till_date"]
SUMS = ["nsv", "qty", "mrp_val", "cost_val", "gst_val", "gst_reversal", "margin_val", "margin_nsv", "sec_prim", "ltl_nsv", "ltl_qty"]

MEASURES = [
    ("cont_pct", "CONT %", "pct", "sales"), ("str_25", "#STR-25", "int", "sales"), ("str_26", "#STR-26", "int", "sales"), ("panel_25", "#PANEL-25", "num1", "sales"), ("panel_26", "#PANEL-26", "num1", "sales"),
    ("nsv_25", "NSV-25", "money", "sales"), ("nsv_26", "NSV-26", "money", "sales"), ("nsv_g", "NSV G", "growth", "sales"), ("ltl_g", "LTL G", "growth", "sales"),
    ("est", "EST (Target)", "money", "sales"), ("est_g", "EST G", "growth", "sales"), ("prod_wk_25", "PROD/WK-25", "money", "sales"), ("prod_wk_26", "PROD/WK-26", "money", "sales"),
    ("qty_25", "QTY-25", "int", "sales"), ("qty_26", "QTY-26", "int", "sales"), ("qty_g", "QTY G", "growth", "sales"), ("asp_25", "ASP-25", "money", "sales"), ("asp_26", "ASP-26", "money", "sales"),
    ("mrp_val_26", "MRP VAL-26", "money", "finance"), ("disc_26", "DISC-26", "money", "finance"), ("disc_pct_26", "DISC%-26", "pct", "finance"), ("gst_val_26", "GST VAL-26", "money", "finance"),
    ("margin_val_26", "MARGIN VAL-26", "money", "finance"), ("prim_billing_26", "PRIM BILLING-26", "money", "finance"), ("gst_reversal_26", "GST REVERSAL-26", "money", "finance"),
    ("margin_reversal_26", "MARGIN REVERSAL-26", "money", "finance"), ("realized_26", "REALIZED VALUE-26", "money", "finance"), ("cost_val_26", "COST VAL-26", "money", "finance"), ("margin_pct_26", "MARGIN%-26", "pct", "finance"),
    ("mrp_val_25", "MRP VAL-25", "money", "finance"), ("disc_25", "DISC-25", "money", "finance"), ("disc_pct_25", "DISC%-25", "pct", "finance"), ("prim_billing_25", "PRIM BILLING-25", "money", "finance"),
    ("realized_25", "REALIZED VALUE-25", "money", "finance"), ("margin_pct_25", "MARGIN%-25", "pct", "finance"), ("prim_billing_g", "PRIM BILLING G", "growth", "finance"), ("to_g", "TO G", "growth", "finance"),
]


def _list(v):
    return [x for x in (v or "").split(",") if x != ""]


async def meta():
    m = await db.sis_meta.find_one({"key": "sis_sales"}, {"_id": 0})
    if not m:
        from seed_pbix import refresh_meta
        m = await refresh_meta()
    return m


async def build_match(p: dict):
    q = {}
    for k in FILTERS:
        vals = _list(p.get(k))
        if vals:
            q[k] = {"$in": [int(v) for v in vals] if k == "week" else vals}
    m = await meta()
    if p.get("latest_wk") in ("1", "true", "Yes") and m.get("latest_week"):
        q["week"] = m["latest_week"]
    if p.get("latest_month") in ("1", "true", "Yes") and m.get("latest_bmonth"):
        q["bmonth"] = m["latest_bmonth"]
    if p.get("week_from") or p.get("week_to"):
        q["week"] = {**({"$gte": int(p["week_from"])} if p.get("week_from") else {}), **({"$lte": int(p["week_to"])} if p.get("week_to") else {})}
    if p.get("search"):
        q["$or"] = [{k: {"$regex": p["search"], "$options": "i"}} for k in ("store_name", "store_code", "article_name", "cluster_manager", "city")]
    return q


def _div(a, b):
    return round(a / b, 4) if b else None


def measures_from(y: dict, total_nsv26=None):
    a, b = y.get(2025, {}), y.get(2026, {})
    g = lambda d, k: d.get(k) or 0.0
    to25 = g(a, "nsv") - g(a, "gst_val") + g(a, "gst_reversal")
    to26 = g(b, "nsv") - g(b, "gst_val") + g(b, "gst_reversal")
    disc25, disc26 = g(a, "mrp_val") - to25, g(b, "mrp_val") - to26
    prim25 = g(a, "sec_prim")
    prim26 = g(b, "mrp_val") - g(b, "gst_val") - g(b, "margin_val")
    mrev25, mrev26 = g(a, "margin_val") - g(a, "margin_nsv"), g(b, "margin_val") - g(b, "margin_nsv")
    real25 = prim25 - disc25 + g(a, "gst_reversal") + mrev25
    real26 = prim26 - disc26 + g(b, "gst_reversal") + mrev26
    est = g(b, "target")
    r = {"str_25": a.get("stores_pos", 0), "str_26": b.get("stores_pos", 0), "panel_25": round(g(a, "panel"), 1), "panel_26": round(g(b, "panel"), 1),
         "nsv_25": round(g(a, "nsv"), 2), "nsv_26": round(g(b, "nsv"), 2), "nsv_g": _div(g(b, "nsv") - g(a, "nsv"), g(a, "nsv")), "ltl_g": _div(g(b, "ltl_nsv") - g(a, "ltl_nsv"), g(a, "ltl_nsv")),
         "est": round(est, 2), "est_g": (round(g(b, "nsv") / est - 1, 4) if est else None),
         "prod_wk_25": _div(_div(g(a, "nsv"), a.get("stores_all", 0)) or 0, a.get("weeks_n", 0)), "prod_wk_26": _div(_div(g(b, "nsv"), b.get("stores_all", 0)) or 0, b.get("weeks_n", 0)),
         "qty_25": int(g(a, "qty")), "qty_26": int(g(b, "qty")), "qty_g": _div(g(b, "qty") - g(a, "qty"), g(a, "qty")), "asp_25": _div(g(a, "nsv"), g(a, "qty")), "asp_26": _div(g(b, "nsv"), g(b, "qty")),
         "mrp_val_26": round(g(b, "mrp_val"), 2), "disc_26": round(disc26, 2), "disc_pct_26": _div(disc26, g(b, "mrp_val")), "gst_val_26": round(g(b, "gst_val"), 2), "margin_val_26": round(g(b, "margin_val"), 2),
         "prim_billing_26": round(prim26, 2), "gst_reversal_26": round(g(b, "gst_reversal"), 2), "margin_reversal_26": round(mrev26, 2), "realized_26": round(real26, 2), "cost_val_26": round(g(b, "cost_val"), 2),
         "margin_pct_26": _div(real26 - g(b, "cost_val"), real26), "mrp_val_25": round(g(a, "mrp_val"), 2), "disc_25": round(disc25, 2), "disc_pct_25": _div(disc25, g(a, "mrp_val")), "prim_billing_25": round(prim25, 2),
         "realized_25": round(real25, 2), "margin_pct_25": _div(real25 - g(a, "cost_val"), real25), "prim_billing_g": _div(prim26 - prim25, prim25), "to_g": _div(to26 - to25, to25),
         "cont_pct": _div(g(b, "nsv"), total_nsv26) if total_nsv26 else None}
    for k in ("prod_wk_25", "prod_wk_26", "asp_25", "asp_26"):
        if r[k] is not None:
            r[k] = round(r[k], 2)
    return r


async def aggregate(match: dict, dims: list):
    did = {d: f"${d}" for d in dims}
    if "month" in dims:
        did["bmonth"] = "$bmonth"
    sums = lambda src: {k: {"$sum": f"${src}{k}"} for k in SUMS}
    pipe = [{"$match": match},
            {"$group": {"_id": {**did, "year": "$year", "store": "$store_code", "week": "$week", "grpcat": "$grpcat"}, **sums(""), "target": {"$max": "$target"}, "panel_w": {"$max": "$panel_w"}}},
            {"$group": {"_id": {**{k: f"$_id.{k}" for k in did}, "year": "$_id.year", "store": "$_id.store", "week": "$_id.week"}, **sums(""), "target": {"$max": "$target"},
                        "gset": {"$addToSet": {"$cond": [{"$gt": ["$nsv", 0]}, {"g": "$_id.grpcat", "w": "$panel_w"}, None]}}}},
            {"$group": {"_id": {**{k: f"$_id.{k}" for k in did}, "year": "$_id.year", "store": "$_id.store"}, **sums(""), "target": {"$sum": "$target"}, "weeks": {"$addToSet": "$_id.week"}, "gsets": {"$push": "$gset"}}},
            {"$addFields": {"gset": {"$filter": {"input": {"$reduce": {"input": "$gsets", "initialValue": [], "in": {"$setUnion": ["$$value", "$$this"]}}}, "as": "x", "cond": {"$ne": ["$$x", None]}}}}},
            {"$addFields": {"panel": {"$cond": [{"$gt": ["$nsv", 0]}, {"$sum": "$gset.w"}, 0]}, "pos": {"$cond": [{"$gt": ["$nsv", 0]}, 1, 0]}}},
            {"$group": {"_id": {**{k: f"$_id.{k}" for k in did}, "year": "$_id.year"}, **sums(""), "target": {"$sum": "$target"}, "panel": {"$sum": "$panel"}, "stores_pos": {"$sum": "$pos"}, "stores_all": {"$sum": 1},
                        "weeks": {"$push": "$weeks"}}},
            {"$addFields": {"weeks_n": {"$size": {"$reduce": {"input": "$weeks", "initialValue": [], "in": {"$setUnion": ["$$value", "$$this"]}}}}}},
            {"$project": {"weeks": 0}}]
    groups = {}
    async for g in db.sis_sales.aggregate(pipe, allowDiskUse=True):
        key = tuple(g["_id"].get(k) for k in did)
        groups.setdefault(key, {})[g["_id"]["year"]] = g
    return list(did), groups


@router.get("/meta")
async def sis_meta(user=Depends(get_current_user)):
    m = await meta()
    return {**m, "hierarchy": [{"key": k, "label": v} for k, v in HIER.items()], "measures": [{"key": k, "label": l, "type": t, "group": grp} for k, l, t, grp in MEASURES]}


@router.get("/filters")
async def sis_filters(request: Request, user=Depends(get_current_user)):
    """Cascading slicer values: each field's options respect the other active filters."""
    p = dict(request.query_params)
    out = {}
    for k in FILTERS:
        q = await build_match({kk: v for kk, v in p.items() if kk != k})
        vals = await db.sis_sales.distinct(k, q)
        out[k] = sorted([v for v in vals if v is not None], key=(lambda x: x) if k != "month" else None)
    months = [g async for g in db.sis_sales.aggregate([{"$group": {"_id": {"m": "$month", "b": "$bmonth"}}}, {"$sort": {"_id.b": 1}}])]
    out["month"] = [m["_id"]["m"] for m in months if m["_id"]["m"] in out["month"]]
    out["week"] = sorted(out["week"])
    return out


async def run_sales_report(p: dict):
    dims = [d for d in _list(p.get("group_by")) if d in HIER] or ["cluster_manager"]
    match = await build_match(p)
    did, groups = await aggregate(match, dims)
    _, tot = await aggregate(match, [])
    total = measures_from(tot.get((), {}))
    total_nsv26 = total["nsv_26"]
    rows = []
    for key, y in groups.items():
        r = dict(zip(did, key))
        r.update(measures_from(y, total_nsv26))
        rows.append(r)
    sort_by = p.get("sort_by") or ("bmonth" if "month" in dims else "week" if dims == ["week"] else "nsv_26")
    desc = (p.get("sort_dir") or ("asc" if sort_by in ("bmonth", "week") else "desc")) == "desc"
    rows.sort(key=lambda r: ((r.get(sort_by) is None), r.get(sort_by) if r.get(sort_by) is not None else 0), reverse=desc)
    total["cont_pct"] = 1.0 if total_nsv26 else None
    return dims, rows, total, match


@router.get("/sales-report")
async def sales_report(request: Request, page: int = 1, page_size: int = 50, user=Depends(get_current_user)):
    p = dict(request.query_params)
    dims, rows, total, match = await run_sales_report(p)
    page_size = max(1, min(page_size, 500))
    start = (max(1, page) - 1) * page_size
    m = await meta()
    return {"dims": [{"key": d, "label": HIER[d]} for d in dims], "columns": [{"key": k, "label": l, "type": t, "group": grp} for k, l, t, grp in MEASURES],
            "rows": rows[start:start + page_size], "total": total, "count": len(rows), "page": page, "page_size": page_size, "pages": (len(rows) + page_size - 1) // page_size,
            "meta": {"latest_week": m.get("latest_week"), "latest_month": m.get("latest_month"), "years": m.get("years"), "rows_in_scope": await db.sis_sales.count_documents(match)}}


@router.get("/sales-report/export")
async def sales_export(request: Request, fmt: str = "xlsx", user=Depends(get_current_user)):
    p = dict(request.query_params)
    dims, rows, total, _ = await run_sales_report(p)
    cols = _list(p.get("columns")) or [k for k, *_ in MEASURES]
    labels = {k: l for k, l, *_ in MEASURES}
    data = [{**{HIER[d]: r.get(d) for d in dims}, **{labels[c]: r.get(c) for c in cols if c in labels}} for r in rows]
    data.append({**{HIER[d]: ("Total" if i == 0 else None) for i, d in enumerate(dims)}, **{labels[c]: total.get(c) for c in cols if c in labels}})
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    if fmt == "xlsx":
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="SIS Sales")
        media, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        buf.write(df.to_csv(index=False).encode("utf-8-sig"))
        media, ext = "text/csv", "csv"
    buf.seek(0)
    await log_audit(user["username"], "report.exported", "report", "sis_sales", {"rows": len(rows), "fmt": fmt, "filters": p}, category="reports")
    return StreamingResponse(buf, media_type=media, headers={"Content-Disposition": f'attachment; filename="sis_sales_report.{ext}"'})


@router.post("/reload")
async def reload(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator only")
    from seed_pbix import seed_pbix
    await seed_pbix(force=True)
    return await meta()
