import statistics
from datetime import datetime, timezone, timedelta
from core.db import db
from core.utils import new_id


def _d(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


async def compute_insights():
    out = []
    partners = await db.partners.find({"active": True}, {"_id": 0}).to_list(50)
    last_sale = await db.sales.find_one({"sale_date": {"$ne": None}}, {"_id": 0, "sale_date": 1}, sort=[("sale_date", -1)])
    ref = datetime.fromisoformat(last_sale["sale_date"]).replace(tzinfo=timezone.utc) if last_sale else datetime.now(timezone.utc)
    since = (ref - timedelta(days=30)).strftime("%Y-%m-%d")
    daily = {}
    async for g in db.sales.aggregate([{"$match": {"sale_date": {"$gte": since}}},
                                       {"$group": {"_id": {"p": "$partner_code", "d": "$sale_date"}, "net": {"$sum": "$net_amount"}, "n": {"$sum": 1}}}]):
        daily.setdefault(g["_id"]["p"], {})[g["_id"]["d"]] = g["net"]
    for p in partners:
        series = sorted(daily.get(p["code"], {}).items())
        if len(series) < 8:
            continue
        hist = [v for _, v in series[:-1]][-14:]
        last_d, last_v = series[-1]
        mean, sd = statistics.mean(hist), statistics.pstdev(hist) or 1
        z = (last_v - mean) / sd
        pct = (last_v - mean) / mean * 100 if mean else 0
        if abs(z) > 2 or abs(pct) > 40:
            kind = "spike" if last_v > mean else "drop"
            out.append({"id": new_id(), "type": f"sales_{kind}", "severity": "warning" if kind == "drop" else "info", "partner_code": p["code"],
                        "title": f"{p['name']}: sales {kind} on {last_d}", "metric": {"value": round(last_v, 2), "baseline": round(mean, 2), "pct_change": round(pct, 1), "z_score": round(z, 2)},
                        "description": f"₹{last_v:,.0f} vs 14-day average ₹{mean:,.0f} ({pct:+.0f}%, z={z:.1f}). Statistical threshold: |z|>2 or |Δ|>40%.",
                        "link": {"path": "/reports", "params": {"report": "daily_sales", "partner_code": p["code"], "date_from": last_d, "date_to": last_d}}})
    store_rows = {}
    async for g in db.sales.aggregate([{"$match": {"sale_date": {"$gte": (ref - timedelta(days=14)).strftime("%Y-%m-%d")}}},
                                       {"$group": {"_id": {"p": "$partner_code", "s": "$store_code", "n": "$store_name"}, "net": {"$sum": "$net_amount"}}}]):
        store_rows.setdefault(g["_id"]["p"], []).append((g["_id"]["s"], g["_id"]["n"], g["net"]))
    pname = {p["code"]: p["name"] for p in partners}
    for pc, rows in store_rows.items():
        if len(rows) < 3:
            continue
        med = statistics.median(r[2] for r in rows)
        worst = sorted([r for r in rows if med and r[2] < 0.5 * med], key=lambda r: r[2])[:3]
        for code, name, net in worst:
            if True:
                out.append({"id": new_id(), "type": "underperformer", "severity": "warning", "partner_code": pc,
                            "title": f"Underperforming store: {name or code} ({pname.get(pc, pc)})",
                            "metric": {"value": round(net, 2), "baseline": round(med, 2), "pct_change": round((net - med) / med * 100, 1)},
                            "description": f"14-day net ₹{net:,.0f} is below 50% of partner store median ₹{med:,.0f}.",
                            "link": {"path": "/reports", "params": {"report": "records", "partner_code": pc, "store_code": code, "date_from": _d(14)}}})
    grace = 2
    rule = await db.validation_rules.find_one({"code": "MISSING_SUBMISSION"}, {"_id": 0})
    if rule:
        grace = rule.get("params", {}).get("grace_days", 2)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=grace + 1)).isoformat()
    for p in partners:
        if p.get("expected_frequency", "daily") == "none":
            continue
        last = await db.batches.find_one({"partner_code": p["code"], "status": {"$nin": ["Rejected", "Failed"]}, "source": {"$ne": "import"}}, {"_id": 0, "created_at": 1, "id": 1}, sort=[("created_at", -1)])
        if not last or last["created_at"] < cutoff:
            days = (datetime.now(timezone.utc) - datetime.fromisoformat(last["created_at"])).days if last else None
            out.append({"id": new_id(), "type": "missing_submission", "severity": "critical", "partner_code": p["code"],
                        "title": f"Missing submission: {p['name']}", "metric": {"days_since": days},
                        "description": f"No file received for {days} days (expected {p.get('expected_frequency', 'daily')}, grace {grace}d)." if days is not None else "No file has ever been received.",
                        "link": {"path": "/batches", "params": {"partner_code": p["code"]}}})
    pcts = []
    async for g in db.sales.aggregate([{"$match": {"sale_date": {"$gte": since}, "gross_amount": {"$gt": 0}}}, {"$project": {"discount_pct": 1}}, {"$sample": {"size": 5000}}]):
        pcts.append(g["discount_pct"] or 0)
    if len(pcts) > 20:
        mean, sd = statistics.mean(pcts), statistics.pstdev(pcts)
        thr = round(mean + 2 * sd, 1)
        n = await db.sales.count_documents({"sale_date": {"$gte": since}, "discount_pct": {"$gt": thr}})
        if n:
            out.append({"id": new_id(), "type": "discount_outlier", "severity": "warning", "partner_code": None, "title": f"{n} transactions with outlier discounts (> {thr}%)",
                        "metric": {"count": n, "threshold_pct": thr, "mean_pct": round(mean, 1)},
                        "description": f"Discount % above mean + 2σ ({mean:.1f}% + 2×{sd:.1f}%) in the last 30 days.",
                        "link": {"path": "/reports", "params": {"report": "records", "min_discount_pct": thr, "date_from": since}}})
    async for b in db.batches.find({"row_count_anomaly": {"$exists": True}, "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}}, {"_id": 0}):
        out.append({"id": new_id(), "type": "row_count_anomaly", "severity": "info", "partner_code": b["partner_code"], "title": f"Unusual row count: {b['file_name']}",
                    "metric": {"rows": b["counts"]["total"]}, "description": b["row_count_anomaly"], "link": {"path": f"/batches/{b['id']}", "params": {}}})
    async for g in db.batches.aggregate([{"$match": {"created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}, "status": {"$nin": ["Rejected"]}, "counts.total": {"$gt": 0}}},
                                         {"$group": {"_id": "$partner_code", "total": {"$sum": "$counts.total"}, "rej": {"$sum": "$counts.rejected"}}}]):
        if g["total"] and g["rej"] / g["total"] > 0.1:
            out.append({"id": new_id(), "type": "data_quality", "severity": "warning", "partner_code": g["_id"], "title": f"High rejection rate: {pname.get(g['_id'], g['_id'])}",
                        "metric": {"rejection_pct": round(g["rej"] / g["total"] * 100, 1), "rejected": g["rej"], "total": g["total"]},
                        "description": f"{g['rej']} of {g['total']} rows rejected in the last 7 days ({g['rej'] / g['total'] * 100:.0f}%, threshold 10%).",
                        "link": {"path": "/review", "params": {"partner_code": g["_id"]}}})
    order = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda i: order.get(i["severity"], 3))
    return out
