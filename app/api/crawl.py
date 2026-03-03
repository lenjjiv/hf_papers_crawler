"""
API эндпоинты для управления краулерами
"""
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pymongo.database import Database

from app.db.mongo import get_db
from app.models.schemas import TaskCreate, CrawlType, TaskStartResponse, ErrorResponse
from app.services.task_service import TaskService
from app.services.parser_service import CrawlScheduler
from app.config import get_settings

router = APIRouter()
settings = get_settings()


def get_task_service(db: Database = Depends(get_db)) -> TaskService:
    """Dependency для получения сервиса задач"""
    return TaskService(db)


def validate_date_not_before_2023(date_str: str, date_format: str, param_name: str) -> str:
    """
    Валидация даты - запрет дат ранее 01.01.2023
    
    Args:
        date_str: Строка с датой
        date_format: Формат даты
        param_name: Имя параметра для сообщения об ошибке
    
    Returns:
        Валидированная дата
    
    Raises:
        HTTPException: Если дата ранее 01.01.2023
    """
    try:
        if date_format == "%Y-%m-%d":
            parsed_date = datetime.strptime(date_str, date_format).date()
        elif date_format == "%Y-%m":
            parsed_date = datetime.strptime(date_str + "-01", "%Y-%m-%d").date()
        elif date_format == "%Y-W%W":
            # Парсим неделю в формате YYYY-Www
            year, week = date_str.split("-W")
            # Первая неделя года
            first_day = datetime(int(year), 1, 1)
            # Находим первый день нужной недели
            from datetime import timedelta
            days_to_add = (int(week) - 1) * 7
            parsed_date = (first_day + timedelta(days=days_to_add)).date()
        else:
            return date_str
        
        # Проверяем минимальную дату
        min_date = date(settings.min_date_year, settings.min_date_month, settings.min_date_day)
        
        if parsed_date < min_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Дата {param_name} не может быть ранее 01.01.2023"
            )
        
        return date_str
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверный формат даты для {param_name}: {str(e)}"
        )


def detect_pattern(date_param: str) -> str:
    """
    Определение паттерна по строке даты.
    
    Паттерны:
    - daily: YYYY-MM-DD (например, 2026-03-02)
    - weekly: YYYY-Www (например, 2026-W10)
    - monthly: YYYY-MM (например, 2026-03)
    
    Args:
        date_param: Строка с датой
        
    Returns:
        Паттерн: "daily", "weekly" или "monthly"
        
    Raises:
        ValueError: Если формат даты не распознан
    """
    # Проверяем monthly (YYYY-MM)
    if len(date_param) == 7 and date_param[4] == "-":
        try:
            int(date_param[:4])
            int(date_param[5:7])
            return "monthly"
        except ValueError:
            pass
    
    # Проверяем weekly (YYYY-Www)
    if "-W" in date_param:
        try:
            year_part, week_part = date_param.split("-W")
            int(year_part)
            int(week_part)
            return "weekly"
        except (ValueError, IndexError):
            pass
    
    # Проверяем daily (YYYY-MM-DD)
    if len(date_param) == 10 and date_param[4] == "-" and date_param[7] == "-":
        try:
            int(date_param[:4])
            int(date_param[5:7])
            int(date_param[8:10])
            return "daily"
        except ValueError:
            pass
    
    raise ValueError(f"Не удалось определить паттерн для: {date_param}")


def get_crawl_type_from_pattern(pattern: str) -> CrawlType:
    """Получение CrawlType из паттерна"""
    if pattern == "daily":
        return CrawlType.DAILY
    elif pattern == "weekly":
        return CrawlType.WEEKLY
    elif pattern == "monthly":
        return CrawlType.MONTHLY
    else:
        raise ValueError(f"Неизвестный паттерн: {pattern}")


@router.post(
    "/crawl",
    response_model=TaskStartResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Запуск краулинга",
    description="""
    Универсальный эндпоинт для запуска краулинга статей с Hugging Face Papers.
    
    Поддерживает три паттерна дат:
    - daily: YYYY-MM-DD (например, 2026-03-02)
    - weekly: YYYY-Www (например, 2026-W10)
    - monthly: YYYY-MM (например, 2026-03)
    
    Параметры:
    - start_date: обязательный параметр - начальная дата/неделя/месяц
    - end_date: опциональный параметр - конечная дата/неделя/месяц
    
    Если передан только start_date - выполняется краулинг одной страницы.
    Если передан start_date и end_date - выполняется итеративный обход диапазона.
    
    ВАЖНО: Паттерны start_date и end_date должны совпадать (оба daily, оба weekly или оба monthly).
    """
)
def crawl(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD, YYYY-Www или YYYY-MM)"),
    end_date: str = Query(None, description="Конечная дата (опционально, паттерн должен совпадать с start_date)"),
    service: TaskService = Depends(get_task_service)
):
    """
    Универсальный эндпоинт для запуска краулинга.
    
    Определяет паттерн автоматически по формату даты.
    Поддерживает как одиночный краулинг, так и диапазон.
    """
    
    # Определяем паттерн для start_date
    try:
        start_pattern = detect_pattern(start_date)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверный формат start_date: {str(e)}"
        )
    
    # Валидируем start_date
    if start_pattern == "daily":
        validate_date_not_before_2023(start_date, "%Y-%m-%d", "start_date")
    elif start_pattern == "weekly":
        validate_date_not_before_2023(start_date, "%Y-W%W", "start_date")
    elif start_pattern == "monthly":
        validate_date_not_before_2023(start_date, "%Y-%m", "start_date")
    
    # Если передан end_date - проверяем паттерн и валидируем
    if end_date:
        try:
            end_pattern = detect_pattern(end_date)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неверный формат end_date: {str(e)}"
            )
        
        # Проверяем, что паттерны совпадают
        if start_pattern != end_pattern:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Паттерны дат должны совпадать: start_date={start_pattern}, end_date={end_pattern}"
            )
        
        # Валидируем end_date
        if end_pattern == "daily":
            validate_date_not_before_2023(end_date, "%Y-%m-%d", "end_date")
        elif end_pattern == "weekly":
            validate_date_not_before_2023(end_date, "%Y-W%W", "end_date")
        elif end_pattern == "monthly":
            validate_date_not_before_2023(end_date, "%Y-%m", "end_date")
    
    # Определяем crawl_type по паттерну
    crawl_type = get_crawl_type_from_pattern(start_pattern)
    
    # Создаем задачу
    task_data = TaskCreate(
        crawl_type=crawl_type,
        date_param=start_date,
        crawl_pattern=start_pattern,
        start_param=start_date if end_date else None,
        end_param=end_date
    )
    
    task_id = service.create_task(task_data)
    service.start_crawl(task_id, task_data)
    
    # Формируем сообщение
    if end_date:
        message = f"{start_pattern.capitalize()} crawl from {start_date} to {end_date} started"
    else:
        message = f"{start_pattern.capitalize()} crawl for {start_date} started"
    
    return TaskStartResponse(
        task_id=task_id,
        status="started",
        message=message
    )
