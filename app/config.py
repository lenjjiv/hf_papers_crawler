"""
Конфигурация приложения через переменные окружения
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # ===================
    # MongoDB
    # ===================
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
    
    # ===================
    # Scrapy
    # ===================
    scrapy_crawl_dir: str = "/app/crawls"
    scrapy_log_level: str = "INFO"
    
    # ===================
    # API
    # ===================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_version: str = "1.0.0"
    
    # ===================
    # Валидация дат
    # ===================
    min_date_year: int = 2023
    min_date_month: int = 1
    min_date_day: int = 1
    
    # ===================
    # HTTP клиент (httpx)
    # ===================
    http_timeout: float = 30.0
    http_user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # ===================
    # Retry логика
    # ===================
    http_max_retries: int = 5
    http_initial_delay: float = 10.0  # начальная задержка в секундах
    http_max_delay: float = 120.0  # максимальная задержка в секундах
    
    # ===================
    # Краулинг
    # ===================
    crawl_base_url: str = "https://huggingface.co"
    crawl_delay: float = 5.0  # задержка между запросами в секундах
    
    # ===================
    # Task Service
    # ===================
    task_max_workers: int = 4
    task_default_limit: int = 100
    task_max_limit: int = 1000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# ===================
# Константы (не из env)
# ===================

# Индексы MongoDB
MONGO_INDEX_CRAWL_LOGS_TASK_ID = "task_id"
MONGO_INDEX_CRAWL_LOGS_STATUS = "status"
MONGO_INDEX_CRAWL_LOGS_START_TIME = "start_time"
MONGO_INDEX_PAPERS_PAPER_ID = "paper_id"
MONGO_INDEX_PAPERS_ARXIV_ID = "arxiv_id"
MONGO_INDEX_PAPERS_CRAWL_DATE = "crawl_date"


@lru_cache()
def get_settings() -> Settings:
    """Получение настроек (cached)"""
    return Settings()
