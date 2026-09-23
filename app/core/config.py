from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "PPE_Guard"
    DEBUG: bool = False

    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    MONGO_HOST: str
    MONGO_DB_NAME: str
    MONGO_DB_PORT: int = 27017
    MONGO_USERNAME: str
    MONGO_PASSWORD: str

    # Un modelo por área — Opción B
    MODEL_PATHS: dict[str, str] = {
        "civil": "weights/civil.pt",
        "medicina": "weights/medicina.pt",
    }
    CONFIDENCE_THRESHOLD: float = 0.50
    IOU_THRESHOLD: float = 0.45


settings = Settings()