# Hugging Face Papers Crawler

API для сбора данных со страниц [Hugging Face Papers](https://huggingface.co/papers).

## Примеры использования API

### Одиночный краулинг

**Один день:**
```bash
curl -X POST "http://localhost:8000/crawl/crawl?start_date=2026-03-02"
```

**Одна неделя:**
```bash
curl -X POST "http://localhost:8000/crawl/crawl?start_date=2026-W10"
```

**Один месяц:**
```bash
curl -X POST "http://localhost:8000/crawl/crawl?start_date=2026-03"
```

### Диапазон с итерацией

**Диапазон по дням (итерация каждый день):**
```bash
curl -X POST "http://localhost:8000/crawl/crawl?start_date=2026-03-01&end_date=2026-03-05"
```

**Диапазон по неделям (итерация каждая неделя):**
```bash
curl -X POST "http://localhost:8000/crawl/crawl?start_date=2026-W10&end_date=2026-W12"
```

**Диапазон по месяцам (итерация каждый месяц):**
```bash
curl -X POST "http://localhost:8000/crawl/crawl?start_date=2026-01&end_date=2026-03"
```

## Форматы дат

| Паттерн | Формат | Пример |
|---------|--------|--------|
| Daily   | YYYY-MM-DD | 2026-03-02 |
| Weekly  | YYYY-Www | 2026-W10 |
| Monthly | YYYY-MM | 2026-03 |

## Задержка между запросами

По умолчанию установлена задержка **1 секунда** между каждым краулингом в очереди, чтобы избежать перегрузки сервера Hugging Face.
