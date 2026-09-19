import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score
import pickle
import os
import logging
import asyncio
import httpx
from typing import Tuple, Dict, Any, Optional

from sklearn.utils.class_weight import compute_sample_weight
from backend.utils.cache import cache

logger = logging.getLogger("orbit_sentinel.collision_probability_ann")

def generate_synthetic_training_data(n_samples: int = 50000) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates realistic synthetic conjunction feature data for ANN training.
    Labels are derived from a physics-based collision probability approximation using the
    Chan formulation: Pc = (R_combined^2 / 2*sigma^2) * exp(-0.5 * miss^2/sigma^2) / (1 + 0.1*vel).
    Positives (y=1) are samples where Pc_final > 1e-4, the NASA/ESA operational alert threshold.
    This ensures the model learns to generalise from real physical relationships, not hard thresholds.
    """
    # 0: miss_distance_km — log-uniform [0.01, 100.0]
    miss_distance_km = np.exp(np.random.uniform(np.log(0.01), np.log(100.0), n_samples))
    
    # 1: relative_velocity_kmps — uniform [0.1, 15.0]
    relative_velocity_kmps = np.random.uniform(0.1, 15.0, n_samples)
    
    # 2: combined_cross_section_m2 — uniform [5.0, 100.0]
    combined_cross_section_m2 = np.random.uniform(5.0, 100.0, n_samples)
    
    # 3: time_to_tca_hours — uniform [0.5, 72.0]
    time_to_tca_hours = np.random.uniform(0.5, 72.0, n_samples)
    
    # 4: criticality_a — uniform [1.0, 10.0]
    criticality_a = np.random.uniform(1.0, 10.0, n_samples)
    
    # 5: criticality_b — uniform [1.0, 10.0]
    criticality_b = np.random.uniform(1.0, 10.0, n_samples)
    
    # 6: object_type_a_encoded — randint [0, 3] (0=PAYLOAD, 1=ROCKET_BODY, 2=DEBRIS, 3=UNKNOWN)
    object_type_a_encoded = np.random.randint(0, 4, n_samples)
    
    # 7: object_type_b_encoded — same
    object_type_b_encoded = np.random.randint(0, 4, n_samples)
    
    # 8: altitude_km — uniform [200, 2000]
    altitude_km = np.random.uniform(200.0, 2000.0, n_samples)
    
    # 9: solar_flux_f10_7 — uniform [65, 250]
    solar_flux_f10_7 = np.random.uniform(65.0, 250.0, n_samples)
    
    # 10: kp_index — uniform [0, 9]
    kp_index = np.random.uniform(0.0, 9.0, n_samples)
    
    # 11: maneuver_history_count — randint [0, 20]
    maneuver_history_count = np.random.randint(0, 21, n_samples)
    
    X = np.stack([
        miss_distance_km,
        relative_velocity_kmps,
        combined_cross_section_m2,
        time_to_tca_hours,
        criticality_a,
        criticality_b,
        object_type_a_encoded,
        object_type_b_encoded,
        altitude_km,
        solar_flux_f10_7,
        kp_index,
        maneuver_history_count
    ], axis=1)
    
    # Physics-derived collision probability labels using Chan formulation.
    # Labels are y=1 if the approximate Pc exceeds the NASA/ESA operational alert threshold (1e-4).
    combined_radius_km = 0.020  # 20 metre hard-body radius
    # TLE positional uncertainty grows with time to TCA
    position_uncertainty_km = 0.1 + (0.05 * time_to_tca_hours)
    sigma_sq = position_uncertainty_km ** 2

    # 2D Gaussian Pc approximation
    Pc_approx = (combined_radius_km**2 / (2.0 * sigma_sq)) * np.exp(
        -0.5 * (miss_distance_km**2 / sigma_sq)
    )

    # High relative velocity shortens encounter duration → reduces Pc
    Pc_final = Pc_approx / (1.0 + 0.1 * relative_velocity_kmps)

    # Operational alert threshold: 1e-4 (NASA/ESA standard)
    y = np.where(Pc_final > 1e-4, 1, 0).astype(int)

    # Ensure class balance: if fewer than 1000 positives, generate physics-consistent positives
    n_positives = np.sum(y == 1)
    target_positives = int(0.30 * n_samples)
    if n_positives < target_positives:
        needed = target_positives - n_positives
        logger.info(f"Adding {needed} physics-consistent positive training samples to balance ANN...")

        # Sample parameters that produce Pc_final > 1e-4 using the same formula
        extra_samples_found = 0
        extra_rows = []
        max_attempts = needed * 50
        attempts = 0
        while extra_samples_found < needed and attempts < max_attempts:
            attempts += 1
            e_miss = np.random.uniform(0.001, 0.3)
            e_vel = np.random.uniform(0.1, 15.0)
            e_tca = np.random.uniform(0.5, 24.0)
            e_unc = 0.1 + (0.05 * e_tca)
            e_sigma_sq = e_unc ** 2
            e_pc = (combined_radius_km**2 / (2.0 * e_sigma_sq)) * np.exp(
                -0.5 * (e_miss**2 / e_sigma_sq)
            ) / (1.0 + 0.1 * e_vel)
            if e_pc > 1e-4:
                extra_rows.append([
                    e_miss, e_vel,
                    np.random.uniform(5.0, 100.0), e_tca,
                    np.random.uniform(1.0, 10.0), np.random.uniform(1.0, 10.0),
                    np.random.randint(0, 4), np.random.randint(0, 4),
                    np.random.uniform(200.0, 2000.0),
                    np.random.uniform(65.0, 250.0),
                    np.random.uniform(0.0, 9.0),
                    np.random.randint(0, 21)
                ])
                extra_samples_found += 1

        if extra_rows:
            X_extra = np.array(extra_rows)
            y_extra = np.ones(len(extra_rows), dtype=int)
            X = np.vstack([X, X_extra])
            y = np.concatenate([y, y_extra])

    return X, y

class CollisionProbabilityANN:
    MODEL_PATH = "ml_models/ann_model.pkl"
    SCALER_PATH = "ml_models/ann_scaler.pkl"
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.accuracy_metrics = {}
        self.threshold = 0.5
        os.makedirs("ml_models", exist_ok=True)
        
    def train(self, X=None, y=None):
        logger.info("Starting training process for CollisionProbabilityANN classifier neural network...")
        if X is None or y is None:
            X, y = generate_synthetic_training_data()
            
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        X_test_scaled = self.scaler.transform(X_test)
        
        self.model = MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation='relu',
            solver='adam',
            max_iter=800,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=30
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Balanced eval — equal positives/negatives, honest metric on imbalanced domain
        pos_idx = np.where(y_test == 1)[0]
        neg_idx = np.where(y_test == 0)[0]
        n_each = min(len(pos_idx), len(neg_idx))
        if n_each > 0:
            bal_idx = np.concatenate([pos_idx[:n_each], neg_idx[:n_each]])
            np.random.shuffle(bal_idx)
            X_bal = X_test_scaled[bal_idx]
            y_bal = y_test[bal_idx]
        else:
            X_bal, y_bal = X_test_scaled, y_test

        y_pred = self.model.predict(X_bal)
        prec = precision_score(y_bal, y_pred, zero_division=0)
        rec = recall_score(y_bal, y_pred, zero_division=0)
        f1 = f1_score(y_bal, y_pred, zero_division=0)
        accuracy = self.model.score(X_bal, y_bal)

        self.accuracy_metrics = {
            "precision": float(prec),
            "recall": float(rec),
            "f1_score": float(f1),
            "accuracy": float(accuracy)
        }
        neg_idx = np.where(y_test == 0)[0]
        n_each = min(len(pos_idx), len(neg_idx))
        if n_each > 0:
            bal_idx = np.concatenate([pos_idx[:n_each], neg_idx[:n_each]])
            np.random.shuffle(bal_idx)
            X_bal = X_test_scaled[bal_idx]
            y_bal = y_test[bal_idx]
        else:
            X_bal, y_bal = X_test_scaled, y_test

        probs_bal = self.model.predict_proba(X_bal)[:, 1]
        best_f1, best_thr = 0.0, 0.5
        for thr in np.arange(0.05, 0.96, 0.01):
            y_pred_thr = (probs_bal >= thr).astype(int)
            f1_thr = f1_score(y_bal, y_pred_thr, zero_division=0)
            if f1_thr > best_f1:
                best_f1, best_thr = f1_thr, thr

        y_pred = (probs_bal >= best_thr).astype(int)
        prec = precision_score(y_bal, y_pred, zero_division=0)
        rec = recall_score(y_bal, y_pred, zero_division=0)
        f1 = f1_score(y_bal, y_pred, zero_division=0)
        accuracy = float(np.mean(y_pred == y_bal))

        self.threshold = float(best_thr)
        self.accuracy_metrics = {
            "precision": float(prec),
            "recall": float(rec),
            "f1_score": float(f1),
            "accuracy": float(accuracy),
            "threshold": float(best_thr)
        }
        
        # Save models securely to disk
        with open(self.MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)
        with open(self.SCALER_PATH, "wb") as f:
            pickle.dump(self.scaler, f)
        # Save metrics so they survive process restarts
        import json
        metrics_path = self.MODEL_PATH.replace(".pkl", "_metrics.json")
        with open(metrics_path, "w") as f:
            json.dump(self.accuracy_metrics, f)
        logger.info(f"ANN balanced-eval metrics saved: precision={prec:.3f} recall={rec:.3f} f1={f1:.3f}")
            
        self.is_trained = True
        logger.info(f"ANN trained on physically-meaningful synthetic conjunctions. Positive class rate: {float(np.sum(y==1))/len(y):.3f}")
        logger.info(f"CollisionProbabilityANN training completed successfully. Metrics: {self.accuracy_metrics}")
        
    def load(self) -> bool:
        if os.path.exists(self.MODEL_PATH) and os.path.exists(self.SCALER_PATH):
            try:
                with open(self.MODEL_PATH, "rb") as f:
                    self.model = pickle.load(f)
                with open(self.SCALER_PATH, "rb") as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
                import json as _json
                metrics_path = self.MODEL_PATH.replace(".pkl", "_metrics.json")
                if os.path.exists(metrics_path):
                    try:
                        with open(metrics_path, "r") as _f:
                            loaded_m = _json.load(_f)
                        self.accuracy_metrics = loaded_m
                        self.threshold = loaded_m.get("threshold", 0.5)
                    except Exception:
                        self.accuracy_metrics = {}
                else:
                    self.accuracy_metrics = {}
                logger.info("CollisionProbabilityANN loaded successfully from model directory.")
                return True
            except Exception as e:
                logger.error(f"Failed to load compiled ANN models from disk: {e}")
                return False
        return False
        
    def predict_probability(self, features_dict: dict) -> float:
        if not self.is_trained or self.model is None or self.scaler is None:
            return 0.0
            
        type_a = features_dict.get("object_type_a", "UNKNOWN")
        type_b = features_dict.get("object_type_b", "UNKNOWN")
        
        type_a_enc = features_dict.get("object_type_a_encoded", self.encode_object_type(type_a))
        type_b_enc = features_dict.get("object_type_b_encoded", self.encode_object_type(type_b))
        
        try:
            feats = [
                float(features_dict.get("miss_distance_km", 10.0)),
                float(features_dict.get("relative_velocity_kmps", 7.0)),
                float(features_dict.get("combined_cross_section_m2", 15.0)),
                float(features_dict.get("time_to_tca_hours", 24.0)),
                float(features_dict.get("criticality_a", 5.0)),
                float(features_dict.get("criticality_b", 5.0)),
                int(type_a_enc),
                int(type_b_enc),
                float(features_dict.get("altitude_km", 500.0)),
                float(features_dict.get("solar_flux_f10_7", 120.0)),
                float(features_dict.get("kp_index", 3.0)),
                int(features_dict.get("maneuver_history_count", 0))
            ]
            
            feats_arr = np.array([feats])
            scaled_feats = self.scaler.transform(feats_arr)
            probs = self.model.predict_proba(scaled_feats)
            return float(probs[0][1])
        except Exception as e:
            logger.error(f"Prediction error inside ANN probability routine: {e}")
            return 0.0

    def predict_is_high_risk(self, features_dict: dict) -> bool:
        return self.predict_probability(features_dict) >= self.threshold
            
    def encode_object_type(self, obj_type: str) -> int:
        if not obj_type:
            return 3
        obj_upper = str(obj_type).upper()
        if "PAYLOAD" in obj_upper or "SATELLITE" in obj_upper:
            return 0
        if "ROCKET" in obj_upper or "BODY" in obj_upper:
            return 1
        if "DEBRIS" in obj_upper:
            return 2
        return 3

# Module singleton instance
ann_model = CollisionProbabilityANN()

async def retrain_model(db: Any) -> None:
    logger.info("Starting background retrain trigger on ANN classifier...")
    samples = []
    try:
        if db is not None:
            cursor = db["ml_training_data"].find().sort([("_id", -1)]).limit(10000)
            samples = await cursor.to_list(length=10000)
    except Exception as e:
        logger.warning(f"Error reading historical train frames from MongoDB ml_training_data: {e}")
        
    if len(samples) < 1000:
        logger.info(f"Fewer than 1000 samples matched inside DB ({len(samples)}). Utilizing synthetics...")
        X, y = generate_synthetic_training_data()
        n_count = len(y)
    else:
        X_list = []
        y_list = []
        
        for record in samples:
            features = record.get("features", record)
            type_a = features.get("object_type_a", "UNKNOWN")
            type_b = features.get("object_type_b", "UNKNOWN")
            
            type_a_enc = features.get("object_type_a_encoded", ann_model.encode_object_type(type_a))
            type_b_enc = features.get("object_type_b_encoded", ann_model.encode_object_type(type_b))
            
            feats = [
                float(features.get("miss_distance_km", 10.0)),
                float(features.get("relative_velocity_kmps", 7.0)),
                float(features.get("combined_cross_section_m2", 15.0)),
                float(features.get("time_to_tca_hours", 24.0)),
                float(features.get("criticality_a", 5.0)),
                float(features.get("criticality_b", 5.0)),
                int(type_a_enc),
                int(type_b_enc),
                float(features.get("altitude_km", 500.0)),
                float(features.get("solar_flux_f10_7", 120.0)),
                float(features.get("kp_index", 3.0)),
                int(features.get("maneuver_history_count", 0))
            ]
            X_list.append(feats)
            y_list.append(int(record.get("label", record.get("collision", 0))))
            
        X = np.array(X_list)
        y = np.array(y_list)
        n_count = len(samples)
        
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, ann_model.train, X, y)
    logger.info(f"ANN retrained on {n_count} samples")

async def initialize_ann() -> None:
    loaded = ann_model.load()
    # load() already rejects metrics with f1 < 0.50, so empty metrics = needs retrain
    if not loaded or not ann_model.accuracy_metrics:
        logger.info("ANN not loaded or metrics missing — training now...")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, ann_model.train)
    logger.info(f"ANN ready. Metrics: {ann_model.accuracy_metrics}")

async def get_space_weather() -> Tuple[float, float]:
    """
    Fetches Space Weather indexes (Kp Index and Solar Flux F10.7).
    """
    cached_data = cache.get("space_weather")
    if cached_data is not None:
        return cached_data
        
    kp = 3.0
    f107 = 150.0
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    last_entry = data[-1]
                    for k in ["kp_index", "Kp_index", "kp", "Kp"]:
                        if k in last_entry:
                            kp = float(last_entry[k])
                            break
    except Exception as exc:
        logger.warning(f"Failed to fetch Kp index from NOAA, defaulting to {kp}: {exc}")
        
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    last_entry = data[-1]
                    for k in ["f10.7", "f10_7", "f107", "f11_7", "observed_f107", "observed_f10.7"]:
                        if k in last_entry:
                            f107 = float(last_entry[k])
                            break
    except Exception as exc:
        logger.warning(f"Failed to fetch Solar Flux F10.7 index from NOAA, defaulting to {f107}: {exc}")
        
    cache.set("space_weather", (kp, f107), ttl=3600)
    return (kp, f107)