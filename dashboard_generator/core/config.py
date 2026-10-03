import os
from pathlib import Path
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    # Загружаем .env из корня проекта
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass


class Settings(BaseModel):
    superset_url: str = Field(default_factory=lambda: os.getenv("SUPERSET_URL", "http://localhost:8088").rstrip("/"))
    superset_username: str = Field(default_factory=lambda: os.getenv("SUPERSET_USERNAME", "admin"))
    superset_password: str = Field(default_factory=lambda: os.getenv("SUPERSET_PASSWORD", "admin"))

    postgres_host: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: int = Field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    postgres_db: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "analytics_db"))
    postgres_user: str = Field(default_factory=lambda: os.getenv("POSTGRES_USER", "superset"))
    postgres_password: str = Field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "superset"))
    
    # Хост PostgreSQL, как его видит контейнер Apache Superset внутри Docker-сети
    postgres_docker_host: str = Field(default_factory=lambda: os.getenv("POSTGRES_DOCKER_HOST", "postgres"))

    semantic_model_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).resolve().parent.parent / "config" / "semantic_model.yaml"
        )
    )

    llm_repair_attempts: int = Field(default_factory=lambda: int(os.getenv("LLM_REPAIR_ATTEMPTS", "2")))

    @property
    def postgres_local_uri(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def postgres_superset_uri(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_docker_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
