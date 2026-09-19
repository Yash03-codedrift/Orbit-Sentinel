import os
import logging
import asyncio
import contextlib
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Settings loading
from backend.config import settings

# Database client functions
from backend.db.mongo_client import init_db, close_db

# Scheduler wrapper
from backend.core.scheduler import sentinel_scheduler

# ML modules initialization
from backend.ml.collision_probability_ann import initialize_ann, ann_model
from backend.ml.trajectory_lstm import initialize_lstm, lstm_predictor
from backend.ml.rl_maneuver_agent import initialize_rl_agent, rl_agent

# TLE operations
from backend.core.tle_ingestion import run_tle_ingestion_job, get_cached_tles

# Routers
from backend.routers.history_router import router as history_router
from backend.routers import (
    tle_router,
    conjunction_router,
    maneuver_router,
    satellite_router,
    audit_router,
    analytics_router,
    websocket_router,
    risk_config_router
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("orbit_sentinel.main")

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages FastAPI lifespan hooks: initializes MongoClient, loads machine learning algorithms,
    pre-populates dry-run orbital catalogs, and flags up periodic check routines.
    """
    logger.info("Orbit Sentinel booting up...")

    if settings.WEBHOOK_SECRET == "changeme" or settings.API_KEY == "changeme":
        logger.warning(
            "SECURITY WARNING: WEBHOOK_SECRET/API_KEY are still default values. "
            "Set real secrets in .env before any non-local deployment."
        )

    # 1. Establish and secure database connection
    db_uri = os.environ.get("MONGODB_URI", settings.MONGODB_URI)
    db_name = os.environ.get("MONGODB_DB_NAME", settings.MONGODB_DB_NAME)
    db = await init_db(db_uri, db_name)
    app.state.db = db
    
    # 2. Warm up machine learning parameters in parallel, prevent failure crashes
    try:
        logger.info("Warming up system neural models...")
        await asyncio.gather(
            initialize_ann(),
            initialize_lstm(),
            initialize_rl_agent()
        )
        logger.info("All neural models loaded and initialized successfully.")
    except Exception as ml_err:
        logger.error(f"Error during baseline ML model initialization sequence: {ml_err}", exc_info=True)
        
    # 3. Check if standard satellite catalogs are empty and preload them during first-run scenarios
    try:
        sat_count = await db["satellites"].count_documents({})
        if sat_count == 0:
            logger.info("Spacecraft catalogs detected empty. Launching automated catalog ingestion pipeline...")
            await run_tle_ingestion_job(db)
        else:
            logger.info(f"Existing tracking catalogs verified database. Logged: {sat_count} records.")
    except Exception as ing_err:
        logger.error(f"Failed carrying out catalog first-run validation sync: {ing_err}", exc_info=True)
        
    # 4. Bind scheduler triggers and turn process threads on
    try:
        await sentinel_scheduler.initialize(db)
    except Exception as sched_err:
        logger.error(f"Failed establishing scheduler queues: {sched_err}", exc_info=True)
        
    logger.info("------ ORBIT SENTINEL ONLINE ------")
    # Write startup audit entry so the log is never empty on first load
    try:
        from backend.db import audit_repo
        from backend.db.mongo_client import get_db as get_db_func
        db = get_db_func()
        if db is not None:
            await audit_repo.append_audit_entry(db, {
                "timestamp": datetime.now(timezone.utc),
                "action_type": "SYSTEM_STARTUP",
                "actor": "ORBIT_SENTINEL_AUTONOMOUS",
                "outcome": "SUCCESS",
                "severity": "INFO",
                "details": "Orbit Sentinel system initialized. Sentinel active.",
                "notes": "Backend startup complete."
            })
    except Exception as audit_err:
        logger.error(f"Failed writing startup audit entry: {audit_err}", exc_info=True)

    yield
    
    # 5. Safe, clean shutdown and garbage collection
    logger.info("Deactivating Sentinel background processes...")
    try:
        sentinel_scheduler.stop()
    except Exception as sched_stop_err:
        logger.error(f"Error while disabling active schedules: {sched_stop_err}")
        
    close_db()
    logger.info("------ ORBIT SENTINEL SHUTDOWN ------")

# App Setup
app = FastAPI(title="Orbit Sentinel", version="1.0.0", lifespan=lifespan)

# CORS Middleware setup
_dev_origins = ["http://localhost:5173", "http://localhost:3000"] if settings.ENV != "production" else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, *_dev_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route mappings
app.include_router(history_router, prefix="/api/history", tags=["Historical Scenarios"])
app.include_router(tle_router.router, prefix="/api/tle", tags=["TLE"])
app.include_router(conjunction_router.router, prefix="/api/conjunctions", tags=["Conjunctions"])
app.include_router(maneuver_router.router, prefix="/api/maneuvers", tags=["Maneuvers"])
app.include_router(satellite_router.router, prefix="/api/satellites", tags=["Satellites"])
app.include_router(audit_router.router, prefix="/api/audit", tags=["Audit Log"])
app.include_router(analytics_router.router, prefix="/api/analytics", tags=["Analytics & AI"])
app.include_router(risk_config_router.router, prefix="/api/risk-config", tags=["Risk Configuration"])
app.include_router(websocket_router.router, tags=["Real-time Sync"])

@app.get("/health")
async def health_check(request: Request):
    """
    Returns automated service health metrics, scheduler diagnostics, and current ML training flags.
    """
    db = request.app.state.db
    
    # 1. Fetch TLE last update
    last_tle_pull = None
    try:
        last_snapshot = await db["tle_snapshots"].find({}).sort("fetched_at", -1).to_list(length=1)
        last_snapshot = last_snapshot[0] if last_snapshot else None
        if last_snapshot:
            fetched = last_snapshot.get("fetched_at")
            if isinstance(fetched, datetime):
                last_tle_pull = fetched.isoformat()
            elif isinstance(fetched, str):
                last_tle_pull = fetched
    except Exception as e:
        logger.debug(f"Failed retrieving last TLE snapshot: {e}")

    # Fallback — read last_updated from satellites collection
    if not last_tle_pull:
        try:
            sats = await db["satellites"].find({}).sort("last_updated", -1).to_list(length=1)
            if sats:
                lu = sats[0].get("last_updated")
                if isinstance(lu, datetime):
                    last_tle_pull = lu.isoformat()
                elif isinstance(lu, str):
                    last_tle_pull = lu
        except Exception:
            pass
        
    # 2. Extract collection totals
    try:
        total_objects = await db["satellites"].count_documents({})
        active_conjs = await db["conjunctions"].count_documents({"resolved": False})
    except Exception as e:
        logger.error(f"Could not connect to database for health check counts: {e}")
        total_objects, active_conjs = 0, 0
        
    # 3. Determine scheduler status
    scheduler_status = "STOPPED"
    try:
        if sentinel_scheduler.scheduler and sentinel_scheduler.scheduler.running:
            scheduler_status = "RUNNING"
    except Exception:
        pass
        
    return {
        "status": "SENTINEL_ACTIVE",
        "last_tle_pull": last_tle_pull,
        "total_objects_tracked": total_objects,
        "active_conjunctions": active_conjs,
        "scheduler_status": scheduler_status,
        "ml_models": {
            "ann": getattr(ann_model, "is_trained", False),
            "lstm": getattr(lstm_predictor, "is_trained", False),
            "rl_agent": getattr(rl_agent, "is_trained", False)
        }
    }

@app.get("/")
async def root_ping():
    """
    Primary API entrypoint ping endpoint.
    """
    return {
        "message": "Orbit Sentinel API", 
        "docs": "/docs"
    }
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)