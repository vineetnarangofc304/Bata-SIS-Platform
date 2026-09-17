"""Live data tools for the Ask Bata analytics agent. Every tool returns JSON-serialisable dicts; rows are capped."""
import re
from core.db import db
from routers.analytics import run_report, sales_match, REPORTS
from services.insights import compute_insights
from services.help_content import search_help

MAX_ROWS = 60
DIMS = {"partner_code", "partner_name", "store_code", "store_name", "city", "region", "cluster_manager", "category", "brand", "sku", "article_name", "size", "sale_date", "month", "year", "week", "data_quality"}
FILTER_KEYS = ["date_from", "date_to", "partner_code", "store_code", "region", "category", "sku", "brand", "city", "data_quality", "min_discount_pct", "search"]

FILTER_SCHEMA = {"type": "object", "description": "Optional filters", "properties": {
    "date_from": {"type": "string", "description": "YYYY-MM-DD inclusive"}, "date_to": {"type": "string", "description": "YYYY-MM-DD inclusive"},
    "partner_code": {"type": "string", "description": "Partner code e.g. LIFESTYLE, SHOPPERS, RTRENDS, RCENTRAL, CENTRO, INC5, KORA, LULU, SPENCER, ZUUP"},
    "store_code": {"type": "string"}, "region": {"type": "string", "description": "North|South|East|West"}, "category": {"type": "string"}, "sku": {"type": "string", "description": "7-digit Bata article code"},
    "brand": {"type": "string"}, "city": {"type": "string"}, "year": {"type": "integer"}, "week": {"type": "integer", "description": "Bata week number"}, "month": {"type": "string", "description": "YYYY-MM"},
    "cluster_manager": {"type": "string"}, "min_discount_pct": {"type": "number"}, "search": {"type": "string", "description": "regex over sku/article_name/store_name/invoice_no"}}}

TOOLS = [
    {"type": "function", "function": {"name": "get_data_coverage", "description": "Always call first in a session when unsure what data exists: date range, years/weeks, partners, row counts, latest week per partner.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "run_report", "description": "Run one of the platform's standard reports exactly as the Reports page does. Keys: " + ", ".join(REPORTS.keys()) + ". Extra params: week (target_vs_actual), days (missing_submissions), limit (top_bottom).",
                                      "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "filters": FILTER_SCHEMA, "week": {"type": "integer"}, "days": {"type": "integer"}, "limit": {"type": "integer"}}, "required": ["key"]}}},
    {"type": "function", "function": {"name": "aggregate_sales", "description": "Ad-hoc aggregation of the sales reporting data. Returns Σquantity, Σgross, Σdiscount, Σtax, Σnet, transactions, discount_pct, avg_ticket per group. Use for any question the standard reports don't answer (e.g. by cluster manager, by size, by city, by week for one store).",
                                      "parameters": {"type": "object", "properties": {"group_by": {"type": "array", "items": {"type": "string", "enum": sorted(DIMS)}, "description": "Dimensions; empty = grand total"}, "filters": FILTER_SCHEMA,
                                                                                       "sort_by": {"type": "string", "enum": ["net_amount", "quantity", "gross_amount", "discount", "transactions", "discount_pct", "avg_ticket"], "default": "net_amount"},
                                                                                       "sort_dir": {"type": "string", "enum": ["asc", "desc"], "default": "desc"}, "limit": {"type": "integer", "default": 25, "maximum": MAX_ROWS}}}}},
    {"type": "function", "function": {"name": "get_dashboard", "description": "Dashboard KPIs (MTD sales, target achievement, acceptance %, pending action, weekly trend, partner split, category mix, top articles).", "parameters": {"type": "object", "properties": {"partner_code": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "get_targets_vs_actual", "description": "Target vs actual NSV for a Bata week (2026) at partner, store, grpcat or cluster_manager level, with achievement % and gap. Use for store-level target drill questions.",
                                      "parameters": {"type": "object", "properties": {"week": {"type": "integer", "default": 32}, "level": {"type": "string", "enum": ["partner", "store", "grpcat", "cluster_manager"], "default": "partner"}, "partner_code": {"type": "string"}, "region": {"type": "string"}, "limit": {"type": "integer", "default": 40}, "sort": {"type": "string", "enum": ["achievement_asc", "achievement_desc", "gap_asc", "gap_desc", "target_desc"], "default": "achievement_desc"}}}}},
    {"type": "function", "function": {"name": "get_stock", "description": "Week-32 closing stock (pairs) grouped by partner, store, category or sku, with week-32 sold pairs and weeks of cover.",
                                      "parameters": {"type": "object", "properties": {"level": {"type": "string", "enum": ["partner", "store", "category", "sku"], "default": "partner"}, "partner_code": {"type": "string"}, "store_code": {"type": "string"}, "region": {"type": "string"}, "limit": {"type": "integer", "default": 40}}}}},
    {"type": "function", "function": {"name": "get_margins", "description": "Partner margin % master (BATA and HP markets) for all partners.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "list_partners", "description": "Partner master: code, name, expected frequency, partial ingestion, active.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "find_store", "description": "Look up stores by code, name, city or cluster manager.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "partner_code": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "find_article", "description": "Look up Bata articles (SKUs) by code or name.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_batches", "description": "Ingestion batches (files) with status, counts, confidence, dates.", "parameters": {"type": "object", "properties": {"partner_code": {"type": "string"}, "status": {"type": "string"}, "limit": {"type": "integer", "default": 20}}}}},
    {"type": "function", "function": {"name": "get_exceptions", "description": "Exceptions (validation issues) — summary by rule/partner or the latest individual items.", "parameters": {"type": "object", "properties": {"partner_code": {"type": "string"}, "status": {"type": "string", "description": "open|accepted|corrected|ignored|rejected"}, "rule_code": {"type": "string"}, "mode": {"type": "string", "enum": ["summary", "items"], "default": "summary"}, "limit": {"type": "integer", "default": 20}}}}},
    {"type": "function", "function": {"name": "get_data_quality", "description": "Data-quality overview: acceptance % and avg confidence per partner, exceptions by rule, 30-day trend.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_insights", "description": "Current rule-based anomalies (spikes/drops, underperformers, missing submissions, discount outliers, rejection rates).", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "search_help", "description": "Search the Help Center for how a KPI, report, formula, rule or screen works.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]


def _match(f: dict):
    f = f or {}
    q = sales_match(f)
    for k in ("year", "week"):
        if f.get(k) is not None:
            q[k] = int(f[k])
    if f.get("month"):
        q["month"] = f["month"]
    if f.get("cluster_manager"):
        q["cluster_manager"] = {"$regex": re.escape(f["cluster_manager"]), "$options": "i"}
    return q


def _r(v):
    return round(v, 2) if isinstance(v, float) else v


async def get_data_coverage(**_):
    rng = [g async for g in db.sales.aggregate([{"$match": {"sale_date": {"$ne": None}}}, {"$group": {"_id": None, "min": {"$min": "$sale_date"}, "max": {"$max": "$sale_date"}, "rows": {"$sum": 1}, "net": {"$sum": "$net_amount"}}}])]
    per_partner = [{"partner_code": g["_id"], "rows": g["rows"], "net_amount": _r(g["net"]), "first_date": g["min"], "last_date": g["max"], "latest_week": f"{g['y']}-W{g['w']}"} async for g in db.sales.aggregate([{"$group": {"_id": "$partner_code", "rows": {"$sum": 1}, "net": {"$sum": "$net_amount"}, "min": {"$min": "$sale_date"}, "max": {"$max": "$sale_date"}, "y": {"$max": "$year"}, "w": {"$max": "$week"}}}, {"$sort": {"_id": 1}}])]
    weeks = [f"{g['_id']['y']}-W{g['_id']['w']}" async for g in db.sales.aggregate([{"$group": {"_id": {"y": "$year", "w": "$week"}}}, {"$sort": {"_id.y": -1, "_id.w": -1}}, {"$limit": 6}])]
    return {"sales": rng[0] if rng else {}, "latest_weeks": weeks, "per_partner": per_partner, "targets": {"weeks": await db.targets.distinct("week"), "year": 2026, "stores": len(await db.targets.distinct("store_code"))},
            "stock": {"week": 32, "rows": await db.stock.count_documents({})}, "stores": await db.stores.count_documents({}), "articles": await db.skus.count_documents({}), "open_exceptions": await db.exceptions.count_documents({"status": "open"}),
            "categories": await db.sales.distinct("category"), "regions": await db.sales.distinct("region"), "note": "Weekly history rows are dated on the Bata week start (Monday). Dashboards are 'as of' the latest sale_date."}


async def run_report_tool(key, filters=None, **extra):
    params = {k: str(v) for k, v in (filters or {}).items() if v not in (None, "")}
    params.update({k: str(v) for k, v in extra.items() if v is not None})
    res = await run_report(key, params)
    rows = res["rows"]
    return {"report": res["name"], "columns": res["columns"], "row_count": len(rows), "rows": rows[:MAX_ROWS], "totals": res.get("totals"), "truncated": len(rows) > MAX_ROWS, "filters": params}


async def aggregate_sales(group_by=None, filters=None, sort_by="net_amount", sort_dir="desc", limit=25, **_):
    dims = [d for d in (group_by or []) if d in DIMS]
    gid = {d: f"${d}" for d in dims} or None
    pipe = [{"$match": _match(filters)}, {"$group": {"_id": gid, "quantity": {"$sum": "$quantity"}, "gross_amount": {"$sum": "$gross_amount"}, "discount": {"$sum": "$discount"}, "tax": {"$sum": "$tax"}, "net_amount": {"$sum": "$net_amount"}, "transactions": {"$sum": 1}}}]
    rows = []
    async for g in db.sales.aggregate(pipe):
        r = {**(g["_id"] or {}), **{k: _r(g[k]) for k in ("quantity", "gross_amount", "discount", "tax", "net_amount", "transactions")}}
        r["discount_pct"] = round(r["discount"] / r["gross_amount"] * 100, 2) if r["gross_amount"] else 0
        r["avg_ticket"] = round(r["net_amount"] / r["transactions"], 2) if r["transactions"] else 0
        rows.append(r)
    rows.sort(key=lambda r: (r.get(sort_by) is None, r.get(sort_by)), reverse=(sort_dir != "asc"))
    limit = min(int(limit or 25), MAX_ROWS)
    total = {k: _r(sum((r.get(k) or 0) for r in rows)) for k in ("quantity", "gross_amount", "discount", "net_amount", "transactions")}
    return {"group_by": dims, "filters": filters or {}, "group_count": len(rows), "rows": rows[:limit], "truncated": len(rows) > limit, "grand_total": total}


async def get_dashboard(partner_code=None, **_):
    from routers.analytics import dashboard
    from starlette.requests import Request
    scope = {"type": "http", "query_string": (f"partner_code={partner_code}" if partner_code else "").encode(), "headers": []}
    d = await dashboard(Request(scope), user={"role": "admin"})
    d.pop("recent_batches", None)
    d["weekly"] = d["weekly"][-12:]
    d.pop("daily", None)
    return d


async def get_targets_vs_actual(week=32, level="partner", partner_code=None, region=None, limit=40, sort="achievement_desc", **_):
    week = int(week or 32)
    m = {"week": week}
    sm = {"year": 2026, "week": week}
    if partner_code:
        m["partner_code"] = sm["partner_code"] = partner_code
    if region:
        m["region"] = sm["region"] = region
    key = {"partner": ["partner_code", "partner_name"], "store": ["partner_name", "store_code", "store_name", "region", "cluster_manager"], "grpcat": ["grpcat"], "cluster_manager": ["cluster_manager", "partner_name"]}[level]
    skey = {"partner": ["partner_code", "partner_name"], "store": ["partner_name", "store_code", "store_name", "region", "cluster_manager"], "grpcat": ["category"], "cluster_manager": ["cluster_manager", "partner_name"]}[level]
    tg = {}
    async for g in db.targets.aggregate([{"$match": m}, {"$group": {"_id": {k: f"${k}" for k in key}, "target": {"$sum": "$target"}}}]):
        tg[tuple(g["_id"].get(k) for k in key)] = g
    ac = {}
    async for g in db.sales.aggregate([{"$match": sm}, {"$group": {"_id": {k: f"${k}" for k in skey}, "net": {"$sum": "$net_amount"}, "qty": {"$sum": "$quantity"}}}]):
        ac[tuple(g["_id"].get(k) for k in skey)] = g
    rows = []
    for k, g in tg.items():
        a = ac.get(k, {"net": 0, "qty": 0})
        row = dict(zip(key, k))
        row.update({"target": _r(g["target"]), "actual": _r(a["net"]), "gap": _r(a["net"] - g["target"]), "achievement_pct": round(a["net"] / g["target"] * 100, 1) if g["target"] else None, "pairs": a["qty"]})
        rows.append(row)
    sk = {"achievement_asc": (lambda r: (r["achievement_pct"] is None, r["achievement_pct"] or 0)), "achievement_desc": (lambda r: -(r["achievement_pct"] or 0)), "gap_asc": (lambda r: r["gap"]), "gap_desc": (lambda r: -r["gap"]), "target_desc": (lambda r: -r["target"])}[sort]
    rows.sort(key=sk)
    t, a = sum(r["target"] for r in rows), sum(r["actual"] for r in rows)
    return {"week": week, "level": level, "row_count": len(rows), "rows": rows[:min(int(limit or 40), MAX_ROWS)], "truncated": len(rows) > limit, "total": {"target": _r(t), "actual": _r(a), "achievement_pct": round(a / t * 100, 1) if t else None, "gap": _r(a - t)},
            "note": "Actual = Σ net_amount in sales for 2026 week %d; stores with no target are excluded." % week}


async def get_stock(level="partner", partner_code=None, store_code=None, region=None, limit=40, **_):
    m = {k: v for k, v in (("partner_code", partner_code), ("store_code", store_code), ("region", region)) if v}
    key = {"partner": ["partner_name"], "store": ["partner_name", "store_code", "store_name", "region"], "category": ["category"], "sku": ["sku", "category"]}[level]
    rows = [{**g["_id"], "stock_qty": g["qty"], "articles": len(g["arts"])} async for g in db.stock.aggregate([{"$match": m}, {"$group": {"_id": {k: f"${k}" for k in key}, "qty": {"$sum": "$quantity"}, "arts": {"$addToSet": "$sku"}}}, {"$sort": {"qty": -1}}])]
    sold = {tuple(g["_id"].get(k) for k in key): g["q"] async for g in db.sales.aggregate([{"$match": {"year": 2026, "week": 32, **m}}, {"$group": {"_id": {k: f"${k}" for k in key}, "q": {"$sum": "$quantity"}}}])}
    for r in rows:
        s = sold.get(tuple(r.get(k) for k in key), 0)
        r["sold_wk32"] = s
        r["weeks_cover"] = round(r["stock_qty"] / s, 1) if s else None
    return {"level": level, "week": 32, "row_count": len(rows), "rows": rows[:min(int(limit or 40), MAX_ROWS)], "total_stock": sum(r["stock_qty"] for r in rows)}


async def get_margins(**_):
    return {"rows": await db.margins.find({}, {"_id": 0, "partner_code": 1, "partner_name": 1, "market": 1, "margin": 1}).sort([("partner_code", 1), ("market", 1)]).to_list(100), "note": "margin is a fraction (0.35 = 35%)"}


async def list_partners(**_):
    return {"rows": await db.partners.find({}, {"_id": 0, "code": 1, "name": 1, "expected_frequency": 1, "partial_ingestion": 1, "active": 1, "keywords": 1}).to_list(50)}


async def find_store(query, partner_code=None, **_):
    rx = {"$regex": re.escape(str(query)), "$options": "i"}
    q = {"$or": [{"code": rx}, {"name": rx}, {"city": rx}, {"cluster_manager": rx}, {"state": rx}]}
    if partner_code:
        q["partner_code"] = partner_code
    return {"rows": await db.stores.find(q, {"_id": 0, "partner_code": 1, "code": 1, "name": 1, "city": 1, "state": 1, "region": 1, "cluster_manager": 1, "active": 1}).limit(30).to_list(30)}


async def find_article(query, **_):
    rx = {"$regex": re.escape(str(query)), "$options": "i"}
    return {"rows": await db.skus.find({"$or": [{"code": rx}, {"name": rx}]}, {"_id": 0, "code": 1, "name": 1, "category": 1, "brand": 1, "mrp": 1}).limit(30).to_list(30)}


async def get_batches(partner_code=None, status=None, limit=20, **_):
    q = {k: v for k, v in (("partner_code", partner_code), ("status", status)) if v}
    rows = await db.batches.find(q, {"_id": 0, "id": 1, "file_name": 1, "partner_name": 1, "status": 1, "counts": 1, "confidence": 1, "source": 1, "created_at": 1, "review_reason": 1, "failure_reason": 1}).sort("created_at", -1).limit(min(int(limit or 20), MAX_ROWS)).to_list(MAX_ROWS)
    by_status = {g["_id"]: g["n"] async for g in db.batches.aggregate([{"$match": q}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    return {"by_status": by_status, "rows": rows}


async def get_exceptions(partner_code=None, status=None, rule_code=None, mode="summary", limit=20, **_):
    q = {k: v for k, v in (("partner_code", partner_code), ("status", status), ("rule_code", rule_code)) if v}
    if mode == "items":
        return {"rows": await db.exceptions.find(q, {"_id": 0, "id": 1, "batch_id": 1, "partner_name": 1, "rule_code": 1, "severity": 1, "field": 1, "message": 1, "original_value": 1, "proposed_value": 1, "status": 1, "created_at": 1}).sort("created_at", -1).limit(min(int(limit or 20), MAX_ROWS)).to_list(MAX_ROWS)}
    rows = [{"partner_name": g["_id"]["p"], "rule_code": g["_id"]["r"], "status": g["_id"]["s"], "count": g["n"]} async for g in db.exceptions.aggregate([{"$match": q}, {"$group": {"_id": {"p": "$partner_name", "r": "$rule_code", "s": "$status"}, "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": MAX_ROWS}])]
    return {"total": await db.exceptions.count_documents(q), "rows": rows}


async def get_data_quality(**_):
    from routers.analytics import data_quality
    return await data_quality(user={"role": "admin"})


async def get_insights(**_):
    items = await compute_insights()
    return {"count": len(items), "items": [{k: i.get(k) for k in ("type", "severity", "partner_code", "title", "description", "metric")} for i in items[:30]]}


async def search_help_tool(query, **_):
    return {"results": search_help(query)}


DISPATCH = {"get_data_coverage": get_data_coverage, "run_report": run_report_tool, "aggregate_sales": aggregate_sales, "get_dashboard": get_dashboard, "get_targets_vs_actual": get_targets_vs_actual,
            "get_stock": get_stock, "get_margins": get_margins, "list_partners": list_partners, "find_store": find_store, "find_article": find_article, "get_batches": get_batches,
            "get_exceptions": get_exceptions, "get_data_quality": get_data_quality, "get_insights": get_insights, "search_help": search_help_tool}


async def dispatch(name, args):
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return await fn(**(args or {}))
    except Exception as e:
        return {"error": str(e)[:300]}
