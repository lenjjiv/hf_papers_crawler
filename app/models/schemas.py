"""
Pydantic схемы для API
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """Статус задачи"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CrawlType(str, Enum):
    """Тип краулинга"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TaskCreate(BaseModel):
    """Схема для создания задачи"""
    crawl_type: CrawlType
    date_param: str  # Параметр даты (YYYY-MM-DD, YYYY-Www, YYYY-MM)
    # Диапазон для итерации (опционально)
    start_date: Optional[str] = None  # Начальная дата диапазона (YYYY-MM-DD)
    end_date: Optional[str] = None    # Конечная дата диапазона (YYYY-MM-DD)
    # Параметры для итерации по паттерну
    start_param: Optional[str] = None  # Начальный параметр (день/неделя/месяц)
    end_param: Optional[str] = None    # Конечный параметр (день/неделя/месяц)
    crawl_pattern: Optional[str] = None  # Паттерн краулинга: "daily", "weekly", "monthly"


class TaskResponse(BaseModel):
    """Схема ответа задачи"""
    task_id: str
    status: TaskStatus
    crawl_type: CrawlType
    date_param: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    items_collected: int = 0
    error: Optional[str] = None


class TaskListResponse(BaseModel):
    """Схема списка задач"""
    tasks: List[TaskResponse]
    total: int


class TaskStartResponse(BaseModel):
    """Схема ответа при запуске задачи"""
    task_id: str
    status: str = "started"
    message: str


class ErrorResponse(BaseModel):
    """Схема ошибки"""
    detail: str
    error_code: Optional[str] = None
