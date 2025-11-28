from pydantic_settings import BaseSettings
from typing import Optional, Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar('T')

class DefaultResponse(BaseModel, Generic[T]):
    error: bool
    message: str
    payload: Optional[Any] = None
    
    class Config:
        from_attributes = True

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: str
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()