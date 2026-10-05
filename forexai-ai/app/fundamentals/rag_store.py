import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg  # type: ignore[import-not-found]
from psycopg.rows import dict_row  # type: ignore[import-not-found]

from app.config import (
    rag_db_hostaddr,
    rag_db_sslmode,
)
from app.fundamentals.models import (
    EconomicObservation,
)


class FundamentalRAGStore:
    def __init__(self) -> None:
        self.connection_kwargs = {
            "host": os.getenv(
                "RAG_DB_HOST",
                "127.0.0.1",
            ),
            "port": int(
                os.getenv(
                    "RAG_DB_PORT",
                    "5432",
                )
            ),
            "dbname": os.getenv(
                "RAG_DB_NAME",
                "forexai",
            ),
            "user": os.getenv(
                "RAG_DB_USER",
                "postgres",
            ),
            "password": os.getenv(
                "RAG_DB_PASSWORD",
                "",
            ),
            # Managed Postgres (Neon) refuses a plaintext handshake, and
            # libpq's default of "prefer" tries that first and fails with
            # "connection is insecure (try using sslmode=require)". Set
            # explicitly so TLS is negotiated on the first attempt.
            "sslmode": rag_db_sslmode(),
            # Optional: skip the AAAA records a free-tier host cannot route
            # to. None lets psycopg resolve normally.
            "hostaddr": rag_db_hostaddr(),
        }

    def _connect(self):
        return psycopg.connect(
            **self.connection_kwargs,
            row_factory=dict_row,
        )

    def initialize(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS
                    fundamental_documents (
                        id BIGSERIAL PRIMARY KEY,
                        record_id TEXT NOT NULL UNIQUE,
                        source TEXT NOT NULL,
                        country_code TEXT,
                        currency TEXT NOT NULL,
                        indicator_code TEXT NOT NULL,
                        indicator_name TEXT NOT NULL,
                        period TEXT NOT NULL,
                        observation_date DATE,
                        value DOUBLE PRECISION,
                        unit TEXT,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        search_vector TSVECTOR NOT NULL,
                        ingested_at TIMESTAMPTZ NOT NULL
                            DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS
                    ix_fundamental_documents_currency
                    ON fundamental_documents(currency);

                    CREATE INDEX IF NOT EXISTS
                    ix_fundamental_documents_source
                    ON fundamental_documents(source);

                    CREATE INDEX IF NOT EXISTS
                    ix_fundamental_documents_indicator
                    ON fundamental_documents(indicator_code);

                    CREATE INDEX IF NOT EXISTS
                    ix_fundamental_documents_observation_date
                    ON fundamental_documents(observation_date);

                    CREATE INDEX IF NOT EXISTS
                    ix_fundamental_documents_search
                    ON fundamental_documents
                    USING GIN(search_vector);

                    CREATE TABLE IF NOT EXISTS
                    fundamental_source_refresh (
                        source_scope TEXT PRIMARY KEY,
                        refreshed_at TIMESTAMPTZ NOT NULL
                    );
                    """
                )

            connection.commit()

    def upsert_documents(
        self,
        observations: list[EconomicObservation],
    ) -> None:
        if not observations:
            return

        with self._connect() as connection:
            with connection.cursor() as cursor:
                for item in observations:
                    search_text = " ".join(
                        [
                            item.currency,
                            item.country_code or "",
                            item.indicator_code,
                            item.indicator_name,
                            item.period,
                            item.content,
                        ]
                    )

                    cursor.execute(
                        """
                        INSERT INTO fundamental_documents (
                            record_id,
                            source,
                            country_code,
                            currency,
                            indicator_code,
                            indicator_name,
                            period,
                            observation_date,
                            value,
                            unit,
                            content,
                            metadata,
                            search_vector,
                            ingested_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            to_tsvector('english', %s),
                            NOW()
                        )
                        ON CONFLICT (record_id)
                        DO UPDATE SET
                            value = EXCLUDED.value,
                            unit = EXCLUDED.unit,
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            observation_date =
                                EXCLUDED.observation_date,
                            search_vector =
                                EXCLUDED.search_vector,
                            ingested_at = NOW()
                        """,
                        (
                            item.record_id,
                            item.source,
                            item.country_code,
                            item.currency,
                            item.indicator_code,
                            item.indicator_name,
                            item.period,
                            item.observation_date,
                            item.value,
                            item.unit,
                            item.content,
                            json.dumps(
                                item.metadata
                            ),
                            search_text,
                        ),
                    )

            connection.commit()

    def is_fresh(
        self,
        source_scope: str,
        max_age_hours: int,
    ) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT refreshed_at
                    FROM fundamental_source_refresh
                    WHERE source_scope = %s
                    """,
                    (source_scope,),
                )

                row = cursor.fetchone()

        if not row:
            return False

        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(
                hours=max_age_hours
            )
        )

        return row["refreshed_at"] >= cutoff

    def mark_fresh(
        self,
        source_scope: str,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO
                    fundamental_source_refresh (
                        source_scope,
                        refreshed_at
                    )
                    VALUES (%s, NOW())
                    ON CONFLICT (source_scope)
                    DO UPDATE SET
                        refreshed_at = NOW()
                    """,
                    (source_scope,),
                )

            connection.commit()

    @staticmethod
    def _prepare_search_query(
        query: str,
    ) -> str:
        """
        Prepare a retrieval query for PostgreSQL websearch_to_tsquery.

        A normal whitespace-separated query such as:

            inflation unemployment GDP payroll

        is converted to:

            inflation OR unemployment OR GDP OR payroll

        This prevents one economic observation from needing to
        contain every requested indicator.

        Queries that already contain search operators or quoted
        phrases are preserved.
        """

        normalized = query.strip()

        if not normalized:
            raise ValueError(
                "Fundamental RAG query cannot be empty."
            )

        upper = normalized.upper()

        contains_search_syntax = any(
            token in upper
            for token in (
                " OR ",
                " AND ",
                " -",
                '"',
            )
        )

        if contains_search_syntax:
            return normalized

        terms = [
            term.strip()
            for term in normalized.replace(
                ",",
                " ",
            ).split()
            if term.strip()
        ]

        if not terms:
            raise ValueError(
                "Fundamental RAG query contains no searchable terms."
            )

        return " OR ".join(terms)

    def retrieve(
        self,
        currencies: list[str],
        query: str,
        limit: int = 16,
    ) -> list[dict[str, Any]]:
        if not currencies:
            return []

        if limit <= 0:
            return []

        search_query = self._prepare_search_query(
            query
        )

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH search AS (
                        SELECT websearch_to_tsquery(
                            'english',
                            %s
                        ) AS query
                    ),
                    ranked AS (
                        SELECT
                            fd.id,
                            fd.source,
                            fd.country_code,
                            fd.currency,
                            fd.indicator_code,
                            fd.indicator_name,
                            fd.period,
                            fd.observation_date,
                            fd.value,
                            fd.unit,
                            fd.content,
                            fd.metadata,

                            ts_rank_cd(
                                fd.search_vector,
                                search.query
                            ) AS relevance,

                            ROW_NUMBER() OVER (
                                PARTITION BY
                                    fd.currency,
                                    fd.indicator_code
                                ORDER BY
                                    ts_rank_cd(
                                        fd.search_vector,
                                        search.query
                                    ) DESC,
                                    fd.observation_date DESC
                                        NULLS LAST,
                                    fd.id DESC
                            ) AS indicator_rank

                        FROM fundamental_documents fd
                        CROSS JOIN search

                        WHERE fd.currency = ANY(%s)
                          AND fd.search_vector @@
                              search.query
                    )
                    SELECT
                        id,
                        source,
                        country_code,
                        currency,
                        indicator_code,
                        indicator_name,
                        period,
                        observation_date,
                        value,
                        unit,
                        content,
                        metadata,
                        relevance
                    FROM ranked
                    WHERE indicator_rank <= 3
                    ORDER BY
                        relevance DESC,
                        observation_date DESC
                            NULLS LAST,
                        id DESC
                    LIMIT %s
                    """,
                    (
                        search_query,
                        [
                            currency.upper()
                            for currency in currencies
                        ],
                        limit,
                    ),
                )

                return cursor.fetchall()