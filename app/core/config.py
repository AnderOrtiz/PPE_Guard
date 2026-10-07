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

    MODEL_PATHS: dict[str, str] = {
        "civil": "weights/civil.pt",
        "medicina": "weights/medicina.pt",
    }
    CONFIDENCE_THRESHOLD: float = 0.50
    IOU_THRESHOLD: float = 0.45

    # Al arrancar, una práctica que quedó "activa" se reanuda solo si empezó
    # hace menos de estas horas; si no, se cierra.
    PRACTICA_RECUPERABLE_HORAS: int = 8

    # Autenticación
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 horas, cubre una jornada de clases


settings = Settings()