"""
Конфигурация приложения через переменные окружения
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # MongoDB
    mongo_host: str = "mongo"
    mongo_port: int = 27017
    mongo_db: str = "huggingface_papers"
    mongo_user: str = ""
    mongo_password: str = ""
    
    @property
    def mongo_uri(self) -> str:
        """Получение URI для подключения к MongoDB"""
        if self.mongo_user and self.mongo_password:
            return f"mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}/"
        return f"mongodb://{self.mongo_host}:{self.mongo_port}/"
    
    # Scrapy
    scrapy_crawl_dir: str = "/app/crawls"
    scrapy_log_level: str = "INFO"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Валидация дат
    min_date_year: int = 2023
    min_date_month: int = 1
    min_date_day: int = 1
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Получение настроек (cached)"""
    return Settings()
