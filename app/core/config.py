import os
from enum import Enum
from pydantic_settings import BaseSettings

class DatabaseType(str, Enum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"

class Settings(BaseSettings):
    # Application Config
    APP_ENV: str = "development"
    
    # Database Config
    DB_TYPE: DatabaseType = DatabaseType.SQLITE
    
    # SQLite Path
    SQLITE_URL: str = "sqlite:///./app.db"
    
    # Postgres Connection Args
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "cookbook"

    @property
    def database_url(self) -> str:
        if self.DB_TYPE == DatabaseType.SQLITE:
            return self.SQLITE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()
