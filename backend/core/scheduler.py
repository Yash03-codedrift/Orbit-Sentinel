import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import settings
from backend.utils.time_utils import utc_now, datetime_to_iso
from backend.db.satellite_repo import get_all_satellites
from backend.db.conjunction_repo import insert_conjunction, get_active_conjunctions, expire_past_conjunctions
from backend.db.maneuver_repo import insert_maneuver
from backend.db.audit_repo import append_audit_entry

from backend.core.sgp4_propagator import get_propagation_timestamps, propagate_batch_python
from backend.core.conjunction_detector import detect_conjunctions, ConjunctionEvent
from backend.core.risk_scorer import score_conjunction, classify_risk_level, compute_kessler_index
from backend.db.risk_config_repo import get_risk_bands, top_severity_keys
from backend.core.maneuver_calculator import compute_optimal_maneuver
from backend.core.webhook_dispatcher import build_webhook_payload, simulate_webhook_dispatch

logger = logging.getLogger("orbit_sentinel.scheduler")

def dict_to_conjunction_event(d: dict) -> ConjunctionEvent:
    def parse_dt(val: Any) -> datetime:
        if isinstance(val, datetime): return val
        if isinstance(val, str):
            try: return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError: pass
        return utc_now()

    return ConjunctionEvent(
        detected_at=parse_dt(d.get("detected_at")),
        norad_id_a=d.get("norad_id_a", ""),
        norad_id_b=d.get("norad_id_b", ""),
        name_a=d.get("name_a", "UNKNOWN"),
        name_b=d.get("name_b", "UNKNOWN"),
        tca_utc=parse_dt(d.get("tca_utc")),
        miss_distance_km=float(d.get("miss_distance_km", 0.0)),
        relative_velocity_kmps=float(d.get("relative_velocity_kmps", 0.0)),
        collision_probability_chan=float(d.get("collision_probability_chan", 0.0)),
        event_id=d.get("event_id", ""),
        risk_score=float(d.get("risk_score", 0.0)),
        risk_level=d.get("risk_level", "LOW"),
        object_type_a=d.get("object_type_a", "UNKNOWN"),
        object_type_b=d.get("object_type_b", "UNKNOWN"),
        criticality_a=float(d.get("criticality_a", 1.0)),
        criticality_b=float(d.get("criticality_b", 1.0)),
        combined_criticality=float(d.get("combined_criticality", 0.0)),
        altitude_km=float(d.get("altitude_km", 0.0)),
        state_vector_at_tca_a=d.get("state_vector_at_tca_a", {}),
        state_vector_at_tca_b=d.get("state_vector_at_tca_b", {}),
        already_maneuvered=bool(d.get("already_maneuvered", False)),
        resolved=bool(d.get("resolved", False))
    )

async def safe_broadcast(message_dict: dict) -> None:
    try:
        from backend.routers.websocket_router import broadcast_message
        await broadcast_message(message_dict)
    except Exception as exc:
        logger.debug(f"Websocket signal bypass: {exc}")

class SentinelScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.db = None
        
    async def initialize(self, db: Any) -> None:
        self.db = db
        logger.info("Initializing SentinelScheduler background systems...")
        
        tle_interval = getattr(settings, "TLE_REFRESH_INTERVAL_MINUTES", 10)
        
        # 1. TLE Ingestion — run immediately on startup, then every interval
        self.scheduler.add_job(
            self.job_ingest_tles,
            IntervalTrigger(minutes=tle_interval),
            id="job_ingest_tles",
            replace_existing=True,
            next_run_time=datetime.now()  # fires immediately on startup
        )
        
        # 2. Conjunction Sweep (Offset by 3 minutes to follow ingestion completion)
        prop_start_date = datetime.now() + timedelta(minutes=3)
        self.scheduler.add_job(
            self.job_propagate_and_detect,
            IntervalTrigger(minutes=tle_interval, start_date=prop_start_date),
            id="job_propagate_and_detect",
            replace_existing=True,
            next_run_time=datetime.now()  # fires immediately on startup
        )

        # Broadcast initial sweep status so UI shows "RUNNING..." instead of "PENDING..."
        asyncio.get_event_loop().call_soon(
            lambda: asyncio.ensure_future(safe_broadcast({
                "type": "system_stats",
                "sweep_status": "RUNNING",
                "timestamp": datetime_to_iso(utc_now()),
                "last_sweep_satellite_count": 0,
                "last_sweep_duration_s": None,
                "kessler_index": 0,
                "total_objects": 0,
            }))
        )
        
        # 3. Fast-loop Threshold/Mitigation Checks
        self.scheduler.add_job(
            self.job_check_thresholds,
            IntervalTrigger(seconds=60),
            id="job_check_thresholds",
            replace_existing=True
        )
        
        # ML and Maintenance Jobs
        self.scheduler.add_job(self.job_retrain_ann, IntervalTrigger(hours=1), id="job_retrain_ann")
        self.scheduler.add_job(self.job_train_lstm, IntervalTrigger(hours=6), id="job_train_lstm")
        self.scheduler.add_job(self.job_cleanup_old_data, IntervalTrigger(days=1), id="job_cleanup_old_data")
        
        self.scheduler.start()
        pass  # the startup sweep is already scheduled above via next_run_time
        logger.info("SentinelScheduler activated with staggered pipeline offsets.")

    async def job_ingest_tles(self) -> None:
        try:
            from backend.core.tle_ingestion import run_tle_ingestion_job
            result = await run_tle_ingestion_job(self.db)
            await safe_broadcast({
                "type": "tle_refresh",
                "timestamp": datetime_to_iso(utc_now()),
                "count": result.get("count", 0)
            })
        except Exception as exc:
            logger.error(f"TLE ingestion error: {exc}")

    async def job_propagate_and_detect(self) -> None:
        try:
            import time as _time
            sweep_start = _time.monotonic()

            satellites = await get_all_satellites(self.db, limit=5000)
            timestamps = get_propagation_timestamps(
                hours_ahead=getattr(settings, "PROPAGATION_HOURS", 72),
                interval_minutes=5
            )
            
            propagated_states = await propagate_batch_python(satellites, timestamps)
            cat = {s["norad_id"]: s for s in satellites}
            
            conjunction_events = await detect_conjunctions(
                propagated_states=propagated_states,
                satellites_catalogue=cat,
                timestamps=timestamps,
                threshold_km=getattr(settings, "CONJUNCTION_THRESHOLD_KM", 5.0)
            )
            
            risk_bands = await get_risk_bands(self.db)

            newly_inserted = 0
            for event in conjunction_events:
                if event.miss_distance_km <= 0 or event.relative_velocity_kmps <= 0:
                    continue
                r_score = score_conjunction(event)
                event.risk_score = r_score
                event.risk_level = classify_risk_level(r_score, risk_bands)
                if await insert_conjunction(self.db, event.to_dict()):
                    newly_inserted += 1

            sweep_duration_s = round(_time.monotonic() - sweep_start, 2)
            satellites_scanned = len(satellites)
            self._last_sweep_duration_s = sweep_duration_s
            self._last_sweep_satellite_count = satellites_scanned

            active_list = await get_active_conjunctions(self.db)
            await safe_broadcast({
                "type": "conjunction_update",
                "conjunctions": [dict(c) for c in active_list],
                "count": len(conjunction_events),
                "newly_added": newly_inserted,
                "timestamp": datetime_to_iso(utc_now()),
                "sweep_duration_s": sweep_duration_s,
                "satellites_scanned": satellites_scanned,
                "partial": True,
            })
        except Exception as exc:
            logger.error(f"Propagation loop error: {exc}")

    async def job_check_thresholds(self) -> None:
        try:
            await expire_past_conjunctions(self.db)
            risk_threshold = getattr(settings, "RISK_THRESHOLD", 0.0001)
            cursor = self.db["conjunctions"].find({
                "resolved": False,
                "maneuvered": {"$ne": True},
                "risk_score": {"$gt": risk_threshold}
            })
            active_conjs = await cursor.to_list(length=100)
            
            for d in active_conjs:
                conj_obj = dict_to_conjunction_event(d)
                
                maneuver_plan = await compute_optimal_maneuver(
                    state_vector_a=conj_obj.state_vector_at_tca_a,
                    conjunction_event=conj_obj,
                    use_rl=True
                )
                
                await insert_maneuver(self.db, maneuver_plan.to_dict())
                await simulate_webhook_dispatch(build_webhook_payload(maneuver_plan, conj_obj), self.db)
                
                await self.db["conjunctions"].update_one(
                    {"event_id": conj_obj.event_id},
                    {"$set": {"maneuvered": True, "maneuver_id": maneuver_plan.maneuver_id}}
                )
                
                # FIXED: Scheduled verification using APScheduler args to prevent closure bug
                run_at = datetime.now() + timedelta(minutes=5)
                self.scheduler.add_job(
                    self._verify_maneuver_task,
                    trigger="date",
                    run_date=run_at,
                    args=[maneuver_plan],  # Bound via explicit argument list
                    id=f"verify_{maneuver_plan.maneuver_id}"
                )

            total_objects = await self.db["satellites"].count_documents({})
            debris_count = await self.db["satellites"].count_documents({"object_type": "DEBRIS"})
            current_bands = await get_risk_bands(self.db)
            high_risk_count = await self.db["conjunctions"].count_documents({
                "resolved": False,
                "risk_level": {"$in": top_severity_keys(current_bands, count=2)}
            })
            kri = compute_kessler_index(high_risk_count, total_objects, debris_count)
            from backend.db.kessler_history_repo import record_daily_snapshot
            await record_daily_snapshot(kri)
            await safe_broadcast({
                "type": "system_stats",
                "total_objects": total_objects,
                "kessler_index": kri,
                "last_sweep_duration_s": getattr(self, "_last_sweep_duration_s", None),
                "last_sweep_satellite_count": getattr(self, "_last_sweep_satellite_count", 0),
            })
        except Exception as exc:
            logger.error(f"Threshold check error: {exc}")

    async def _verify_maneuver_task(self, maneuver_plan: Any) -> None:
        """Dedicated task for post-burn resolution check to avoid closure leakage."""
        try:
            logger.info(f"Verifying maneuver resolution for: {maneuver_plan.maneuver_id}")
            all_sats = await get_all_satellites(self.db, limit=5000)
            from backend.core.secondary_check import verify_maneuver_resolution
            await verify_maneuver_resolution(maneuver_plan, all_sats, self.db)
        except Exception as err:
            logger.error(f"Maneuver verification task failed: {err}")

    async def job_retrain_ann(self) -> None:
        try:
            from backend.ml import collision_probability_ann
            await collision_probability_ann.retrain_model(self.db)
        except Exception: pass

    async def job_train_lstm(self) -> None:
        try:
            from backend.ml import trajectory_lstm
            await trajectory_lstm.train_step(self.db)
        except Exception: pass

    async def job_cleanup_old_data(self) -> None:
        try:
            limit_date = utc_now() - timedelta(days=7)
            await self.db["conjunctions"].delete_many({
                "resolved": True,
                "tca_utc": {"$lt": limit_date}
            })
        except Exception as exc:
            logger.error(f"Cleanup error: {exc}")

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)

sentinel_scheduler = SentinelScheduler()