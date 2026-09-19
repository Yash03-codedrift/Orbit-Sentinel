from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # MongoDB configuration
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "orbit_sentinel"
    
    # Orbit data sources and API endpoints
    CELESTRAK_BASE_URL: str = "https://celestrak.org"
    SPACETRACK_BASE_URL: str = "https://www.space-track.org"
    SPACETRACK_USER: str = ""
    SPACETRACK_PASS: str = ""
    N2YO_API_KEY: str = ""
    
    # Event notification and webhooks
    WEBHOOK_SECRET: str = "changeme"
    API_KEY: str = "changeme"
    
    # Scheduler and system options
    TLE_REFRESH_INTERVAL_MINUTES: int = 10
    PROPAGATION_HOURS: int = 72
    CONJUNCTION_THRESHOLD_KM: float = 5.0
    RISK_THRESHOLD: float = 0.0001
    MAX_WORKERS: int = 8
    
    # SGP4 propagation engines
    RUST_SGP4_BINARY_PATH: str = "rust_sgp4/target/release/sgp4_batch"
    
    # Cross-Origin resource sharing (CORS) security configuration
    FRONTEND_URL: str = "http://localhost:5173"
    ENV: str = "development"
    OPENSEARCH_URL: str = "http://opensearch:9200"

    # Pydantic configuration loading settings from '.env' file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings to be loaded across the backend applications
settings = Settings()