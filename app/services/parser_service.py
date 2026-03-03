"""
Сервис для парсинга страниц Hugging Face Papers с использованием httpx
"""
import asyncio
import httpx
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from lxml import etree
import logging
import random

from app.config import get_settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы для ретраев
MAX_RETRIES = 5
INITIAL_DELAY = 1.0  # начальная задержка в секундах
MAX_DELAY = 60.0  # максимальная задержка в секундах


class HFPapersParser:
    """Парсер для Hugging Face Papers"""
    
    BASE_URL = "https://huggingface.co"
    
    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()
    
    async def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """
        Выполнение HTTP-запроса с ретраями при ошибках соединения
        
        Args:
            method: HTTP метод (GET, POST и т.д.)
            url: URL для запроса
            **kwargs: дополнительные аргументы для httpx
            
        Returns:
            Response объект
            
        Raises:
            httpx.HTTPStatusError: при исчерпании ретраев
        """
        last_exception = None
        
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
                
            except (httpx.RemoteProtocolError,
                    httpx.ConnectError,
                    httpx.ConnectTimeout,
                    httpx.ReadTimeout,
                    httpx.WriteTimeout,
                    httpx.PoolTimeout) as e:
                last_exception = e
                delay = min(INITIAL_DELAY * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                
                logger.warning(
                    f"[retry] Attempt {attempt + 1}/{MAX_RETRIES} failed for {url}: {type(e).__name__}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[retry] All {MAX_RETRIES} attempts failed for {url}")
                    
            except httpx.HTTPStatusError as e:
                # Для HTTP ошибок (4xx, 5xx) не делаем ретраи
                raise
        
        # Если все ретраи исчерпаны
        raise last_exception
    
    def _parse_html(self, html: str) -> etree._Element:
        """Парсинг HTML в lxml дерево"""
        return etree.HTML(html)
    
    def _extract_crawl_date_from_url(self, url: str) -> Optional[str]:
        """Извлечение даты краулинга из URL"""
        # Формат: /papers/date/2024-12-01
        if "/papers/date/" in url:
            parts = url.split("/papers/date/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        # Формат: /papers/week/2024-W50
        elif "/papers/week/" in url:
            parts = url.split("/papers/week/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        # Формат: /papers/month/2024-12
        elif "/papers/month/" in url:
            parts = url.split("/papers/month/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        return None
    
    def _parse_paper_element(self, paper_element, response_url: str) -> Optional[Dict[str, Any]]:
        """Парсинг одного элемента статьи из списка"""
        # Ищем ссылку на статью
        link_nodes = paper_element.xpath(".//h3/a[contains(@href, '/papers/')]")
        if not link_nodes:
            return None
        
        link_node = link_nodes[0]
        relative_path = link_node.get("href", "")
        absolute_url = f"{self.BASE_URL}{relative_path}" if relative_path.startswith("/") else relative_path
        
        # Заголовок
        title_nodes = link_node.xpath(".//text()")
        title = "".join(title_nodes).strip()
        
        # Авторы
        author_nodes = paper_element.xpath(".//a//ul//li/@title")
        authors = [x.strip() for x in author_nodes]
        
        # Количество ревью
        review_nodes = paper_element.xpath(".//a[contains(@href, '#community')]/text()")
        num_reviews = None
        if review_nodes:
            try:
                num_reviews = int(review_nodes[-1].strip())
            except (ValueError, TypeError):
                pass
        
        # Рейтинг
        rating_nodes = paper_element.xpath(".//div[@class='leading-none']/text()")
        rating_value = None
        if rating_nodes:
            try:
                rating_value = int(rating_nodes[0].strip())
            except (ValueError, TypeError):
                pass
        
        return {
            "id": absolute_url.split("/")[-1],
            "path": relative_path,
            "url": absolute_url,
            "parsed_at": datetime.now().isoformat(),
            "title": title,
            "authors": authors,
            "rating": rating_value,
            "num_reviews": num_reviews,
        }
    
    async def parse_list_page(self, url: str) -> Dict[str, Any]:
        """
        Парсинг страницы списка статей (daily/weekly/monthly)
        
        Возвращает данные со страницы списка
        """
        logger.info(f"[parse_list_page] Fetching: {url}")
        
        response = await self._request_with_retry("GET", url)
        
        tree = self._parse_html(response.text)
        
        # Извлекаем дату краулинга
        crawl_date = self._extract_crawl_date_from_url(url)
        
        # Находим все статьи на странице
        paper_elements = tree.xpath("//article[.//h3/a[contains(@href, '/papers/')]]")
        
        page_papers = []
        for element in paper_elements:
            paper_data = self._parse_paper_element(element, url)
            if paper_data:
                page_papers.append(paper_data)
        
        # Определяем тип списка и ключ из URL
        url_parts = url.rstrip("/").split("/")
        list_type = url_parts[-2] if len(url_parts) >= 2 else "unknown"
        list_key = url_parts[-1]
        
        result = {
            "list_key": list_key,
            "list_type": list_type,
            "url": url,
            "papers_on_page": page_papers,
            "parsed_at": datetime.now().isoformat(),
            "crawl_date": crawl_date,
        }
        
        logger.info(f"[parse_list_page] Found {len(page_papers)} papers on {url}")
        
        return result
    
    async def parse_paper_page(self, url: str, crawl_date: Optional[str] = None, authors: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Парсинг страницы отдельной статьи
        
        Возвращает полные данные статьи
        """
        logger.info(f"[parse_paper_page] Fetching: {url}")
        
        response = await self._request_with_retry("GET", url)
        
        tree = self._parse_html(response.text)
        
        # Получаем дату краулинга из meta или вычисляем из URL
        if not crawl_date:
            crawl_date = self._extract_crawl_date_from_url(url)
        
        # Заголовок
        title_nodes = tree.xpath("//h1/../..//h1/text()")
        title = "".join(title_nodes).strip()
        
        # Abstract
        abstract_nodes = tree.xpath("//h2[contains(text(), 'Abstract')]/following-sibling::div[1]//text()")
        abstract = " ".join([text.strip() for text in abstract_nodes]).strip()
        
        # Ссылки
        link_nodes = tree.xpath("//h1/../..//a[contains(@class, 'btn')]/@href")
        http_links = [link for link in link_nodes if link.startswith("http")]
        
        # ArXiv URL
        arxiv_url = next(
            (link for link in http_links if "arxiv.org" in link), None
        )
        arxiv_id = arxiv_url.split("/")[-1] if arxiv_url else None
        
        result = {
            "paper_id": url.split("/")[-1],
            "url": url,
            "title": title,
            "abstract": abstract,
            "links": http_links,
            "arxiv_id": arxiv_id,
            "parsed_at": datetime.now().isoformat(),
            "crawl_date": crawl_date,
            "authors": authors or [],
        }
        
        logger.info(f"[parse_paper_page] Parsed paper: {title[:50]}...")
        
        return result


class CrawlScheduler:
    """
    Планировщик задач краулинга.
    Каждый эндпоинт (daily/weekly/monthly) ставит в очередь ровно ОДНУ страницу.
    """
    
    def __init__(self, db):
        self.db = db
        self.parser = HFPapersParser()
        self.papers_collection = db.papers
        self.list_pages_collection = db.list_pages
    
    async def close(self):
        """Закрытие парсера"""
        await self.parser.close()
    
    async def crawl_daily(self, date_param: str) -> Dict[str, Any]:
        """
        Краулинг страницы за конкретный день.
        Ставит в очередь ровно ОДНУ страницу.
        """
        url = f"{HFPapersParser.BASE_URL}/papers/date/{date_param}"
        
        # Парсим страницу списка
        list_page_data = await self.parser.parse_list_page(url)
        
        # Сохраняем в БД
        self.list_pages_collection.insert_one(list_page_data)
        
        # Сохраняем статьи
        papers = list_page_data.get("papers_on_page", [])
        for paper in papers:
            paper["crawl_date"] = date_param
            self.papers_collection.update_one(
                {"url": paper["url"]},
                {"$set": paper},
                upsert=True
            )
        
        return {
            "url": url,
            "papers_count": len(papers),
            "crawl_date": date_param
        }
    
    async def crawl_weekly(self, week: str) -> Dict[str, Any]:
        """
        Краулинг страницы за конкретную неделю.
        Ставит в очередь ровно ОДНУ страницу.
        """
        url = f"{HFPapersParser.BASE_URL}/papers/week/{week}"
        
        # Парсим страницу списка
        list_page_data = await self.parser.parse_list_page(url)
        
        # Сохраняем в БД
        self.list_pages_collection.insert_one(list_page_data)
        
        # Сохраняем статьи
        papers = list_page_data.get("papers_on_page", [])
        for paper in papers:
            paper["crawl_date"] = week
            self.papers_collection.update_one(
                {"url": paper["url"]},
                {"$set": paper},
                upsert=True
            )
        
        return {
            "url": url,
            "papers_count": len(papers),
            "crawl_date": week
        }
    
    async def crawl_monthly(self, month: str) -> Dict[str, Any]:
        """
        Краулинг страницы за конкретный месяц.
        Ставит в очередь ровно ОДНУ страницу.
        """
        url = f"{HFPapersParser.BASE_URL}/papers/month/{month}"
        
        # Парсим страницу списка
        list_page_data = await self.parser.parse_list_page(url)
        
        # Сохраняем в БД
        self.list_pages_collection.insert_one(list_page_data)
        
        # Сохраняем статьи
        papers = list_page_data.get("papers_on_page", [])
        for paper in papers:
            paper["crawl_date"] = month
            self.papers_collection.update_one(
                {"url": paper["url"]},
                {"$set": paper},
                upsert=True
            )
        
        return {
            "url": url,
            "papers_count": len(papers),
            "crawl_date": month
        }
    
    # Задержка между запросами (в секундах)
    CRAWL_DELAY = 1.0
    
    async def _apply_delay(self):
        """Применение задержки между запросами"""
        await asyncio.sleep(self.CRAWL_DELAY)
    
    @staticmethod
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
    
    @staticmethod
    def parse_date_param(date_param: str, pattern: str) -> date:
        """
        Парсинг параметра даты в объект date.
        
        Args:
            date_param: Строка с датой
            pattern: Паттерн (daily, weekly, monthly)
            
        Returns:
            Объект date
        """
        if pattern == "daily":
            return datetime.strptime(date_param, "%Y-%m-%d").date()
        elif pattern == "weekly":
            # Парсим неделю в формате YYYY-Www
            year, week = date_param.split("-W")
            # Первая неделя года
            first_day = datetime(int(year), 1, 1)
            # Находим первый день нужной недели
            days_to_add = (int(week) - 1) * 7
            return (first_day + timedelta(days=days_to_add)).date()
        elif pattern == "monthly":
            # Первый день месяца
            return datetime.strptime(date_param + "-01", "%Y-%m-%d").date()
        else:
            raise ValueError(f"Неизвестный паттерн: {pattern}")
    
    @staticmethod
    def format_date_param(d: date, pattern: str) -> str:
        """
        Форматирование даты в строку согласно паттерну.
        
        Args:
            d: Объект date
            pattern: Паттерн (daily, weekly, monthly)
            
        Returns:
            Строка с датой в нужном формате
        """
        if pattern == "daily":
            return d.strftime("%Y-%m-%d")
        elif pattern == "weekly":
            # Находим номер недели
            year, week_num, _ = d.isocalendar()
            return f"{year}-W{week_num:02d}"
        elif pattern == "monthly":
            return d.strftime("%Y-%m")
        else:
            raise ValueError(f"Неизвестный паттерн: {pattern}")
    
    def _get_next_date(self, current: date, pattern: str) -> date:
        """
        Получение следующей даты согласно паттерну.
        
        Args:
            current: Текущая дата
            pattern: Паттерн (daily, weekly, monthly)
            
        Returns:
            Следующая дата
        """
        if pattern == "daily":
            return current + timedelta(days=1)
        elif pattern == "weekly":
            return current + timedelta(weeks=1)
        elif pattern == "monthly":
            # Умный переход между месяцами
            year = current.year
            month = current.month
            
            if month == 12:
                # Переход через год
                return date(year + 1, 1, 1)
            else:
                return date(year, month + 1, 1)
        else:
            raise ValueError(f"Неизвестный паттерн: {pattern}")
    
    async def crawl_pattern_range(
        self,
        start_param: str,
        end_param: str,
        pattern: str
    ) -> List[Dict[str, Any]]:
        """
        Краулинг диапазона по указанному паттерну.
        
        Поддерживает:
        - daily: итерация по дням (YYYY-MM-DD)
        - weekly: итерация по неделям (YYYY-Www)
        - monthly: итерация по месяцам (YYYY-MM)
        
        Args:
            start_param: Начальный параметр (день/неделя/месяц)
            end_param: Конечный параметр (день/неделя/месяц)
            pattern: Паттерн (daily, weekly, monthly)
            
        Returns:
            Список результатов для каждого шага итерации
        """
        results = []
        
        # Парсим начальную и конечную даты
        start_date = self.parse_date_param(start_param, pattern)
        end_date = self.parse_date_param(end_param, pattern)
        
        logger.info(f"[crawl_pattern_range] Starting {pattern} crawl from {start_param} to {end_param}")
        
        current = start_date
        iteration = 0
        
        while current <= end_date:
            iteration += 1
            current_param = self.format_date_param(current, pattern)
            
            logger.info(f"[crawl_pattern_range] Iteration {iteration}: crawling {current_param}")
            
            # Выполняем краулинг в зависимости от паттерна
            if pattern == "daily":
                result = await self.crawl_daily(current_param)
            elif pattern == "weekly":
                result = await self.crawl_weekly(current_param)
            elif pattern == "monthly":
                result = await self.crawl_monthly(current_param)
            else:
                raise ValueError(f"Неизвестный паттерн: {pattern}")
            
            results.append(result)
            
            # Применяем задержку между запросами
            await self._apply_delay()
            
            # Переходим к следующей дате
            current = self._get_next_date(current, pattern)
        
        logger.info(f"[crawl_pattern_range] Completed {iteration} iterations")
        
        return results
    
    async def crawl_range(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Краулинг диапазона дат (для fetch_all).
        Каждый день - отдельная страница в очереди.
        """
        results = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            result = await self.crawl_daily(date_str)
            results.append(result)
            # Применяем задержку
            await self._apply_delay()
            current_date += timedelta(days=1)
        
        return results

