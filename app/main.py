"""
FastAPI приложение для управления краулерами Hugging Face Papers
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api import tasks, crawl
from app.db.mongo import get_mongo_client, init_db, close_mongo_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при запуске и очистка при завершении"""
    # Инициализация базы данных
    client = get_mongo_client()
    init_db(client)
    yield
    # Закрытие соединений при завершении
    close_mongo_client()


app = FastAPI(
    title="Hugging Face Papers Crawler API",
    description="API для управления процессом сбора данных с Hugging Face Papers",
    version="1.0.0",
    lifespan=lifespan,
)

# Подключение роутеров
app.include_router(crawl.router, prefix="/crawl", tags=["Crawl"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "Hugging Face Papers Crawler API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy"}
