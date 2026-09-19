import os
import json
import logging
import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("orbit_sentinel.model_registry")

class ModelRegistry:
    def __init__(self):
        self._registry: Dict[str, Any] = {}
        # Default destination path inside ml_models folder
        self.file_path = "ml_models/registry.json"

    def register(self, model_name: str, version: str, metrics: Dict[str, Any], path: str) -> None:
        """
        Upsert a model version record into the registry and trigger immediate serialization.
        """
        self._registry[model_name] = {
            "version": version,
            "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "accuracy_metrics": metrics,
            "file_path": path
        }
        self.save_registry()

    def get_version_string(self) -> str:
        """
        Returns "ann_v{N}_lstm_v{M}" based on current registered/analyzed version values.
        """
        ann_ver = "1.0"
        lstm_ver = "1.0"
        for name, info in self._registry.items():
            name_lower = name.lower()
            val = info.get("version", "1.0")
            if "ann" in name_lower or "collision" in name_lower:
                ann_ver = val
            elif "lstm" in name_lower or "trajectory" in name_lower:
                lstm_ver = val
        return f"ann_v{ann_ver}_lstm_v{lstm_ver}"

    def get_all_model_info(self) -> List[Dict[str, Any]]:
        """
        Lists all registered models in the central tracker.
        """
        return [{"model_name": name, **info} for name, info in self._registry.items()]

    def save_registry(self) -> None:
        """
        Writes the model registry dictionary JSON output to disk.
        """
        dir_name = os.path.dirname(self.file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        try:
            with open(self.file_path, "w") as f:
                json.dump(self._registry, f, indent=2)
            logger.info(f"Model registry written successfully to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to write model registry: {e}")

    def load_registry(self) -> None:
        """
        Loads the from file, handling FileNotFoundError by initializing an empty state safely.
        """
        possible_paths = [
            self.file_path,
            os.path.join("backend", self.file_path),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), self.file_path)
        ]
        
        loaded = False
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        self._registry = json.load(f)
                    self.file_path = path  # Update active path location
                    loaded = True
                    logger.info(f"Successfully loaded model registry from: {path}")
                    break
                except Exception as e:
                    logger.error(f"Failed to parse registry from {path}: {e}")
                    
        if not loaded:
            logger.info("Initializing blank model registry tracking state. No registry file found.")
            self._registry = {}

# Create ModelRegistry Singleton
model_registry = ModelRegistry()

try:
    model_registry.load_registry()
except Exception as err:
    logger.error(f"Critical error loading model registry singleton: {err}")
