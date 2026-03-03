"""
MongoDB клиент и функции для работы с базой данных (dependency injection)
"""
import pymongo
from pymongo import MongoClient
from pymongo.database import Database
from typing import Generator
from app.config import get_settings, MONGO_INDEX_CRAWL_LOGS_TASK_ID, MONGO_INDEX_CRAWL_LOGS_STATUS, MONGO_INDEX_CRAWL_LOGS_START_TIME, MONGO_INDEX_PAPERS_PAPER_ID, MONGO_INDEX_PAPERS_ARXIV_ID, MONGO_INDEX_PAPERS_CRAWL_DATE


# Синглтон для MongoClient
_mongo_client: MongoClient = None


def get_mongo_client() -> MongoClient:
    """Получение синглтона MongoClient"""
    global _mongo_client
    if _mongo_client is None:
        settings = get_settings()
        _mongo_client = pymongo.MongoClient(settings.mongo_uri)
    return _mongo_client


def close_mongo_client():
    """Закрытие синглтона MongoClient"""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None


def create_mongo_client() -> MongoClient:
    """Создание клиента MongoDB (для совместимости)"""
    settings = get_settings()
    return pymongo.MongoClient(settings.mongo_uri)


def get_db() -> Generator[Database, None, None]:
    """Получение базы данных через dependency injection"""
    settings = get_settings()
    client = get_mongo_client()
    db = client[settings.mongo_db]
    yield db
    # Не закрываем клиент - он переиспользуется


def init_db(client: MongoClient = None) -> Database:
    """Инициализация базы данных и коллекций"""
    settings = get_settings()
    if client is None:
        client = create_mongo_client()
    db = client[settings.mongo_db]
    
    # Создание индексов
    db.crawl_logs.create_index(MONGO_INDEX_CRAWL_LOGS_TASK_ID, unique=True)
    db.crawl_logs.create_index(MONGO_INDEX_CRAWL_LOGS_STATUS)
    db.crawl_logs.create_index(MONGO_INDEX_CRAWL_LOGS_START_TIME)
    
    db.papers.create_index(MONGO_INDEX_PAPERS_PAPER_ID)
    db.papers.create_index(MONGO_INDEX_PAPERS_ARXIV_ID)
    db.papers.create_index(MONGO_INDEX_PAPERS_CRAWL_DATE)
    
    return db
