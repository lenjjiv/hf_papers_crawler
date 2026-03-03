"""
Сервис для управления задачами краулинга
"""
import uuid
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import pymongo
from pymongo.database import Database

from app.models.schemas import TaskStatus, CrawlType, TaskResponse, TaskCreate
from app.config import get_settings
from app.services.parser_service import CrawlScheduler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskService:
    """Сервис для управления задачами краулинга"""
    
    def __init__(self, db: Database):
        self.db = db
        self.settings = get_settings()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.collection = db.crawl_logs
    
    def create_task(self, task_data: TaskCreate) -> str:
        """Создание новой задачи"""
        task_id = str(uuid.uuid4())
        
        doc = {
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
            "crawl_type": task_data.crawl_type.value,
            "date_param": task_data.date_param,
            "start_date": task_data.start_date,
            "end_date": task_data.end_date,
            "start_time": None,
            "end_time": None,
            "items_collected": 0,
            "error": None,
            "created_at": datetime.utcnow()
        }
        
        self.collection.insert_one(doc)
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Получение задачи по ID"""
        doc = self.collection.find_one({"task_id": task_id})
        if not doc:
            return None
        return self._doc_to_response(doc)
    
    def get_all_tasks(self, limit: int = 100, skip: int = 0) -> List[TaskResponse]:
        """Получение всех задач"""
        cursor = self.collection.find() \
            .sort("created_at", pymongo.DESCENDING) \
            .skip(skip) \
            .limit(limit)
        
        return [self._doc_to_response(doc) for doc in cursor]
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        items_collected: int = None,
        error: str = None
    ):
        """Обновление статуса задачи"""
        update = {
            "status": status.value,
            "end_time": datetime.utcnow() if status in [TaskStatus.COMPLETED, TaskStatus.FAILED] else None
        }
        
        if items_collected is not None:
            update["items_collected"] = items_collected
        if error is not None:
            update["error"] = error
        if status == TaskStatus.RUNNING:
            update["start_time"] = datetime.utcnow()
        
        self.collection.update_one(
            {"task_id": task_id},
            {"$set": update}
        )
    
    def start_crawl(self, task_id: str, task_data: TaskCreate):
        """Запуск краулера в отдельном потоке"""
        logger.info(f"Starting crawl for task {task_id}, type={task_data.crawl_type}, date_param={task_data.date_param}")
        
        # Обновляем статус на running
        self.update_task_status(task_id, TaskStatus.RUNNING)
        
        # Запускаем в отдельном потоке
        self.executor.submit(self._run_crawler, task_id, task_data)
    
    def _run_crawler(self, task_id: str, task_data: TaskCreate):
        """Выполнение краулера с использованием httpx"""
        logger.info(f"[_run_crawler] Task {task_id} started")
        
        # Создаем новый event loop для async функции
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(self._async_crawl(task_id, task_data))
            
            logger.info(f"[_run_crawler] Task {task_id} completed with {result.get('items_collected', 0)} items")
            self.update_task_status(
                task_id, 
                TaskStatus.COMPLETED, 
                items_collected=result.get("items_collected", 0)
            )
            
        except Exception as e:
            logger.exception(f"[_run_crawler] Task {task_id} exception: {e}")
            self.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
        finally:
            loop.close()
    
    async def _async_crawl(self, task_id: str, task_data: TaskCreate) -> Dict[str, Any]:
        """Асинхронное выполнение краулера"""
        scheduler = CrawlScheduler(self.db)
        
        try:
            # Определяем паттерн из crawl_type
            pattern = task_data.crawl_type.value
            
            # Проверяем, есть ли диапазон для итерации
            if task_data.start_param and task_data.end_param:
                # Итерация по диапазону с указанным паттерном
                logger.info(f"[_async_crawl] Running pattern range: {task_data.start_param} to {task_data.end_param}, pattern={pattern}")
                
                results = await scheduler.crawl_pattern_range(
                    task_data.start_param,
                    task_data.end_param,
                    pattern
                )
                
                total_papers = sum(r.get("papers_count", 0) for r in results)
                return {
                    "items_collected": total_papers,
                    "iterations": len(results),
                    "pattern": pattern
                }
            else:
                # Одиночный краулинг (без диапазона)
                if task_data.crawl_type == CrawlType.DAILY:
                    result = await scheduler.crawl_daily(task_data.date_param)
                    return {
                        "items_collected": result.get("papers_count", 0),
                        "url": result.get("url")
                    }
                
                elif task_data.crawl_type == CrawlType.WEEKLY:
                    result = await scheduler.crawl_weekly(task_data.date_param)
                    return {
                        "items_collected": result.get("papers_count", 0),
                        "url": result.get("url")
                    }
                
                elif task_data.crawl_type == CrawlType.MONTHLY:
                    result = await scheduler.crawl_monthly(task_data.date_param)
                    return {
                        "items_collected": result.get("papers_count", 0),
                        "url": result.get("url")
                    }
                
                else:
                    raise ValueError(f"Unknown crawl type: {task_data.crawl_type}")
                
        finally:
            await scheduler.close()
    
    def _count_collected_items(self, task_data: TaskCreate) -> int:
        """Подсчет количества собранных items"""
        try:
            papers_collection = self.db.papers
            if task_data.crawl_type == CrawlType.DAILY:
                return papers_collection.count_documents({
                    "crawl_date": task_data.date_param
                })
            elif task_data.crawl_type == CrawlType.FETCH_ALL:
                return papers_collection.count_documents({})
            else:
                return papers_collection.count_documents({})
        except Exception:
            return 0
    
    def _doc_to_response(self, doc: Dict[str, Any]) -> TaskResponse:
        """Преобразование документа в ответ"""
        return TaskResponse(
            task_id=doc["task_id"],
            status=TaskStatus(doc["status"]),
            crawl_type=CrawlType(doc["crawl_type"]),
            date_param=doc["date_param"],
            start_time=doc.get("start_time"),
            end_time=doc.get("end_time"),
            items_collected=doc.get("items_collected", 0),
            error=doc.get("error")
        )
