# ForexAI Database Schema

PostgreSQL 17. App tables are managed by EF Core (`ForexAiDbContext`); the RAG tables are created by `FundamentalRAGStore.initialize()` with raw SQL. Table names below are the physical names (`forex_pairs`, `trading_signals`, `fundamental_documents`, ...).

```text
users ──1──┐
           ├──< trading_signals >──1──< signal_audit_events
forex_pairs ─1──┤
           ├──< market_candles
           └──< market_analyses

fundamental_documents (standalone RAG store, no FKs)
fundamental_source_refresh (bookkeeping, no FKs)
+ ASP.NET Identity tables (AspNetUsers, AspNetRoles, ...)
```

## Core Trading Tables (EF Core)

### users

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| id | uuid | PK, default `gen_random_uuid()` |
| email | text / citext | NOT NULL, UNIQUE |
| display_name | text | NOT NULL |
| created_at | timestamptz | NOT NULL, default `NOW()` |

### forex_pairs

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| id | uuid | PK |
| symbol | text (e.g. `EURUSD`) | NOT NULL, UNIQUE |
| base_currency | char(3) | NOT NULL |
| quote_currency | char(3) | NOT NULL |
| is_active | boolean | NOT NULL, default `true` |

### trading_signals

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| id | uuid | PK |
| user_id | uuid | NOT NULL, FK → `users.id` |
| forex_pair_id | uuid | NOT NULL, FK → `forex_pairs.id` |
| direction | enum `Buy, Sell, Hold, NoTrade` | NOT NULL |
| confidence | numeric(4,3) | NOT NULL, CHECK 0–1 |
| entry_price | numeric(18,6) | NOT NULL, CHECK > 0 |
| stop_loss | numeric(18,6) | NOT NULL, CHECK > 0 |
| take_profit | numeric(18,6) | NOT NULL, CHECK > 0 |
| risk_reward | numeric(10,4) | NOT NULL, CHECK > 0 |
| timeframe | enum (OneMinute…OneDay) | NOT NULL |
| status | enum `Generated, UnderReview, Accepted, Rejected` | NOT NULL, default `Generated` |
| reasoning | text | NOT NULL |
| created_at | timestamptz | NOT NULL, default `NOW()` |

Domain invariants: Buy requires `stop_loss < entry_price < take_profit`; Sell requires `take_profit < entry_price < stop_loss`.

### signal_audit_events

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| id | uuid | PK |
| signal_id | uuid | NOT NULL, FK → `trading_signals.id` ON DELETE CASCADE |
| event_type | text (e.g. `Accepted`, `Rejected`) | NOT NULL |
| reason | text | NULLABLE |
| created_at | timestamptz | NOT NULL, default `NOW()` |

### market_candles

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| id | uuid | PK |
| forex_pair_id | uuid | NOT NULL, FK → `forex_pairs.id` |
| timestamp | timestamptz | NOT NULL |
| open / high / low / close | numeric(18,6) | NOT NULL, CHECK `high >= open, close >= low` |
| volume | numeric(18,6) | NOT NULL, CHECK >= 0 |
| timeframe | enum | NOT NULL |

UNIQUE `(forex_pair_id, timeframe, timestamp)`.

### market_analyses

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| id | uuid | PK |
| forex_pair_id | uuid | NOT NULL, FK → `forex_pairs.id` |
| trend | text | NOT NULL |
| volatility | numeric(10,6) | NOT NULL, CHECK >= 0 |
| market_regime | text | NOT NULL |
| summary | text | NOT NULL |
| created_at | timestamptz | NOT NULL, default `NOW()` |

## RAG / Fundamentals Store (raw SQL)

### fundamental_documents

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| id | bigserial | PK |
| record_id | text (`source:country:indicator:period`) | NOT NULL, UNIQUE |
| source | text (`world_bank`, `sotw`, `business_quant`) | NOT NULL, INDEX |
| country_code | char(2) | NULLABLE |
| currency | char(3) | NOT NULL, INDEX |
| indicator_code | text | NOT NULL, INDEX |
| indicator_name | text | NOT NULL |
| period | text | NOT NULL |
| observation_date | date | NULLABLE, INDEX |
| value | double precision | NULLABLE |
| unit | text | NULLABLE |
| content | text | NOT NULL |
| metadata | jsonb | NOT NULL, default `'{}'` |
| search_vector | tsvector | NOT NULL, GIN INDEX |
| ingested_at | timestamptz | NOT NULL, default `NOW()` |

### fundamental_source_refresh

| Field | Type | Constraints |
| ----- | ---- | ----------- |
| source_scope | text | PK |
| refreshed_at | timestamptz | NOT NULL |

ASP.NET Identity tables (`AspNetUsers`, `AspNetRoles`, `AspNetUserRoles`, ...) are managed by `IdentityDbContext` and join on `Guid` keys.

## Relationships

One `forex_pair` has many `trading_signals`, `market_candles` and `market_analyses`, and one `trading_signal` has many `signal_audit_events` (human accept/reject trail). One `user` owns many `trading_signals`, while `fundamental_documents` is a standalone RAG store partitioned by `(currency, indicator_code)` with no foreign keys into the trading tables.



