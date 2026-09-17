import io
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import pandas as pd
from core.db import db
from core.auth import get_current_user
from core.utils import now_iso, new_id, paginate
from core.audit import log_audit
from services.insights import compute_insights

router = APIRouter()


def _d(days, base=None):
    return ((base or datetime.now(timezone.utc)) - timedelta(days=days)).strftime("%Y-%m-%d")


async def ref_dt():
    """Latest sale date in reporting data — dashboards are 'as of' the data, not the wall clock."""
    last = await db.sales.find_one({"sale_date": {"$ne": None}}, {"_id": 0, "sale_date": 1}, sort=[("sale_date", -1)])
    if not last:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(last["sale_date"]).replace(tzinfo=timezone.utc)


def sales_match(p: dict):
    q = {}
    if p.get("date_from") or p.get("date_to"):
        q["sale_date"] = {}
        if p.get("date_from"):
            q["sale_date"]["$gte"] = p["date_from"]
        if p.get("date_to"):
            q["sale_date"]["$lte"] = p["date_to"]
    for k in ("partner_code", "store_code", "region", "category", "sku", "brand", "city", "batch_id", "data_quality"):
        if p.get(k):
            q[k] = p[k]
    if p.get("min_discount_pct"):
        q["discount_pct"] = {"$gt": float(p["min_discount_pct"])}
    if p.get("search"):
        q["$or"] = [{k: {"$regex": p["search"], "$options": "i"}} for k in ("sku", "article_name", "store_name", "invoice_no")]
    return q


SUM = {"quantity": {"$sum": "$quantity"}, "gross_amount": {"$sum": "$gross_amount"}, "discount": {"$sum": "$discount"}, "tax": {"$sum": "$tax"},
       "net_amount": {"$sum": "$net_amount"}, "transactions": {"$sum": 1}}
NUM = [("quantity", "Qty", "int"), ("gross_amount", "Gross (₹)", "money"), ("discount", "Discount (₹)", "money"), ("net_amount", "Net Sales (₹)", "money"), ("transactions", "Txns", "int")]

REPORTS = {
    "daily_sales": {"name": "Daily Sales Trend", "group": {"sale_date": "$sale_date"}, "dims": [("sale_date", "Date", "date")], "sort": ("sale_date", 1)},
    "monthly_sales": {"name": "Monthly Sales Summary", "group": {"month": "$month"}, "dims": [("month", "Month", "string")], "sort": ("month", 1)},
    "partner_performance": {"name": "Partner Performance", "group": {"partner_code": "$partner_code", "partner_name": "$partner_name"}, "dims": [("partner_code", "Code", "string"), ("partner_name", "Partner", "string")], "sort": ("net_amount", -1)},
    "store_performance": {"name": "Store / SIS Performance", "group": {"partner_name": "$partner_name", "store_code": "$store_code", "store_name": "$store_name", "city": "$city", "region": "$region"}, "dims": [("partner_name", "Partner", "string"), ("store_code", "Store", "string"), ("store_name", "Store Name", "string"), ("city", "City", "string"), ("region", "Region", "string")], "sort": ("net_amount", -1)},
    "region_performance": {"name": "Region Performance", "group": {"region": "$region"}, "dims": [("region", "Region", "string")], "sort": ("net_amount", -1)},
    "category_performance": {"name": "Category Performance", "group": {"category": "$category", "brand": "$brand"}, "dims": [("category", "Category", "string"), ("brand", "Brand", "string")], "sort": ("net_amount", -1)},
    "sku_performance": {"name": "SKU / Article Performance", "group": {"sku": "$sku", "article_name": "$article_name", "category": "$category"}, "dims": [("sku", "Article", "string"), ("article_name", "Article Name", "string"), ("category", "Category", "string")], "sort": ("net_amount", -1)},
    "top_bottom": {"name": "Top / Bottom Articles", "group": {"sku": "$sku", "article_name": "$article_name"}, "dims": [("sku", "Article", "string"), ("article_name", "Article Name", "string")], "sort": ("net_amount", -1), "top_bottom": True},
    "discount_analysis": {"name": "Discount Analysis", "group": {"partner_name": "$partner_name", "month": "$month"}, "dims": [("partner_name", "Partner", "string"), ("month", "Month", "string")], "sort": ("month", 1), "discount_pct": True},
    "data_quality_trend": {"name": "Data Quality Trend", "special": "dq"},
    "missing_submissions": {"name": "Missing Submission Calendar", "special": "missing"},
    "exception_summary": {"name": "Exception Summary", "special": "exceptions"},
    "target_vs_actual": {"name": "Target vs Actual (Q2 targets)", "special": "targets"},
    "stock_position": {"name": "Stock Position (Week 32)", "special": "stock"},
    "partner_margin": {"name": "Partner Margin Contribution", "special": "margin"},
}


@router.get("/reports")
async def list_reports(user=Depends(get_current_user)):
    return [{"key": k, "name": v["name"]} for k, v in REPORTS.items()]


async def run_report(key, params):
    key_ = key
    spec = REPORTS.get(key)
    if not spec:
        raise HTTPException(status_code=404, detail="Unknown report")
    if spec.get("special") == "dq":
        pipe = [{"$match": {"status": {"$nin": ["Rejected"]}, "counts.total": {"$gt": 0}, **({"partner_code": params["partner_code"]} if params.get("partner_code") else {})}},
                {"$group": {"_id": {"$substr": ["$created_at", 0, 10]}, "batches": {"$sum": 1}, "total": {"$sum": "$counts.total"}, "accepted": {"$sum": "$counts.accepted"},
                            "warning": {"$sum": "$counts.warning"}, "rejected": {"$sum": "$counts.rejected"}, "duplicate": {"$sum": "$counts.duplicate"}}}, {"$sort": {"_id": 1}}]
        rows = []
        async for g in db.batches.aggregate(pipe):
            t = g["total"] or 1
            rows.append({"date": g["_id"], "batches": g["batches"], "total": g["total"], "accepted": g["accepted"], "warning": g["warning"], "rejected": g["rejected"],
                         "duplicate": g["duplicate"], "acceptance_pct": round((g["accepted"] + g["warning"]) / t * 100, 1)})
        cols = [("date", "Date", "date"), ("batches", "Batches", "int"), ("total", "Rows", "int"), ("accepted", "Accepted", "int"), ("warning", "Warnings", "int"),
                ("rejected", "Rejected", "int"), ("duplicate", "Duplicates", "int"), ("acceptance_pct", "Acceptance %", "pct")]
        return {"key": key, "name": spec["name"], "columns": [{"key": c[0], "label": c[1], "type": c[2]} for c in cols], "rows": rows}
    if spec.get("special") == "missing":
        days = int(params.get("days") or 14)
        dates = [_d(i) for i in range(days - 1, -1, -1)]
        partners = await db.partners.find({"active": True}, {"_id": 0, "code": 1, "name": 1, "expected_frequency": 1}).to_list(50)
        got = {}
        async for g in db.batches.aggregate([{"$match": {"status": {"$nin": ["Rejected"]}, "created_at": {"$gte": dates[0]}}},
                                             {"$group": {"_id": {"p": "$partner_code", "d": {"$substr": ["$created_at", 0, 10]}}, "n": {"$sum": 1}}}]):
            got[(g["_id"]["p"], g["_id"]["d"])] = g["n"]
        rows = []
        for p in partners:
            r = {"partner_code": p["code"], "partner_name": p["name"], "frequency": p.get("expected_frequency", "daily")}
            miss = 0
            for d in dates:
                n = got.get((p["code"], d), 0)
                r[d] = n
                miss += 0 if n else 1
            r["missing_days"] = miss
            rows.append(r)
        cols = [("partner_name", "Partner", "string"), ("frequency", "Expected", "string"), ("missing_days", "Missing", "int")] + [(d, d[5:], "calendar") for d in dates]
        return {"key": key, "name": spec["name"], "columns": [{"key": c[0], "label": c[1], "type": c[2]} for c in cols], "rows": rows}
    if spec.get("special") == "exceptions":
        m = {}
        if params.get("partner_code"):
            m["partner_code"] = params["partner_code"]
        if params.get("date_from"):
            m["created_at"] = {"$gte": params["date_from"]}
        pipe = [{"$match": m}, {"$group": {"_id": {"p": "$partner_name", "r": "$rule_code", "s": "$severity"}, "total": {"$sum": 1},
                                           "open": {"$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}},
                                           "resolved": {"$sum": {"$cond": [{"$in": ["$status", ["accepted", "corrected", "resolved"]]}, 1, 0]}},
                                           "ignored": {"$sum": {"$cond": [{"$eq": ["$status", "ignored"]}, 1, 0]}},
                                           "rejected": {"$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}}}}, {"$sort": {"total": -1}}]
        rows = [{"partner_name": g["_id"]["p"], "rule_code": g["_id"]["r"], "severity": g["_id"]["s"], **{k: g[k] for k in ("total", "open", "resolved", "ignored", "rejected")}} async for g in db.exceptions.aggregate(pipe)]
        cols = [("partner_name", "Partner", "string"), ("rule_code", "Rule", "string"), ("severity", "Severity", "string"), ("total", "Total", "int"), ("open", "Open", "int"), ("resolved", "Resolved", "int"), ("ignored", "Ignored", "int"), ("rejected", "Rejected", "int")]
        return {"key": key, "name": spec["name"], "columns": [{"key": c[0], "label": c[1], "type": c[2]} for c in cols], "rows": rows}
    if spec.get("special") == "targets":
        pm = {"partner_code": params["partner_code"]} if params.get("partner_code") else {}
        week = int(params.get("week") or 32)
        tg = {(g["_id"]["p"], g["_id"]["n"]): g async for g in db.targets.aggregate([{"$match": {"week": week, **pm}}, {"$group": {"_id": {"p": "$partner_code", "n": "$partner_name"}, "target": {"$sum": "$target"}, "stores": {"$addToSet": "$store_code"}}}])}
        ac = {g["_id"]: g async for g in db.sales.aggregate([{"$match": {"year": 2026, "week": week, **pm}}, {"$group": {"_id": "$partner_code", "net": {"$sum": "$net_amount"}, "qty": {"$sum": "$quantity"}, "stores": {"$addToSet": "$store_code"}}}])}
        rows = []
        for (pc, pn), g in tg.items():
            a = ac.get(pc, {"net": 0, "qty": 0, "stores": []})
            rows.append({"partner_code": pc, "partner_name": pn, "week": week, "target": round(g["target"], 2), "actual": round(a["net"], 2), "achievement_pct": round(a["net"] / g["target"] * 100, 1) if g["target"] else 0,
                         "gap": round(a["net"] - g["target"], 2), "target_stores": len(g["stores"]), "reporting_stores": len(a["stores"]), "quantity": a["qty"]})
        rows.sort(key=lambda r: -r["achievement_pct"])
        cols = [("partner_name", "Partner", "string"), ("week", "Week", "int"), ("target_stores", "Target stores", "int"), ("reporting_stores", "Stores reported", "int"), ("target", "Target (₹)", "money"), ("actual", "Actual NSV (₹)", "money"), ("gap", "Gap (₹)", "money"), ("achievement_pct", "Achievement %", "pct"), ("quantity", "Pairs", "int")]
        return {"key": key_, "name": spec["name"], "columns": [{"key": c[0], "label": c[1], "type": c[2]} for c in cols], "rows": rows}
    if spec.get("special") == "stock":
        m = {k: params[k] for k in ("partner_code", "store_code", "region") if params.get(k)}
        rows = [{"partner_name": g["_id"]["p"], "store_code": g["_id"]["s"], "store_name": g["_id"]["n"], "region": g["_id"]["r"], "articles": len(g["arts"]), "stock_qty": g["qty"]} async for g in db.stock.aggregate([{"$match": m}, {"$group": {"_id": {"p": "$partner_name", "s": "$store_code", "n": "$store_name", "r": "$region"}, "qty": {"$sum": "$quantity"}, "arts": {"$addToSet": "$sku"}}}, {"$sort": {"qty": -1}}])]
        sold = {(g["_id"]["p"], g["_id"]["s"]): g["q"] async for g in db.sales.aggregate([{"$match": {"year": 2026, "week": 32}}, {"$group": {"_id": {"p": "$partner_name", "s": "$store_code"}, "q": {"$sum": "$quantity"}}}])}
        for r in rows:
            r["sold_wk32"] = sold.get((r["partner_name"], r["store_code"]), 0)
            r["weeks_cover"] = round(r["stock_qty"] / r["sold_wk32"], 1) if r["sold_wk32"] else None
        cols = [("partner_name", "Partner", "string"), ("store_code", "Store", "string"), ("store_name", "Store Name", "string"), ("region", "Region", "string"), ("articles", "Articles", "int"), ("stock_qty", "Stock (pairs)", "int"), ("sold_wk32", "Sold Wk32", "int"), ("weeks_cover", "Weeks cover", "int")]
        return {"key": key_, "name": spec["name"], "columns": [{"key": c[0], "label": c[1], "type": c[2]} for c in cols], "rows": rows}
    if spec.get("special") == "margin":
        mg = {(m["partner_code"], m["market"]): m["margin"] async for m in db.margins.find({}, {"_id": 0})}
        rows = []
        async for g in db.sales.aggregate([{"$match": sales_match(params)}, {"$group": {"_id": {"p": "$partner_code", "n": "$partner_name", "hp": {"$regexMatch": {"input": {"$ifNull": ["$brand", ""]}, "regex": "hush", "options": "i"}}}, "net": {"$sum": "$net_amount"}, "qty": {"$sum": "$quantity"}}}]):
            market = "HP" if g["_id"]["hp"] else "BATA"
            m = mg.get((g["_id"]["p"], market))
            rows.append({"partner_name": g["_id"]["n"], "market": market, "net_amount": round(g["net"], 2), "quantity": g["qty"], "margin_pct": round((m or 0) * 100, 1) if m is not None else None, "partner_margin": round(g["net"] * m, 2) if m is not None else None, "bata_net": round(g["net"] * (1 - m), 2) if m is not None else None})
        rows.sort(key=lambda r: -r["net_amount"])
        cols = [("partner_name", "Partner", "string"), ("market", "Market", "string"), ("net_amount", "NSV (₹)", "money"), ("quantity", "Pairs", "int"), ("margin_pct", "Margin %", "pct"), ("partner_margin", "Partner margin (₹)", "money"), ("bata_net", "Bata net (₹)", "money")]
        return {"key": key_, "name": spec["name"], "columns": [{"key": c[0], "label": c[1], "type": c[2]} for c in cols], "rows": rows}
    match = sales_match(params)
    pipe = [{"$match": match}, {"$group": {"_id": spec["group"], **SUM}}]
    rows = []
    async for g in db.sales.aggregate(pipe):
        r = {**g["_id"], **{k: round(g[k], 2) if isinstance(g[k], float) else g[k] for k in SUM}}
        r["discount_pct"] = round(r["discount"] / r["gross_amount"] * 100, 2) if r["gross_amount"] else 0
        r["avg_ticket"] = round(r["net_amount"] / r["transactions"], 2) if r["transactions"] else 0
        rows.append(r)
    sort_by = params.get("sort_by") or spec["sort"][0]
    sort_dir = -1 if (params.get("sort_dir") or ("desc" if spec["sort"][1] == -1 else "asc")) == "desc" else 1
    rows.sort(key=lambda r: (r.get(sort_by) is None, r.get(sort_by)), reverse=sort_dir == -1)
    if spec.get("top_bottom"):
        n = int(params.get("limit") or 10)
        rows.sort(key=lambda r: -r["net_amount"])
        top = [{**r, "rank": f"Top {i + 1}"} for i, r in enumerate(rows[:n])]
        bottom = [{**r, "rank": f"Bottom {i + 1}"} for i, r in enumerate(reversed(rows[-n:]))] if len(rows) > n else []
        rows = top + bottom
    cols = ([("rank", "Rank", "string")] if spec.get("top_bottom") else []) + spec["dims"] + NUM + [("discount_pct", "Disc %", "pct"), ("avg_ticket", "Avg Ticket (₹)", "money")]
    total = {k: round(sum(r.get(k) or 0, 0) for r in rows) if False else round(sum((r.get(k) or 0) for r in rows), 2) for k, _, _ in NUM}
    return {"key": key, "name": spec["name"], "columns": [{"key": c[0], "label": c[1], "type": c[2]} for c in cols], "rows": rows, "totals": total}


@router.get("/reports/records")
async def records(request: Request, page: int = 1, page_size: int = 50, sort_by: str = "sale_date", sort_dir: str = "desc", user=Depends(get_current_user)):
    params = dict(request.query_params)
    return await paginate(db.sales, sales_match(params), page, page_size, (sort_by, -1 if sort_dir == "desc" else 1))


@router.get("/reports/records/export")
async def records_export(request: Request, fmt: str = "csv", user=Depends(get_current_user)):
    rows = await db.sales.find(sales_match(dict(request.query_params)), {"_id": 0}).sort("sale_date", -1).limit(100000).to_list(100000)
    await log_audit(user["username"], "report.exported", "report", "records", {"rows": len(rows), "fmt": fmt}, category="reports")
    return _stream(pd.DataFrame(rows), "source_records", fmt)


@router.get("/reports/{key}")
async def report(key: str, request: Request, user=Depends(get_current_user)):
    return await run_report(key, dict(request.query_params))


@router.get("/reports/{key}/export")
async def report_export(key: str, request: Request, fmt: str = "csv", user=Depends(get_current_user)):
    params = dict(request.query_params)
    res = await run_report(key, params)
    cols = params.get("columns").split(",") if params.get("columns") else [c["key"] for c in res["columns"]]
    labels = {c["key"]: c["label"] for c in res["columns"]}
    df = pd.DataFrame([{labels.get(c, c): r.get(c) for c in cols} for r in res["rows"]])
    await log_audit(user["username"], "report.exported", "report", key, {"rows": len(df), "fmt": fmt, "filters": params}, category="reports")
    return _stream(df, key, fmt)


def _stream(df, base, fmt):
    buf = io.BytesIO()
    if fmt == "xlsx":
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="report")
        media, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        buf.write(df.to_csv(index=False).encode("utf-8-sig"))
        media, ext = "text/csv", "csv"
    buf.seek(0)
    return StreamingResponse(buf, media_type=media, headers={"Content-Disposition": f'attachment; filename="{base}.{ext}"'})


@router.get("/saved-views")
async def saved_views(user=Depends(get_current_user)):
    return await db.saved_views.find({"$or": [{"owner": user["username"]}, {"shared": True}]}, {"_id": 0}).sort("name", 1).to_list(200)


@router.post("/saved-views")
async def save_view(body: dict, user=Depends(get_current_user)):
    doc = {"id": new_id(), "name": body.get("name", "Untitled view"), "report": body.get("report"), "params": body.get("params", {}), "columns": body.get("columns"),
           "shared": bool(body.get("shared")), "owner": user["username"], "created_at": now_iso()}
    await db.saved_views.insert_one(dict(doc))
    return doc


@router.delete("/saved-views/{view_id}")
async def delete_view(view_id: str, user=Depends(get_current_user)):
    await db.saved_views.delete_one({"id": view_id, "owner": user["username"]})
    return {"ok": True}


@router.get("/dashboard")
async def dashboard(request: Request, user=Depends(get_current_user)):
    params = dict(request.query_params)
    today = await ref_dt()
    now_wall = datetime.now(timezone.utc)
    month = today.strftime("%Y-%m")
    first_prev = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    pm = {"partner_code": params["partner_code"]} if params.get("partner_code") else {}

    async def total(m):
        agg = [g async for g in db.sales.aggregate([{"$match": {"month": m, **pm}}, {"$group": {"_id": None, "net": {"$sum": "$net_amount"}, "qty": {"$sum": "$quantity"}, "n": {"$sum": 1}}}])]
        return agg[0] if agg else {"net": 0, "qty": 0, "n": 0}
    cur, prev = await total(month), await total(first_prev)
    prev_to_date = [g async for g in db.sales.aggregate([{"$match": {"month": first_prev, "sale_date": {"$lte": (today - timedelta(days=30)).strftime("%Y-%m-%d")}, **pm}}, {"$group": {"_id": None, "net": {"$sum": "$net_amount"}}}])]
    ptd = prev_to_date[0]["net"] if prev_to_date else 0
    since30 = (now_wall - timedelta(days=30)).isoformat()
    bq = {"created_at": {"$gte": since30}, "status": {"$nin": ["Rejected"]}, **pm}
    bagg = [g async for g in db.batches.aggregate([{"$match": bq}, {"$group": {"_id": None, "total": {"$sum": "$counts.total"}, "acc": {"$sum": "$counts.accepted"}, "warn": {"$sum": "$counts.warning"}, "rej": {"$sum": "$counts.rejected"}, "dup": {"$sum": "$counts.duplicate"}, "n": {"$sum": 1}}}])]
    b = bagg[0] if bagg else {"total": 0, "acc": 0, "warn": 0, "rej": 0, "dup": 0, "n": 0}
    partners = await db.partners.find({"active": True}, {"_id": 0, "code": 1, "name": 1}).to_list(50)
    active_partners = await db.batches.distinct("partner_code", {"created_at": {"$gte": (now_wall - timedelta(days=14)).isoformat()}, "status": {"$nin": ["Rejected"]}, "source": {"$ne": "import"}})
    daily = [{"date": g["_id"], "net": round(g["net"], 2), "qty": g["qty"]} async for g in db.sales.aggregate([{"$match": {"sale_date": {"$gte": _d(30, today)}, **pm}}, {"$group": {"_id": "$sale_date", "net": {"$sum": "$net_amount"}, "qty": {"$sum": "$quantity"}}}, {"$sort": {"_id": 1}}])]
    weekly = [{"week": f"{g['_id']['y']}-W{g['_id']['w']:02d}", "net": round(g["net"], 2), "qty": g["qty"]} async for g in db.sales.aggregate([{"$match": {"year": {"$ne": None}, **pm}}, {"$group": {"_id": {"y": "$year", "w": "$week"}, "net": {"$sum": "$net_amount"}, "qty": {"$sum": "$quantity"}}}, {"$sort": {"_id.y": 1, "_id.w": 1}}])]
    by_partner = [{"partner": g["_id"], "net": round(g["net"], 2), "qty": g["qty"]} async for g in db.sales.aggregate([{"$match": {"sale_date": {"$gte": _d(30, today)}}}, {"$group": {"_id": "$partner_name", "net": {"$sum": "$net_amount"}, "qty": {"$sum": "$quantity"}}}, {"$sort": {"net": -1}}])]
    by_category = [{"category": g["_id"], "net": round(g["net"], 2)} async for g in db.sales.aggregate([{"$match": {"sale_date": {"$gte": _d(30, today)}, **pm}}, {"$group": {"_id": "$category", "net": {"$sum": "$net_amount"}}}, {"$sort": {"net": -1}}, {"$limit": 8}])]
    dq_trend = [{"date": g["_id"] or "—", "accepted": g["acc"] + g["warn"], "rejected": g["rej"], "duplicate": g["dup"]} async for g in db.batches.aggregate([{"$match": {"status": {"$nin": ["Rejected"]}, "source": {"$ne": "import"}, **pm}}, {"$group": {"_id": "$partner_name", "acc": {"$sum": "$counts.accepted"}, "warn": {"$sum": "$counts.warning"}, "rej": {"$sum": "$counts.rejected"}, "dup": {"$sum": "$counts.duplicate"}}}, {"$sort": {"acc": -1}}])]
    recent = await db.batches.find(pm, {"_id": 0, "id": 1, "file_name": 1, "partner_name": 1, "status": 1, "counts": 1, "confidence": 1, "created_at": 1}).sort("created_at", -1).limit(8).to_list(8)
    open_exc = await db.exceptions.count_documents({"status": "open", **pm})
    awaiting = await db.batches.count_documents({"status": "Awaiting Review", **pm})
    top_skus = [{"sku": g["_id"]["s"], "name": g["_id"]["n"], "net": round(g["net"], 2), "qty": g["qty"]} async for g in db.sales.aggregate([{"$match": {"sale_date": {"$gte": _d(30, today)}, **pm}}, {"$group": {"_id": {"s": "$sku", "n": "$article_name"}, "net": {"$sum": "$net_amount"}, "qty": {"$sum": "$quantity"}}}, {"$sort": {"net": -1}}, {"$limit": 5}])]
    tv = (await run_report("target_vs_actual", {"week": 32, **pm}))["rows"]
    t_sum, a_sum = sum(r["target"] for r in tv), sum(r["actual"] for r in tv)
    return {"as_of": today.strftime("%Y-%m-%d"), "kpis": {"mtd_sales": round(cur["net"], 2), "mtd_qty": cur["qty"], "mtd_txns": cur["n"], "prev_month_sales": round(prev["net"], 2), "month": month,
                     "target_wk": round(t_sum, 2), "actual_wk": round(a_sum, 2), "achievement_pct": round(a_sum / t_sum * 100, 1) if t_sum else None,
                     "mtd_change_pct": round((cur["net"] - ptd) / ptd * 100, 1) if ptd else None, "active_partners": len(active_partners), "total_partners": len(partners),
                     "rows_30d": b["total"], "accepted_30d": b["acc"] + b["warn"], "rejected_30d": b["rej"], "duplicate_30d": b["dup"], "batches_30d": b["n"],
                     "acceptance_pct": round((b["acc"] + b["warn"]) / b["total"] * 100, 1) if b["total"] else 0, "open_exceptions": open_exc, "awaiting_review": awaiting},
            "daily": daily, "weekly": weekly[-40:], "by_partner": by_partner, "by_category": by_category, "dq_trend": dq_trend, "recent_batches": recent, "top_skus": top_skus}


@router.get("/insights")
async def insights(user=Depends(get_current_user)):
    items = await compute_insights()
    return {"generated_at": now_iso(), "engine": "rule-based statistical thresholds (no LLM)", "items": items,
            "nl_query": {"status": "active", "message": "Natural-language questions are answered by Ask Bata (GPT-5.4 analytics agent) at /ask."}}


@router.get("/data-quality")
async def data_quality(user=Depends(get_current_user)):
    by_partner = [{"partner_code": g["_id"], "batches": g["n"], "total": g["total"], "accepted": g["acc"], "warning": g["warn"], "rejected": g["rej"], "duplicate": g["dup"],
                   "avg_confidence": round(g["conf"] or 0, 1), "acceptance_pct": round((g["acc"] + g["warn"]) / g["total"] * 100, 1) if g["total"] else 0}
                  async for g in db.batches.aggregate([{"$match": {"status": {"$nin": ["Rejected"]}, "counts.total": {"$gt": 0}}},
                                                       {"$group": {"_id": "$partner_code", "n": {"$sum": 1}, "total": {"$sum": "$counts.total"}, "acc": {"$sum": "$counts.accepted"}, "warn": {"$sum": "$counts.warning"},
                                                                   "rej": {"$sum": "$counts.rejected"}, "dup": {"$sum": "$counts.duplicate"}, "conf": {"$avg": "$confidence"}}}, {"$sort": {"_id": 1}}])]
    names = {p["code"]: p["name"] async for p in db.partners.find({}, {"_id": 0, "code": 1, "name": 1})}
    for r in by_partner:
        r["partner_name"] = names.get(r["partner_code"], r["partner_code"])
    by_rule = [{"rule_code": g["_id"]["r"], "severity": g["_id"]["s"], "total": g["n"], "open": g["open"]} async for g in db.exceptions.aggregate([{"$group": {"_id": {"r": "$rule_code", "s": "$severity"}, "n": {"$sum": 1}, "open": {"$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}}}}, {"$sort": {"n": -1}}])]
    trend = (await run_report("data_quality_trend", {}))["rows"][-30:]
    return {"by_partner": by_partner, "by_rule": by_rule, "trend": trend}


@router.get("/audit-logs")
async def audit_logs(page: int = 1, page_size: int = 50, category: Optional[str] = None, actor: Optional[str] = None, action: Optional[str] = None,
                     batch_id: Optional[str] = None, entity_id: Optional[str] = None, search: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None,
                     user=Depends(get_current_user)):
    q = {}
    for k, v in (("category", category), ("actor", actor), ("batch_id", batch_id), ("entity_id", entity_id)):
        if v:
            q[k] = v
    if action:
        q["action"] = {"$regex": action, "$options": "i"}
    if search:
        q["$or"] = [{"action": {"$regex": search, "$options": "i"}}, {"actor": {"$regex": search, "$options": "i"}}, {"entity_id": {"$regex": search, "$options": "i"}}]
    if date_from:
        q["created_at"] = {"$gte": date_from}
    if date_to:
        q.setdefault("created_at", {})["$lte"] = date_to + "T23:59:59"
    res = await paginate(db.audit_logs, q, page, page_size)
    res["categories"] = await db.audit_logs.distinct("category")
    return res


@router.get("/notifications")
async def notifications(unread_only: bool = False, limit: int = 30, user=Depends(get_current_user)):
    q = {"$or": [{"roles": user["role"]}, {"user_id": user["username"]}]}
    if unread_only:
        q["read_by"] = {"$ne": user["username"]}
    items = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    unread = await db.notifications.count_documents({"$or": [{"roles": user["role"]}, {"user_id": user["username"]}], "read_by": {"$ne": user["username"]}})
    for i in items:
        i["read"] = user["username"] in i.get("read_by", [])
        i.pop("read_by", None)
    return {"items": items, "unread": unread}


@router.post("/notifications/read")
async def mark_read(body: dict, user=Depends(get_current_user)):
    q = {"id": {"$in": body["ids"]}} if body.get("ids") else {"$or": [{"roles": user["role"]}, {"user_id": user["username"]}]}
    await db.notifications.update_many(q, {"$addToSet": {"read_by": user["username"]}})
    return {"ok": True}
