# Mini SofaScore-like live football service
Мини-сервис на FastAPI, который показывает, как я бы сделал live football endpoint в стиле SofaScore:
- fixture ingestion вместо внешнего API;
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
### Запустить API
```bash
uvicorn app.main:app --reload
```
Swagger:
- http://127.0.0.1:8000/docs
Endpoint:
- http://127.0.0.1:8000/api/v1/sport/football/events/live
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

Если хотите встроить это в pre-commit, тот же набор команд можно повесить на hook.

## Короткий разбор для интервью
### Где был бы bottleneck
Главный bottleneck в реальном проекте был бы не в FastAPI, а в read-model под live feed:
- большое количество матчей и частые updates;
- конкурирующие writes во время ingestion;
- сложные joins при недостатке индексов;
- JSON serialization на горячем пути.
### Какие индексы нужны
Минимум:
- `events(is_editor, status, start_time)` — основной фильтр public live;
- `events(league_id, status, start_time)` — если нужен фильтр по турнирам;
- `events(home_team_id)` и `events(away_team_id)` — для быстрых lookups;
- `leagues(external_id)` и `teams(external_id)` — already unique.
### Как масштабировать ingestion
- отделить ingestion worker от API процесса;
- писать raw snapshot append-only;
- нормализацию делать асинхронно или через очередь;
- использовать idempotent upserts по external_id;
- при росте нагрузки — partitioning по дате snapshot или по sport/league.
### Риски raw snapshot + normalized DB
- рассинхронизация raw и normalized слоев;
- schema drift у внешнего payload;
- двойное хранение увеличивает disk usage;
- при плохом backfill можно получить stale serving data;
- нужен контракт на версионирование fixture / source payload.
