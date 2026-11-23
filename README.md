# kurs-mayak

Telegram-бот для мониторинга курсов валют и криптовалют.

## Backend contracts

`contracts.py` contains domain objects and errors; `ports.py` defines interfaces; `services.py` contains application services. Database writes are expected to run inside a Unit of Work and be committed by the caller.

## PostgreSQL schema and migrations

The Alembic history is intentionally split in dependency order:

1. `0001_catalog_and_sessions` creates `users`, `dialog_sessions`, `assets` and `pairs`, then seeds the supported catalogue.
2. `0002_quotes_storage` creates `quotes`, which has a foreign key to `pairs`.

The schema follows HLD 6 (pages 7–8):

- `users.telegram_user_id` is unique; `chat_id` is stored as `BIGINT`.
- `dialog_sessions.user_id` is both its primary key and a cascading foreign key to `users.id`, so one user cannot have more than one session. `version` is a positive `BIGINT`, initially `1`.
- `assets` contains RUB, USD, EUR, BTC and ETH. Provider IDs are `bitcoin` and `ethereum` for BTC and ETH.
- `pairs` contains directed fiat pairs between RUB/USD/EUR and BTC/ETH pairs quoted in RUB/USD/EUR. `(base_code, quote_code)` is unique; both codes reference `assets`.
- `quotes.price` is `NUMERIC` without fixed precision/scale; `quoted_at` and `received_at` are `TIMESTAMPTZ`; primary key is `(pair_id, source, series_kind, quoted_at)`, where `series_kind` is `live` or `hour`.

### Apply migrations

```sh
python -m pip install -r requirements.txt
# Set sqlalchemy.url in alembic.ini to your PostgreSQL URL.
python -m alembic upgrade head
```

To apply the revisions individually:

```sh
python -m alembic upgrade 0001_catalog_and_sessions
python -m alembic upgrade head
```

### Rewriting an already-applied local migration history

If the previous single-revision migration `0001_quotes_storage` has already been applied to a disposable development database, first keep the old project version (the one containing that old migration file) and run:

```sh
python -m alembic current
python -m alembic downgrade base
```

Only after that downgrade completes, replace the project with this version and run the two migrations in order. **This downgrade is destructive:** the previous migration drops `quotes`, `pairs` and `assets`. Back up the database first, and do not use this history-rewrite procedure on a database whose data must be preserved. If the old migration has not been applied, simply apply the new `head` on a clean database.

### Reload the supported catalogue

`infrastructure/db/catalog.py` exposes `seed_catalog(async_session)`. It upserts assets before pairs using their natural unique keys. Calling it repeatedly does not create duplicates. It preserves existing `enabled` flags; the caller owns transaction commit/rollback.

### Quote storage

`infrastructure/db/models.py` defines the SQLAlchemy 2 mappings. `infrastructure/db/quote_repository.py` implements async reads (`latest`, `get_series`) and an idempotent PostgreSQL `ON CONFLICT DO UPDATE`. The discriminator `series_kind` is part of the key and conflict target, so `hour` never overwrites `live`.

### Tests

```sh
python -m pytest -q
```

The tests validate domain contracts, SQL generation and catalogue seed idempotency with mocked sessions. For end-to-end database verification, apply migrations to a disposable PostgreSQL database and perform insert/select tests against PostgreSQL 18.
