"""
API эндпоинты для мониторинга задач
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pymongo.database import Database

from app.db.mongo import get_db
from app.models.schemas import TaskResponse, TaskListResponse, ErrorResponse
from app.services.task_service import TaskService
from app.config import get_settings

router = APIRouter()
settings = get_settings()


def get_task_service(db: Database = Depends(get_db)) -> TaskService:
    """Dependency для получения сервиса задач"""
    return TaskService(db)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="Получение списка всех задач",
    description="Возвращает список всех запущенных и завершенных задач"
)
def get_all_tasks(
    service: TaskService = Depends(get_task_service),
    limit: int = Query(default=None, ge=1, le=1000, description="Максимальное количество задач"),
    skip: int = Query(0, ge=0, description="Количество задач для пропуска")
):
    """
    Получение списка всех задач
    
    Возвращает все задачи с пагинацией
    """
    # Используем значение по умолчанию из конфига если limit не передан
    if limit is None:
        limit = settings.task_default_limit
    """
    Получение списка всех задач
    
    Возвращает все задачи с пагинацией
    """
    tasks = service.get_all_tasks(limit=limit, skip=skip)
    total = service.collection.count_documents({})
    
    return TaskListResponse(
        tasks=tasks,
        total=total
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Задача не найдена"}
    },
    summary="Получение статуса конкретной задачи",
    description="Детальный статус конкретной задачи: статус, время начала/конца, количество собранных items"
)
def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service)
):
    """
    Получение статуса задачи
    
    Возвращает детальную информацию о задаче:
    - status: pending/running/completed/failed
    - start_time: время начала
    - end_time: время завершения
    - items_collected: количество собранных items
    - Параметры запуска
    """
    task = service.get_task(task_id)
    
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found"
        )
    
    return task
