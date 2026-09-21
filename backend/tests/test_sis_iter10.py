"""Iteration 10: SIS seed self-heal, reload, defaults + partner filter tests."""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login(u, p):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": u, "password": p}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_tok():
    return _login("admin", "Admin@123")


@pytest.fixture(scope="module")
def ops_tok():
    return _login("ops", "Ops@123")


def H(t):
    return {"Authorization": f"Bearer {t}"}


# --- Meta status ---
class TestMetaStatus:
    def test_meta_ready(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/meta", headers=H(admin_tok), timeout=30)
        assert r.status_code == 200
        m = r.json()
        assert m.get("status") == "ready", f"status={m.get('status')} meta={m}"
        assert m["rows"] == 218447
        assert m.get("loaded_rows") == 218447
        assert m["latest_week"] == 16
        assert m["latest_month"] == "Apr"


# --- Reload admin/ops authz ---
class TestReloadAuth:
    def test_reload_ops_forbidden(self, ops_tok):
        r = requests.post(f"{BASE}/api/sis/reload", headers=H(ops_tok), timeout=30)
        assert r.status_code == 403


# --- Sales report defaults (partner + till_date=Yes) ---
class TestPartnerDefaults:
    def test_partner_default_till_date(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report",
                         headers=H(admin_tok),
                         params={"group_by": "partner", "till_date": "Yes"},
                         timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] == 8, f"got {d['count']} partners"
        for row in d["rows"]:
            assert row.get("nsv_25") is not None
            assert row.get("nsv_26") is not None
        assert d["total"].get("nsv_g") is not None
        assert d["total"]["nsv_g"] > 0

    def test_filter_partner_centro(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report",
                         headers=H(admin_tok),
                         params={"group_by": "partner", "till_date": "Yes", "partner": "CENTRO"},
                         timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 1
        assert d["rows"][0]["partner"] == "CENTRO"

    def test_partner_month_multi(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report",
                         headers=H(admin_tok),
                         params={"group_by": "partner,month", "partner": "CENTRO"},
                         timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] > 1
        for row in d["rows"]:
            assert row.get("month") is not None

    def test_partner_week_latest_month(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/sales-report",
                         headers=H(admin_tok),
                         params={"group_by": "partner,week", "latest_month": "1"},
                         timeout=60)
        assert r.status_code == 200
        d = r.json()
        weeks = {row["week"] for row in d["rows"]}
        assert weeks.issubset({14, 15, 16}), f"weeks={weeks}"
        assert weeks  # non-empty


# --- Filters after ready ---
class TestFilters:
    def test_filters_after_ready(self, admin_tok):
        r = requests.get(f"{BASE}/api/sis/filters", headers=H(admin_tok), timeout=60)
        assert r.status_code == 200
        f = r.json()
        assert len(f["partner"]) == 8
        assert len(f["month"]) == 12
        assert len(f["week"]) == 52


# --- Reload background flow (best-effort, tolerate fast completion) ---
class TestReloadBackground:
    def test_reload_returns_quickly(self, admin_tok):
        t0 = time.time()
        r = requests.post(f"{BASE}/api/sis/reload", headers=H(admin_tok), timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        assert elapsed < 5, f"reload took {elapsed}s"
        body = r.json()
        # status may already be ready if very fast; otherwise loading
        assert body.get("status") in ("loading", "ready"), body

        # Poll meta; must reach ready within 90s. During loading, sales-report must be 200.
        deadline = time.time() + 90
        saw_status = None
        while time.time() < deadline:
            m = requests.get(f"{BASE}/api/sis/meta", headers=H(admin_tok), timeout=15).json()
            saw_status = m.get("status")
            # Even during loading, sales-report must still respond
            sr = requests.get(f"{BASE}/api/sis/sales-report",
                              headers=H(admin_tok),
                              params={"group_by": "partner", "till_date": "Yes"},
                              timeout=60)
            assert sr.status_code == 200, sr.text
            if saw_status == "ready" and m.get("rows") == 218447:
                break
            time.sleep(3)
        assert saw_status == "ready", f"final status={saw_status}"
