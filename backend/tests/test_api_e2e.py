"""End-to-end API tests for Bata SIS platform - hits the public backend URL."""
import io
import os
import time
import hashlib
from datetime import datetime, timedelta

import pytest
import requests
import openpyxl

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://partner-sync-38.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=30)
    return r


@pytest.fixture(scope="session")
def admin_token():
    r = _login("admin", "Admin@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def ops_token():
    r = _login("ops", "Ops@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def mgmt_token():
    r = _login("mgmt", "Mgmt@123")
    assert r.status_code == 200, r.text
    return r.json()["token"]


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------------------- AUTH ----------------------
class TestAuth:
    def test_login_invalid(self):
        r = _login("admin", "wrong")
        assert r.status_code == 401

    def test_login_valid_roles(self, admin_token, ops_token, mgmt_token):
        assert admin_token and ops_token and mgmt_token

    def test_me(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=h(admin_token))
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_mgmt_forbidden_uploads(self, mgmt_token):
        # Attempting upload endpoint should be forbidden
        files = {"file": ("t.txt", b"abc", "text/plain")}
        r = requests.post(f"{API}/uploads", headers=h(mgmt_token), files=files, data={"partner_code": ""})
        assert r.status_code in (400, 403), r.text

    def test_ops_forbidden_masters_create(self, ops_token):
        r = requests.post(f"{API}/masters/stores", headers=h(ops_token), json={"code": "TS999", "name": "x", "partner_code": "SHOPPERS"})
        assert r.status_code == 403


# ---------------------- DASHBOARD / REPORTS ----------------------
class TestDashboard:
    def test_dashboard(self, admin_token):
        r = requests.get(f"{API}/dashboard", headers=h(admin_token))
        assert r.status_code == 200
        d = r.json()
        assert d.get("as_of") == "2026-08-09"
        assert "kpis" in d
        k = d["kpis"]
        for key in ("mtd_sales", "active_partners", "acceptance_pct", "target_wk", "achievement_pct"):
            assert key in k
        assert k["target_wk"] > 0
        assert 60 <= k["achievement_pct"] <= 80  # ~69.7
        assert isinstance(d.get("weekly"), list) and len(d["weekly"]) > 0

    def test_reports_list_has_15(self, admin_token):
        r = requests.get(f"{API}/reports", headers=h(admin_token))
        assert r.status_code == 200
        keys = [x["key"] for x in r.json()]
        assert len(keys) == 15, f"expected 15 reports, got {len(keys)}: {keys}"
        expected = ["daily_sales", "monthly_sales", "partner_performance", "store_performance",
                    "region_performance", "category_performance", "sku_performance", "top_bottom",
                    "discount_analysis", "data_quality_trend", "missing_submissions", "exception_summary",
                    "target_vs_actual", "stock_position", "partner_margin"]
        for e in expected:
            assert e in keys, f"missing {e}"

    @pytest.mark.parametrize("key", ["daily_sales", "monthly_sales", "partner_performance", "store_performance",
                                     "region_performance", "category_performance", "sku_performance", "top_bottom",
                                     "discount_analysis", "data_quality_trend", "missing_submissions", "exception_summary",
                                     "target_vs_actual", "stock_position", "partner_margin"])
    def test_each_report(self, admin_token, key):
        r = requests.get(f"{API}/reports/{key}", headers=h(admin_token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "columns" in data and "rows" in data
        # These 3 must have rows
        if key in ("target_vs_actual", "stock_position", "partner_margin", "partner_performance", "sku_performance"):
            assert len(data["rows"]) > 0, f"{key} has no rows"

    def test_target_vs_actual_export_csv(self, admin_token):
        r = requests.get(f"{API}/reports/target_vs_actual/export?fmt=csv", headers=h(admin_token))
        assert r.status_code == 200
        assert r.content and len(r.content) > 20

    def test_target_vs_actual_export_xlsx(self, admin_token):
        r = requests.get(f"{API}/reports/target_vs_actual/export?fmt=xlsx", headers=h(admin_token))
        assert r.status_code == 200
        assert len(r.content) > 100

    def test_report_export_csv(self, admin_token):
        r = requests.get(f"{API}/reports/daily_sales/export?fmt=csv", headers=h(admin_token))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower() or r.content

    def test_report_export_xlsx(self, admin_token):
        r = requests.get(f"{API}/reports/daily_sales/export?fmt=xlsx", headers=h(admin_token))
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_report_records_paginate(self, admin_token):
        r = requests.get(f"{API}/reports/records?limit=5&offset=0", headers=h(admin_token))
        assert r.status_code == 200
        assert "items" in r.json() or "rows" in r.json()


# ---------------------- BATCHES / INSIGHTS / AUDIT ----------------------
class TestListings:
    def test_batches_list(self, admin_token):
        r = requests.get(f"{API}/batches?limit=20", headers=h(admin_token))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_insights(self, admin_token):
        r = requests.get(f"{API}/insights", headers=h(admin_token))
        assert r.status_code == 200
        assert "items" in r.json()

    def test_audit(self, admin_token):
        r = requests.get(f"{API}/audit-logs?page_size=20", headers=h(admin_token))
        assert r.status_code == 200

    def test_notifications(self, admin_token):
        r = requests.get(f"{API}/notifications", headers=h(admin_token))
        assert r.status_code == 200

    def test_partners(self, admin_token):
        r = requests.get(f"{API}/partners", headers=h(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 10
        codes = {p["code"] for p in data}
        for c in ("CENTRO", "INC5", "KORA", "LIFESTYLE", "LULU", "RCENTRAL", "RTRENDS", "SHOPPERS", "SPENCER", "ZUUP"):
            assert c in codes, f"missing partner {c}"

    def test_masters_partners_with_margins(self, admin_token):
        r = requests.get(f"{API}/masters/partners", headers=h(admin_token))
        assert r.status_code == 200
        data = r.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        assert len(items) == 10
        # at least some have margins
        with_margin = [p for p in items if p.get("margins")]
        assert len(with_margin) >= 8

    def test_masters_stores_partner_filter_and_aliases(self, admin_token):
        r = requests.get(f"{API}/masters/stores?partner_code=INC5&limit=5", headers=h(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data.get("total", 0) > 0
        # at least one store has aliases
        assert any(s.get("aliases") for s in data.get("items", []))

    def test_masters_skus_large(self, admin_token):
        r = requests.get(f"{API}/masters/skus?limit=1", headers=h(admin_token))
        assert r.status_code == 200
        assert r.json().get("total", 0) > 2000

    def test_insights_contains_spencer(self, admin_token):
        r = requests.get(f"{API}/insights", headers=h(admin_token))
        assert r.status_code == 200
        titles = [i.get("title", "") for i in r.json().get("items", [])]
        assert any("SPENCER" in t for t in titles), f"no SPENCER missing-submission insight: {titles[:5]}"

    def test_exceptions_unknown_sku(self, admin_token):
        r = requests.get(f"{API}/exceptions?rule_code=UNKNOWN_SKU&limit=5", headers=h(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data.get("total", 0) > 100

    def test_fields(self, admin_token):
        r = requests.get(f"{API}/fields", headers=h(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 5


# ---------------------- MASTERS ----------------------
class TestMasters:
    @pytest.mark.parametrize("tab", ["stores", "skus", "hierarchy", "geo", "aliases", "rules", "sender_rules"])
    def test_masters_lists(self, admin_token, tab):
        r = requests.get(f"{API}/masters/{tab}?limit=5", headers=h(admin_token))
        assert r.status_code == 200, f"{tab}: {r.text}"

    def test_store_create_duplicate(self, admin_token):
        payload = {"code": "TEST_STORE_A", "name": "Test Store A", "partner_code": "SHOPPERS", "city": "Mumbai", "state": "MH", "region": "West"}
        r = requests.post(f"{API}/masters/stores", headers=h(admin_token), json=payload)
        # accept 200/201 first time or 409 if exists
        assert r.status_code in (200, 201, 409), r.text
        r2 = requests.post(f"{API}/masters/stores", headers=h(admin_token), json=payload)
        assert r2.status_code == 409


# ---------------------- UPLOAD FLOW ----------------------
def _make_shoppers_xlsx():
    """Generate a SHOPPERS-format xlsx with 3 valid rows matching seeded article FMBA8713334."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    headers = ["Partner", "Location", "Style Code", "Selling Date", "Brand Name",
               "Sub Category", "Colour Desc", "Size Desc", "Qty Sold",
               "MRP Per Unit", "Disc Amt", "Net Retail Value", "Store No."]
    ws.append(headers)
    for i in range(3):
        ws.append(["SHOPPERS", "PITAMPURA METRO", "FMBA8713334", "2026-08-12",
                   "BATA", "SHOES", "BLACK", "8", 1, 1099, 0, 1099, 101])
    return wb


class TestUploadFlow:
    def test_upload_txt_rejected(self, ops_token):
        files = {"file": ("bad.txt", b"hello", "text/plain")}
        r = requests.post(f"{API}/uploads", headers=h(ops_token), files=files)
        assert r.status_code == 400

    def test_upload_shoppers_success_then_reject(self, ops_token):
        wb = _make_shoppers_xlsx()
        buf = io.BytesIO()
        wb.save(buf)
        content = buf.getvalue()

        # Add a random tail to avoid duplicate hash collision on reruns
        content_unique = content + b" " * (int(time.time()) % 97 + 1)
        files = {"file": (f"SHOPPERS_test_{int(time.time())}.xlsx", content_unique,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/uploads", headers=h(ops_token), files=files)
        assert r.status_code in (200, 201), r.text
        batch_id = r.json().get("id") or r.json().get("batch_id")
        assert batch_id

        # Poll status
        final = None
        detected = None
        for _ in range(30):
            time.sleep(1)
            b = requests.get(f"{API}/batches/{batch_id}", headers=h(ops_token)).json()
            final = b.get("status")
            detected = b.get("partner_code")
            if final and final not in ("Analysing", "Validating", "Queued", "Uploaded"):
                break
        assert final in ("Successfully Processed", "Partially Processed", "Awaiting Review"), f"Got status={final}"
        assert (detected or "").upper() == "SHOPPERS", f"expected SHOPPERS auto-detect, got {detected}"

        # Reject the batch to keep data clean
        rj = requests.post(f"{API}/batches/{batch_id}/reject", headers=h(ops_token), json={"reason": "test cleanup"})
        assert rj.status_code in (200, 204, 202), f"reject failed: {rj.status_code} {rj.text}"

    def test_upload_preview(self, ops_token):
        wb = _make_shoppers_xlsx()
        buf = io.BytesIO(); wb.save(buf)
        files = {"file": ("preview.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/uploads/preview", headers=h(ops_token), files=files)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "sheets" in data


# ---------------------- SETTINGS ----------------------
class TestSettings:
    def test_get_settings(self, admin_token):
        r = requests.get(f"{API}/settings", headers=h(admin_token))
        assert r.status_code == 200

    def test_put_settings(self, admin_token):
        # Get then put back
        cur = requests.get(f"{API}/settings", headers=h(admin_token)).json()
        r = requests.put(f"{API}/settings", headers=h(admin_token), json=cur)
        assert r.status_code in (200, 204)


# ---------------------- USERS ----------------------
class TestUsers:
    def test_list_users_admin(self, admin_token):
        r = requests.get(f"{API}/users", headers=h(admin_token))
        assert r.status_code == 200

    def test_users_forbidden_ops(self, ops_token):
        r = requests.get(f"{API}/users", headers=h(ops_token))
        assert r.status_code == 403

    def test_short_password_rejected(self, admin_token):
        r = requests.post(f"{API}/users", headers=h(admin_token),
                          json={"username": "TEST_shortpw", "password": "abc", "email": "t@t.com", "name": "t", "role": "ops"})
        assert r.status_code == 400
