import io
import hashlib
from datetime import date, timedelta
from openpyxl import Workbook
from services.parser import parse_file, detect_header_row, extract_rows, parse_number, parse_date, infer_type
from services.recognition import normalize, map_columns, compute_overall, REQUIRED_FIELDS, CANONICAL_FIELDS
from services.validation import standardize_row, validate_row, ValidationContext, DEFAULT_RULES, business_key

ALIASES = {normalize(a): f for f, arr in {"sale_date": ["bill date"], "store_code": ["store code"], "sku": ["article code"], "quantity": ["qty"],
                                          "unit_price": ["selling price"], "net_amount": ["net amount"], "discount": ["discount"], "tax": ["gst amount"], "invoice_no": ["bill no"]}.items() for a in arr}
for f in CANONICAL_FIELDS:
    ALIASES[normalize(f["label"])] = f["key"]
HEADERS = ["Bill Date", "Store Code", "Article Code", "Qty", "Selling Price", "Discount", "GST Amount", "Net Amount", "Bill No"]


def make_xlsx(rows, intro=True):
    wb = Workbook()
    ws = wb.active
    if intro:
        ws.append(["Partner Sales Report"])
        ws.append([])
    ws.append(HEADERS)
    for r in rows:
        ws.append(r)
    ws.append(["Grand Total", None, None, sum(r[3] for r in rows)])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


ROWS = [["05/06/2026", "SS001", "8210101", 2, "1,999", 0, 479.76, 4477.76, "B1"], ["05/06/2026", "SS001", "8210138", 1, 2499, 249.9, 269.89, 2518.99, "B2"]]


def test_parser_header_detection_and_totals():
    sheets = parse_file("test.xlsx", make_xlsx(ROWS))
    idx, conf = detect_header_row(sheets[0]["rows"], set(ALIASES), normalize)
    assert idx == 2 and conf > 80
    headers, data, skipped = extract_rows(sheets[0]["rows"], idx)
    assert headers == HEADERS and len(data) == 2 and skipped["totals"] == 1


def test_number_and_date_coercion():
    assert parse_number("1,999") == 1999 and parse_number("₹1,200.50") == 1200.5 and parse_number("(12)") == -12 and parse_number("abc") is None
    assert parse_date("05/06/2026") == "2026-06-05" and parse_date("5-Jun-26") == "2026-06-05" and parse_date("20260605") == "2026-06-05"
    assert parse_date("31/02/2026") is None and parse_date(45000) == "2023-03-15"
    assert infer_type(["1,999", "2499"]) == "number" and infer_type(["05/06/2026", "06/06/2026"]) == "date"


def test_column_mapping_exact_alias_fuzzy_learned():
    headers = ["Bill Date", "Qty Sold", "Net Amt Value", "Zzz", "Article Code"]
    samples = [{"Bill Date": "05/06/2026", "Qty Sold": 2, "Net Amt Value": 100.0, "Zzz": "x", "Article Code": "8210101"}]
    cols = map_columns(headers, samples, ALIASES, {normalize("Zzz"): {"field": "store_code", "version": 3}})
    by = {c["source_column"]: c for c in cols}
    assert by["Bill Date"]["proposed_field"] == "sale_date" and by["Bill Date"]["confidence"] >= 94
    assert by["Qty Sold"]["proposed_field"] == "quantity" and 60 <= by["Qty Sold"]["confidence"] < 94
    assert by["Zzz"]["proposed_field"] == "store_code" and "Previously approved" in by["Zzz"]["reason"]
    assert by["Article Code"]["proposed_field"] == "sku"
    conf = compute_overall(100, 90, cols, {"high": 90, "medium": 70})
    assert "net_amount" in conf["missing_required"] and conf["level"] == "low"


def ctx(existing=()):
    partner = {"code": "SS", "name": "Shoppers Stop", "partial_ingestion": True}
    rules = [{**r, "enabled": True} for r in DEFAULT_RULES]
    stores = [{"code": "SS001", "name": "Shoppers Stop Mumbai", "aliases": ["SS-MUM-1"]}]
    skus = [{"code": "8210101", "name": "Derby", "aliases": []}]
    return ValidationContext(partner, rules, stores, skus, existing)


def std(raw):
    mapping = {"Bill Date": "sale_date", "Store Code": "store_code", "Article Code": "sku", "Qty": "quantity", "Selling Price": "unit_price", "Discount": "discount", "GST Amount": "tax", "Net Amount": "net_amount", "Bill No": "invoice_no"}
    v, o = standardize_row(raw, mapping)
    return {"values": v, "original_values": o}


def test_validation_rules():
    good = std(dict(zip(HEADERS, ["05/06/2026", "SS-MUM-1", "8210101", "2", "1,000", 100, 12, 1912, "B1"])))
    c = ctx()
    validate_row(good, c)
    assert good["status"] == "accepted" and good["resolved_store"]["code"] == "SS001"
    bad = std(dict(zip(HEADERS, ["31/02/2026", "XX9", "999", -1, 0, 900, 0, 5, "B2"])))
    validate_row(bad, c)
    codes = {i["rule_code"] for i in bad["issues"]}
    assert {"INVALID_DATE", "UNKNOWN_STORE", "UNKNOWN_SKU", "NEGATIVE_QTY", "INVALID_PRICE"} <= codes and bad["status"] == "rejected"
    future = std(dict(zip(HEADERS, [(date.today() + timedelta(days=5)).strftime("%d/%m/%Y"), "SS001", "8210101", 1, 100, 0, 0, 100, "B3"])))
    validate_row(future, c)
    assert any(i["rule_code"] == "FUTURE_DATE" for i in future["issues"])
    warn = std(dict(zip(HEADERS, ["05/06/2026", "SS001", "8210101", 1, 1000, 700, 0, 500, "B4"])))
    validate_row(warn, c)
    codes = {i["rule_code"] for i in warn["issues"]}
    assert {"DISCOUNT_OVER_LIMIT", "ARITHMETIC_MISMATCH"} <= codes and warn["status"] == "warning"
    assert next(i for i in warn["issues"] if i["rule_code"] == "ARITHMETIC_MISMATCH")["proposed_value"] == 300.0


def test_dedup_business_key_and_file_hash():
    r1 = std(dict(zip(HEADERS, ["05/06/2026", "SS001", "8210101", 1, 100, 0, 0, 100, "B1"])))
    c = ctx()
    validate_row(r1, c)
    r2 = std(dict(zip(HEADERS, ["05/06/2026", "SS001", "8210101", 1, 100, 0, 0, 100, "B1"])))
    validate_row(r2, c)
    assert r2["status"] == "duplicate" and r1["business_key"] == r2["business_key"]
    c2 = ctx(existing=[business_key("SS", r1["values"])])
    r3 = std(dict(zip(HEADERS, ["05/06/2026", "SS001", "8210101", 1, 100, 0, 0, 100, "B1"])))
    validate_row(r3, c2)
    assert any(i["rule_code"] == "DUPLICATE_ROW" for i in r3["issues"])
    a, b = make_xlsx(ROWS), make_xlsx(ROWS)
    assert hashlib.sha256(a).hexdigest() != "" and parse_file("a.xlsx", a)[0]["rows"] == parse_file("b.xlsx", b)[0]["rows"]
