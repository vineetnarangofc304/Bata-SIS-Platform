from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

import os
import asyncio
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from core.db import db, client
from core.storage import init_storage
from routers import auth_users, ingestion, masters, analytics
import seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("server")

app = FastAPI(title="Bata SIS Sales Intelligence Platform")
api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"service": "Bata SIS Sales Intelligence API", "status": "ok"}


@api.get("/health")
async def health():
    return {"status": "ok"}


api.include_router(auth_users.router)
api.include_router(ingestion.router)
api.include_router(masters.router)
api.include_router(analytics.router)
app.include_router(api)

app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


async def ensure_indexes():
    await db.users.create_index("username", unique=True)
    await db.users.create_index("id", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.batches.create_index("id", unique=True)
    await db.batches.create_index([("created_at", -1)])
    await db.batches.create_index([("partner_code", 1), ("status", 1)])
    await db.batches.create_index("file_hash")
    await db.raw_rows.create_index([("batch_id", 1), ("row_index", 1)])
    await db.std_rows.create_index([("batch_id", 1), ("is_current", 1), ("status", 1)])
    await db.std_rows.create_index("raw_row_id")
    await db.std_rows.create_index("id", unique=True)
    await db.sales.create_index("id", unique=True)
    await db.sales.create_index([("partner_code", 1), ("sale_date", 1)])
    await db.sales.create_index("batch_id")
    await db.sales.create_index("business_key")
    await db.sales.create_index([("store_code", 1), ("sale_date", 1)])
    await db.sales.create_index([("sku", 1), ("sale_date", 1)])
    await db.exceptions.create_index([("status", 1), ("created_at", -1)])
    await db.exceptions.create_index("batch_id")
    await db.exceptions.create_index("raw_row_id")
    await db.exceptions.create_index("id", unique=True)
    await db.audit_logs.create_index([("created_at", -1)])
    await db.audit_logs.create_index("batch_id")
    await db.notifications.create_index([("created_at", -1)])
    await db.aliases.create_index([("alias_norm", 1), ("partner_code", 1)])
    await db.partner_mappings.create_index([("partner_code", 1), ("version", -1)])
    await db.stores.create_index([("partner_code", 1), ("code", 1)])
    await db.skus.create_index("code")


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    try:
        await asyncio.to_thread(init_storage)
        logger.info("Object storage initialised")
    except Exception as e:
        logger.error(f"Object storage init failed: {e}")
    asyncio.create_task(_seed_safe())


async def _seed_safe():
    try:
        await seed.seed()
    except Exception as e:
        logger.exception(f"Seed failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
