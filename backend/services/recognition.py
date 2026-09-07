import re
from rapidfuzz import fuzz, process
from core.db import db
from services.parser import infer_type

CANONICAL_FIELDS = [
    {"key": "sale_date", "label": "Sale Date", "type": "date", "required": True},
    {"key": "store_code", "label": "Store Code", "type": "string", "required": True},
    {"key": "store_name", "label": "Store Name", "type": "string", "required": False},
    {"key": "sku", "label": "Article Code", "type": "string", "required": True},
    {"key": "article_name", "label": "Article Name", "type": "string", "required": False},
    {"key": "category", "label": "Category", "type": "string", "required": False},
    {"key": "size", "label": "Size", "type": "string", "required": False},
    {"key": "quantity", "label": "Quantity", "type": "number", "required": True},
    {"key": "mrp", "label": "MRP", "type": "number", "required": False},
    {"key": "unit_price", "label": "Unit Price", "type": "number", "required": True},
    {"key": "discount", "label": "Discount Amount", "type": "number", "required": False},
    {"key": "tax", "label": "Tax Amount", "type": "number", "required": False},
    {"key": "net_amount", "label": "Net Amount", "type": "number", "required": True},
    {"key": "invoice_no", "label": "Invoice / Bill No", "type": "string", "required": False},
    {"key": "transaction_id", "label": "Transaction ID", "type": "string", "required": False},
    {"key": "city", "label": "City", "type": "string", "required": False},
    {"key": "region", "label": "Region", "type": "string", "required": False},
]
FIELD_MAP = {f["key"]: f for f in CANONICAL_FIELDS}
REQUIRED_FIELDS = [f["key"] for f in CANONICAL_FIELDS if f["required"]]


def normalize(s) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(s or "").lower())).strip()


async def build_alias_index(partner_code=None) -> dict:
    """norm alias -> field. Partner-specific aliases override global ones."""
    idx = {}
    for f in CANONICAL_FIELDS:
        idx[normalize(f["key"])] = f["key"]
        idx[normalize(f["label"])] = f["key"]
    q = {"partner_code": None, "active": True}
    async for a in db.aliases.find(q, {"_id": 0}):
        idx[a["alias_norm"]] = a["field"]
    if partner_code:
        async for a in db.aliases.find({"partner_code": partner_code, "active": True}, {"_id": 0}):
            idx[a["alias_norm"]] = a["field"]
    return idx


async def load_learned(partner_code) -> dict:
    """Latest approved mapping version for partner: norm header -> {field, version}."""
    if not partner_code:
        return {}
    doc = await db.partner_mappings.find_one({"partner_code": partner_code, "active": True}, {"_id": 0}, sort=[("version", -1)])
    if not doc:
        return {}
    return {normalize(k): {"field": v, "version": doc["version"]} for k, v in doc["mapping"].items() if v}


def detect_partner(filename, sheets, partners, selected_code, learned_all):
    if selected_code:
        p = next((p for p in partners if p["code"] == selected_code), None)
        if p:
            return {"partner_code": p["code"], "partner_name": p["name"], "confidence": 100,
                    "reason": "Partner selected by user at upload", "candidates": []}
    fname = normalize(filename)
    head_text = " ".join(normalize(c) for s in sheets for row in s["rows"][:15] for c in row if isinstance(c, str))
    scores = []
    for p in partners:
        score, reasons = 0, []
        kws = [normalize(p["name"])] + [normalize(k) for k in p.get("keywords", [])]
        kws = [k for k in kws if k]
        if any(k in fname for k in kws):
            score += 60
            reasons.append("filename keyword")
        if any(k in head_text for k in kws):
            score += 40
            reasons.append("partner name in sheet header")
        learned = learned_all.get(p["code"]) or {}
        if learned:
            for s in sheets:
                for row in s["rows"][:40]:
                    hdrs = {normalize(c) for c in row if isinstance(c, str)}
                    if len(hdrs) >= 3:
                        overlap = len(hdrs & set(learned)) / max(len(learned), 1)
                        if overlap >= 0.7:
                            score += 35
                            reasons.append(f"header signature matches learned mapping ({int(overlap * 100)}%)")
                            break
                else:
                    continue
                break
        if score:
            scores.append({"partner_code": p["code"], "partner_name": p["name"], "score": min(score, 100), "reasons": reasons})
    scores.sort(key=lambda x: -x["score"])
    if not scores:
        return {"partner_code": None, "partner_name": None, "confidence": 0,
                "reason": "No partner signature found in filename or sheet content", "candidates": []}
    top = scores[0]
    conf = top["score"]
    if len(scores) > 1 and scores[1]["score"] >= top["score"] - 10:
        conf = max(30, conf - 30)
    return {"partner_code": top["partner_code"], "partner_name": top["partner_name"], "confidence": conf,
            "reason": "Detected via " + ", ".join(top["reasons"]), "candidates": scores[:3]}


def map_columns(headers, sample_rows, alias_idx, learned):
    labels_norm = {normalize(f["label"]): f["key"] for f in CANONICAL_FIELDS}
    choices = list(alias_idx.keys())
    results = []
    for i, h in enumerate(headers):
        norm = normalize(h)
        samples = [r.get(h) for r in sample_rows[:8]]
        samples = [s for s in samples if s is not None][:5]
        field, conf, reason = None, 0, "No match found in dictionary or learned mappings"
        if norm in learned:
            field, conf = learned[norm]["field"], 97
            reason = f"Previously approved mapping for this partner (v{learned[norm]['version']})"
        elif norm in labels_norm or norm in {normalize(f["key"]) for f in CANONICAL_FIELDS}:
            field, conf, reason = alias_idx.get(norm), 100, "Exact match with Bata standard field"
        elif norm in alias_idx:
            field, conf, reason = alias_idx[norm], 94, f"Known alias '{h}' in dictionary"
        elif norm and choices:
            match = process.extractOne(norm, choices, scorer=fuzz.token_set_ratio)
            if match and match[1] >= 75:
                field, conf = alias_idx[match[0]], int(match[1] * 0.88)
                reason = f"Fuzzy match to alias '{match[0]}' ({int(match[1])}% similar)"
        if field:
            inferred = infer_type(samples)
            expected = FIELD_MAP[field]["type"]
            if inferred != "empty":
                if inferred == expected or (expected == "string" and inferred in ("number", "date")):
                    if conf < 100:
                        conf = min(100, conf + 3)
                        reason += "; sample values match expected type"
                else:
                    conf = max(10, conf - 30)
                    reason += f"; WARNING sample values look like {inferred}, expected {expected}"
        results.append({"index": i, "source_column": h, "sample_values": [str(s) for s in samples], "proposed_field": field,
                        "confidence": conf, "reason": reason, "action": "map" if field else "ignore", "inferred_type": infer_type(samples)})
    by_field = {}
    for r in results:
        if r["proposed_field"]:
            by_field.setdefault(r["proposed_field"], []).append(r)
    for f, rs in by_field.items():
        rs.sort(key=lambda x: -x["confidence"])
        for loser in rs[1:]:
            loser["reason"] = f"Field '{f}' already claimed by '{rs[0]['source_column']}' with higher confidence"
            loser["proposed_field"], loser["confidence"], loser["action"] = None, 0, "ignore"
    return results


def compute_overall(partner_conf, header_conf, columns, thresholds):
    mapped = [c for c in columns if c["proposed_field"] and c.get("action") != "ignore"]
    mapped_fields = {c["proposed_field"] for c in mapped}
    missing = [f for f in REQUIRED_FIELDS if f not in mapped_fields]
    col_avg = sum(c["confidence"] for c in mapped) / len(mapped) if mapped else 0
    overall = 0.3 * partner_conf + 0.1 * header_conf + 0.6 * col_avg
    if missing:
        overall = min(overall, 45)
    if not partner_conf:
        overall = min(overall, 40)
    overall = int(round(overall))
    level = "high" if overall >= thresholds["high"] else "medium" if overall >= thresholds["medium"] else "low"
    return {"overall": overall, "level": level, "partner": partner_conf, "header_row": header_conf,
            "columns_avg": int(round(col_avg)), "missing_required": missing, "mapped_count": len(mapped), "total_columns": len(columns)}
