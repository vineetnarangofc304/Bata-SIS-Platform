import os
import logging
import requests

logger = logging.getLogger("storage")

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = os.environ.get("APP_NAME", "bata-sis")

storage_key = None


def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def _request(method, path, **kw):
    key = init_storage()
    resp = requests.request(method, f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, **kw.pop("headers", {})}, **kw)
    if resp.status_code == 404 and method == "PUT":
        key = init_storage(force=True)
        resp = requests.request(method, f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, **kw.get("headers", {})}, **kw)
    resp.raise_for_status()
    return resp


def save_file(rel_path: str, data: bytes, content_type: str) -> dict:
    path = f"{APP_NAME}/{rel_path}"
    resp = _request("PUT", path, headers={"Content-Type": content_type}, data=data, timeout=120)
    return {"path": resp.json()["path"], "backend": "object_storage"}


def load_file(path: str, backend: str = "object_storage") -> bytes:
    return _request("GET", path, timeout=60).content
