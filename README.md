# Mini SofaScore-like live football service

Мини-сервис на FastAPI, который показывает, как я бы сделал live football endpoint в стиле SofaScore.

## Что умеет сервис

- fixture mode: локальный `fixtures/live_payload.json` остаётся отдельным тестовым вариантом;
- polling mode: при наличии токена `football-data.org` запускается background poller;
- raw snapshot сохраняется как есть в SQLite;
- public API читает только normalized tables;
- `isEditor=true` события не попадают в public response;
- Swagger доступен на стандартном `/docs`;
- latency измеряется отдельно через benchmark.

## Что внутри

- `app/main.py` — FastAPI app и endpoint `/api/v1/sport/football/events/live`
- `app/db.py` — SQLite schema apply, ingestion, normalized reads
- `migrations/001_init.sql` — SQL schema и индексы
- `fixtures/live_payload.json` — reproducible fixture snapshot
- `app/benchmark.py` — p50/p95 benchmark
- `tests/test_live_api.py` — smoke tests

## Архитектура в двух словах

**Ingestion layer**

- fixture seed или polling real API
- raw payload пишется в `raw_snapshots` без изменений
- затем payload нормализуется в SQL таблицы

**Serving layer**

- `GET /api/v1/sport/football/events/live`
- читает только normalized DB
- не трогает raw snapshot в hot path

## Схема хранения

### Raw layer

`raw_snapshots`

- `payload` хранится неизменяемо
- ingestion пишет snapshot как append-only запись
- public API этот слой не читает

### Normalized layer

- `leagues`
- `teams`
- `events`

`events` содержит ссылки на league/team и поля для serving path:

- `status`
- `minute`
- `period`
- `start_time`
- `home_score` / `away_score`
- `is_editor`

## Environment variables

Файл `.env` читается автоматически при старте приложения, поэтому `--env-file` для `uvicorn` не нужен.

Основные переменные:

- `SOFASCORE_DB_PATH` — путь к SQLite-файлу;
- `SOFASCORE_FIXTURE_PATH` — путь к fixture snapshot;
- `SOFASCORE_AUTO_SEED` — автоматически засевать БД из fixture, если база пустая;
- `SOFASCORE_LOG_LEVEL` — уровень логирования (`DEBUG`, `INFO`, `WARNING`, ...);
- `SOFASCORE_FOOTBALL_DATA_TOKEN` — токен `football-data.org`; если пустой, остаётся fixture mode;
- `SOFASCORE_FOOTBALL_DATA_BASE_URL` — базовый URL football-data.org;
- `SOFASCORE_FOOTBALL_DATA_COMPETITIONS` — опциональные competition codes/IDs для polling;
- `SOFASCORE_FOOTBALL_DATA_POLL_INTERVAL_SECONDS` — период background polling;
- `SOFASCORE_FOOTBALL_DATA_TIMEOUT_SECONDS` — HTTP timeout для внешнего API.

Смотри `.env.example` как шаблон.

## Как запустить

```bash
cd /home/sana451/PycharmProjects/SofaScore
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Инициализировать БД

```bash
python -m app.cli init-db
```

### Засеять fixture вручную

```bash
python -m app.cli ingest-fixture
```

### Запустить API

```bash
uvicorn app.main:app --reload
```

Swagger:

- http://127.0.0.1:8000/docs

Endpoint:

- http://127.0.0.1:8000/api/v1/sport/football/events/live

### Включить polling mode

Если в `.env` задан `SOFASCORE_FOOTBALL_DATA_TOKEN`, приложение автоматически стартует в polling mode.

Пример:

```env
SOFASCORE_FOOTBALL_DATA_TOKEN=your-token
SOFASCORE_FOOTBALL_DATA_COMPETITIONS=PL
SOFASCORE_FOOTBALL_DATA_POLL_INTERVAL_SECONDS=30
```

В этом режиме background poller:

- ходит в `https://api.football-data.org/v4/matches?status=LIVE`;
- сохраняет raw snapshot как есть;
- нормализует данные в `leagues`, `teams`, `events`;
- не меняет public endpoint.

## Пример ответа

```json
{
  "events": [
    {
      "id": 5001,
      "slug": "arsenal-vs-chelsea",
      "status": "LIVE",
      "minute": 53,
      "period": "2H",
      "isEditor": false,
      "startTime": "2026-05-14T12:30:00Z",
      "league": {
        "id": 100,
        "name": "Premier League",
        "country": "England",
        "slug": "premier-league"
      },
      "homeTeam": {
        "id": 11,
        "name": "Arsenal",
        "shortName": "ARS",
        "country": "England"
      },
      "awayTeam": {
        "id": 12,
        "name": "Chelsea",
        "shortName": "CHE",
        "country": "England"
      },
      "scores": {"home": 2, "away": 1},
      "venueName": "Emirates Stadium"
    }
  ]
}
```

## Benchmark

Запустить:

```bash
python -m app.cli benchmark --iterations 1000 --warmup 100 --output benchmarks/latest.txt
```

Отчет с p50/p95 сохраняется в `benchmarks/latest.txt`.

## Formatting and linting

Установить `ruff` вместе с зависимостями:

```bash
pip install -r requirements.txt
```

Применить автоформатирование:

```bash
ruff format app tests
```

Проверить код без внесения изменений:

```bash
ruff check app tests
```

## Где был бы bottleneck

Главный bottleneck в реальном проекте был бы не в FastAPI, а в read-model под live feed:

- большое количество матчей и частые updates;
- конкурирующие writes во время ingestion;
- сложные joins при недостатке индексов;
- JSON serialization на горячем пути.

## Какие индексы нужны

Минимум:

- `events(is_editor, status, start_time)` — основной фильтр public live;
- `events(league_id, status, start_time)` — если нужен фильтр по турнирам;
- `events(home_team_id)` и `events(away_team_id)` — для быстрых lookups;
- `leagues(external_id)` и `teams(external_id)` — already unique.

## Как масштабировать ingestion

- отделить ingestion worker от API процесса;
- писать raw snapshot append-only;
- нормализацию делать асинхронно или через очередь;
- использовать idempotent upserts по external_id;
- при росте нагрузки — partitioning по дате snapshot или по sport/league.

## Риски raw snapshot + normalized DB

- рассинхронизация raw и normalized слоев;
- schema drift у внешнего payload;
- двойное хранение увеличивает disk usage;
- при плохом backfill можно получить stale serving data;
- нужен контракт на версионирование fixture / source payload.
