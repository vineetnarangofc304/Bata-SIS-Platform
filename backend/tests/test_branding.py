"""Branding & preview meta tag tests for Bata SIS."""
import os
import re
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://partner-sync-38.preview.emergentagent.com"


@pytest.fixture(scope="module")
def html():
    r = requests.get(BASE + "/", timeout=30)
    assert r.status_code == 200
    return r.text


def test_title_is_bata(html):
    m = re.search(r"<title>([^<]+)</title>", html)
    assert m and m.group(1).strip() == "Bata SIS Sales Intelligence"


def test_description_mentions_bata(html):
    m = re.search(r'<meta name="description" content="([^"]+)"', html)
    assert m and "Bata" in m.group(1)


@pytest.mark.parametrize("tag", [
    'property="og:title"',
    'property="og:description"',
    'property="og:image"',
    'name="twitter:card"',
])
def test_meta_tags_present(html, tag):
    assert tag in html, f"Missing meta {tag}"


def test_og_url_present(html):
    # og:url is mentioned in review requirements
    assert 'property="og:url"' in html, "og:url meta tag is missing"


def test_no_emergent_in_html(html):
    # Case-insensitive check for 'emergent'
    assert not re.search(r"emergent", html, re.IGNORECASE), "'emergent' still appears in HTML"


def test_no_posthog(html):
    assert "posthog" not in html.lower()


@pytest.mark.parametrize("path,ctype_substr", [
    ("/og-image.png", "image/png"),
    ("/favicon.svg", "svg"),
    ("/manifest.json", "json"),
    ("/bata-logo.svg", "svg"),
    ("/bata-logo-white.svg", "svg"),
])
def test_static_assets(path, ctype_substr):
    r = requests.get(BASE + path, timeout=30)
    assert r.status_code == 200, f"{path} returned {r.status_code}"
    assert ctype_substr in r.headers.get("content-type", "").lower(), f"{path} ctype={r.headers.get('content-type')}"


def test_manifest_name_has_bata():
    r = requests.get(BASE + "/manifest.json", timeout=30)
    j = r.json()
    assert "Bata" in j.get("name", "")


# --- Regression smoke ---

@pytest.fixture(scope="module")
def token():
    r = requests.post(BASE + "/api/auth/login", json={"username": "admin", "password": "Admin@123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_batches(token):
    r = requests.get(BASE + "/api/batches", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


def test_reports_15(token):
    r = requests.get(BASE + "/api/reports", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("reports") or []
    assert len(items) == 15, f"Expected 15 reports, got {len(items)}"
