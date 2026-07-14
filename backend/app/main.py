from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from prisma import Prisma
from app.api import auth, scans, system
import logging
import sys

# Remove manual basicConfig to allow Uvicorn to handle logging
logger = logging.getLogger(__name__)

db = Prisma()


async def ensure_db_connected():
    """Ensure the database connection is alive, reconnect if needed."""
    try:
        if not db.is_connected():
            logger.warning("Database not connected. Reconnecting...")
            await db.connect()
            logger.info("Database reconnected successfully.")
        else:
            # Test the connection is actually alive (not just "thinks" it's connected)
            await db.query_raw("SELECT 1")
    except Exception as e:
        logger.error(f"Database connection test failed: {e}. Attempting reconnect...")
        try:
            # Force disconnect the stale connection, then reconnect
            try:
                await db.disconnect()
            except Exception:
                pass  # Ignore disconnect errors on stale connection
            await db.connect()
            logger.info("Database reconnected successfully after failure.")
        except Exception as reconnect_error:
            logger.critical(f"Database reconnect failed: {reconnect_error}")
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    logger.info("Database connected on startup.")
    
    # Cleanup zombie scans (scans stuck in "Running" state from previous session)
    try:
        zombie_scans = await db.scan.update_many(
            where={"status": "Running"},
            data={"status": "Failed"}
        )
        if zombie_scans > 0:
            logger.info(f"Startup Cleanup: Marked {zombie_scans} zombie scans as Failed.")
    except Exception as e:
        logger.error(f"Startup Cleanup Error: {e}")

    # CTEM M7: start the continuous-monitoring scheduler (recurring scans + KEV refresh)
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler(db)
        logger.info("Continuous-monitoring scheduler started.")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    yield

    # Shutdown: stop background work BEFORE disconnecting the DB so tasks don't
    # spam reconnect errors against a closing query engine.
    try:
        from app.services.scheduler import stop_scheduler
        await stop_scheduler()
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")

    try:
        from app.services.scan_manager import ScanManager
        active = list(ScanManager._active_scans.items())
        for scan_id, task in active:
            task.cancel()
        for scan_id, task in active:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if active:
            logger.info(f"Cancelled {len(active)} in-flight scan(s) on shutdown.")
    except Exception as e:
        logger.error(f"Failed to cancel active scans: {e}")

    try:
        await db.disconnect()
        logger.info("Database disconnected on shutdown.")
    except Exception as e:
        logger.error(f"Error disconnecting DB on shutdown: {e}")

app = FastAPI(title="Pentest Web App API", version="1.0.0", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows requests from any origin (frontend)
    allow_credentials=True, # Allows cookies/auth headers
    allow_methods=["*"], # Allows all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], # Allows all headers
)

from fastapi.staticfiles import StaticFiles
import os

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(scans.router, prefix="/scans", tags=["scans"])
app.include_router(system.router, prefix="/system", tags=["system"])
from app.api import users, admin
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
from app.api import events
app.include_router(events.router, prefix="/events", tags=["events"])
from app.api import breaches
app.include_router(breaches.router, prefix="/breaches", tags=["breaches"])
from app.api import webintel
app.include_router(webintel.router, prefix="/api/webintel", tags=["webintel"])
from app.api import ctem
app.include_router(ctem.router, prefix="/ctem", tags=["ctem"])
from app.api import schedules
app.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
from app.api import aitools
app.include_router(aitools.router, prefix="/ai-tools", tags=["ai-tools"])
from app.api import ai_scans
app.include_router(ai_scans.router, prefix="/ai-scans", tags=["ai-scans"])
from app.api import engagements
app.include_router(engagements.router, prefix="/engagements", tags=["engagements"])

# Ensure reports directory exists
os.makedirs("reports", exist_ok=True) # Ensures reports directory exists
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

@app.get("/")
def read_root():
    return {"message": "Welcome to Pentest Web App API"}

@app.get("/health")
async def health_check():
    """Health check endpoint for Azure Container Apps probes.
    Returns HTTP 503 when unhealthy so Azure knows to restart the container."""
    try:
        await db.execute_raw("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )
