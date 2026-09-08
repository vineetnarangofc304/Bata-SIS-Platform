from datetime import datetime, timezone
from rapidfuzz import fuzz, process
from services.parser import parse_number, parse_date
from services.recognition import FIELD_MAP

DEFAULT_RULES = [
    {"code": "REQUIRED_FIELD", "name": "Required field missing", "severity": "Error", "blocking": True, "params": {},
     "description": "Mandatory Bata field (date, store, article, qty, price, net) is empty"},
    {"code": "INVALID_DATE", "name": "Invalid date", "severity": "Error", "blocking": True, "params": {},
     "description": "Sale date could not be parsed from any known format"},
    {"code": "FUTURE_DATE", "name": "Future sale date", "severity": "Error", "blocking": True, "params": {},
     "description": "Sale date is after today"},
    {"code": "UNKNOWN_STORE", "name": "Unknown store / SIS", "severity": "Error", "blocking": True, "params": {"fuzzy_threshold": 80},
     "description": "Store code not found in partner store master"},
    {"code": "UNKNOWN_SKU", "name": "Unknown SKU / article", "severity": "Warning", "blocking": False, "params": {},
     "description": "Article code not found in Bata article master (partner-internal codes are flagged for mapping, row still loads)"},
    {"code": "NEGATIVE_QTY", "name": "Negative or zero quantity", "severity": "Warning", "blocking": False, "params": {"allow_returns": True},
     "description": "Zero quantity is invalid; negative quantity = customer return (allowed by default, flagged for visibility)"},
    {"code": "INVALID_PRICE", "name": "Invalid unit price", "severity": "Error", "blocking": True, "params": {},
     "description": "Unit price must be a positive number"},
    {"code": "DISCOUNT_OVER_LIMIT", "name": "Discount over limit", "severity": "Warning", "blocking": False, "params": {"max_pct": 60},
     "description": "Discount exceeds allowed percentage of gross value"},
    {"code": "ARITHMETIC_MISMATCH", "name": "Arithmetic mismatch", "severity": "Warning", "blocking": False, "params": {"tolerance": 1.0},
     "description": "qty × price − discount + tax does not equal net amount"},
    {"code": "DUPLICATE_ROW", "name": "Duplicate transaction", "severity": "Warning", "blocking": False, "params": {},
     "description": "Business key (partner, store, date, article, invoice, qty, net) already ingested"},
    {"code": "ROW_COUNT_ANOMALY", "name": "Row count anomaly", "severity": "Info", "blocking": False, "params": {"deviation_pct": 50},
     "description": "Batch row count deviates from partner's usual volume"},
    {"code": "MISSING_SUBMISSION", "name": "Missing submission", "severity": "Warning", "blocking": False, "params": {"grace_days": 2},
     "description": "Partner has not submitted a file within expected frequency"},
]


def standardize_row(raw: dict, mapping: dict):
    values, originals = {}, {}
    for src, field in mapping.items():
        if not field:
            continue
        v = raw.get(src)
        originals[field] = None if v is None else str(v)
        ftype = FIELD_MAP[field]["type"]
        if ftype == "number":
            values[field] = parse_number(v)
        elif ftype == "date":
            values[field] = parse_date(v)
        else:
            values[field] = None if v is None else str(v).strip()
    return values, originals


def business_key(partner_code, v):
    return "|".join(str(x) for x in [partner_code, v.get("store_code"), v.get("sale_date"), v.get("sku"), v.get("invoice_no"),
                                      v.get("quantity"), v.get("net_amount")])


def _norm_code(s):
    return "".join(ch for ch in str(s or "").upper() if ch.isalnum())


class ValidationContext:
    def __init__(self, partner, rules, stores, skus, existing_keys):
        self.partner = partner
        self.rules = {r["code"]: r for r in rules if r.get("enabled", True)}
        self.store_by_code = {}
        for s in stores:
            self.store_by_code[_norm_code(s["code"])] = s
            for a in s.get("aliases", []):
                self.store_by_code[_norm_code(a)] = s
        self.store_choices = {f"{s['code']} {s['name']}": s for s in stores}
        self.sku_by_code = {}
        for k in skus:
            self.sku_by_code[_norm_code(k["code"])] = k
            for a in k.get("aliases", []):
                self.sku_by_code[_norm_code(a)] = k
        self.existing_keys = set(existing_keys)
        self.seen_keys = set()
        self.today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def resolve_store(self, code):
        return self.store_by_code.get(_norm_code(code))

    def resolve_sku(self, code):
        hit = self.sku_by_code.get(_norm_code(code))
        if hit is None and code is not None:
            import re
            for m in re.finditer(r"(?<!\d)0?(\d{7})(?!\d)", str(code)):
                hit = self.sku_by_code.get(m.group(1))
                if hit:
                    break
        return hit


def validate_row(row: dict, ctx: ValidationContext):
    """Mutates row['issues'] and row['status']. Returns list of issues."""
    v, o = row["values"], row["original_values"]
    issues = []

    def add(code, field, msg, proposed=None):
        rule = ctx.rules.get(code)
        if not rule:
            return
        issues.append({"rule_code": code, "severity": rule["severity"], "blocking": rule.get("blocking", False), "field": field,
                       "message": msg, "original_value": o.get(field), "proposed_value": proposed})

    for f in ("sale_date", "store_code", "sku", "quantity", "net_amount"):
        if v.get(f) is None and not o.get(f):
            add("REQUIRED_FIELD", f, f"{FIELD_MAP[f]['label']} is missing")
    price_derived = False
    if v.get("unit_price") is None and not o.get("unit_price"):
        q0, n0 = v.get("quantity"), v.get("net_amount")
        if v.get("mrp"):
            v["unit_price"], price_derived = v["mrp"], True
        elif q0 and n0 is not None and q0 > 0:
            v["unit_price"], price_derived = round((n0 + (v.get("discount") or 0)) / q0, 2), True
    if o.get("sale_date") and v.get("sale_date") is None:
        add("INVALID_DATE", "sale_date", f"Could not parse date '{o['sale_date']}'")
    elif v.get("sale_date") and v["sale_date"] > ctx.today:
        add("FUTURE_DATE", "sale_date", f"Sale date {v['sale_date']} is in the future")
    if v.get("store_code"):
        st = ctx.resolve_store(v["store_code"])
        if st:
            row["resolved_store"] = {"code": st["code"], "name": st["name"], "city": st.get("city"), "region": st.get("region"), "cluster_manager": st.get("cluster_manager")}
        else:
            proposed = None
            query = f"{v['store_code']} {v.get('store_name') or ''}".strip()
            thr = ctx.rules.get("UNKNOWN_STORE", {}).get("params", {}).get("fuzzy_threshold", 80)
            if ctx.store_choices:
                m = process.extractOne(query, list(ctx.store_choices.keys()), scorer=fuzz.token_set_ratio)
                if m and m[1] >= thr:
                    proposed = ctx.store_choices[m[0]]["code"]
            add("UNKNOWN_STORE", "store_code", f"Store '{v['store_code']}' not in {ctx.partner['name']} store master", proposed)
    if v.get("sku"):
        sk = ctx.resolve_sku(v["sku"])
        if sk:
            row["resolved_sku"] = {"code": sk["code"], "name": sk["name"], "category": sk.get("category"), "brand": sk.get("brand")}
        else:
            proposed = None
            digits = "".join(ch for ch in str(v["sku"]) if ch.isdigit())
            if digits and _norm_code(digits) in ctx.sku_by_code:
                proposed = ctx.sku_by_code[_norm_code(digits)]["code"]
            add("UNKNOWN_SKU", "sku", f"Article '{v['sku']}' not in Bata article master", proposed)
    q = v.get("quantity")
    allow_ret = ctx.rules.get("NEGATIVE_QTY", {}).get("params", {}).get("allow_returns", True)
    if o.get("quantity") and q is None:
        add("NEGATIVE_QTY", "quantity", f"Quantity '{o['quantity']}' is not numeric")
    elif q is not None and q == 0:
        add("NEGATIVE_QTY", "quantity", "Quantity is zero")
    elif q is not None and q < 0 and not allow_ret:
        add("NEGATIVE_QTY", "quantity", f"Quantity {q:g} is not positive (returns disabled)", abs(q))
    elif q is not None and q < 0:
        add("NEGATIVE_QTY", "quantity", f"Return line: quantity {q:g}")
    p = v.get("unit_price")
    if p is not None and q is not None and q < 0 and p < 0:
        p = abs(p)
        v["unit_price"] = p
    if o.get("unit_price") and p is None and not price_derived:
        add("INVALID_PRICE", "unit_price", f"Unit price '{o['unit_price']}' is not numeric")
    elif p is not None and p <= 0:
        add("INVALID_PRICE", "unit_price", f"Unit price {p:g} is not positive")
    disc = v.get("discount") or 0.0
    tax = v.get("tax") or 0.0
    net = v.get("net_amount")
    if q and p and q != 0 and p > 0:
        gross = q * p
        max_pct = ctx.rules.get("DISCOUNT_OVER_LIMIT", {}).get("params", {}).get("max_pct", 60)
        if gross > 0 and disc / gross * 100 > max_pct:
            add("DISCOUNT_OVER_LIMIT", "discount", f"Discount {disc:.2f} is {disc / gross * 100:.0f}% of gross {gross:.2f} (limit {max_pct}%)")
        if net is not None and not price_derived:
            expected = round(gross - disc + tax, 2)
            expected_incl = round(gross - disc, 2)
            tol = ctx.rules.get("ARITHMETIC_MISMATCH", {}).get("params", {}).get("tolerance", 1.0)
            if abs(expected - net) > tol and abs(expected_incl - net) > tol:
                add("ARITHMETIC_MISMATCH", "net_amount", f"qty×price−disc+tax = {expected:.2f} but net is {net:.2f}", expected)
    key = business_key(ctx.partner["code"], v)
    row["business_key"] = key
    if key in ctx.existing_keys or key in ctx.seen_keys:
        add("DUPLICATE_ROW", "invoice_no", "Identical transaction already ingested (business key match)")
    ctx.seen_keys.add(key)
    row["issues"] = issues
    if any(i["blocking"] for i in issues):
        row["status"] = "rejected"
    elif any(i["rule_code"] == "DUPLICATE_ROW" for i in issues):
        row["status"] = "duplicate"
    elif issues:
        row["status"] = "warning"
    else:
        row["status"] = "accepted"
    return issues
