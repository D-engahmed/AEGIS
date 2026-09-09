"""PostgreSQL schema migrations (layer 02 infrastructure).

A deliberately small, dependency-free migration runner: a versioned list of DDL
steps, applied in order inside transactions, with progress tracked in
`aegis_schema_versions`. Nothing here imports an ORM; the adapters in
`postgres.py` speak SQL directly.
"""

from __future__ import annotations

import psycopg

_MIGRATIONS: list[tuple[int, str]] = [
    (1, "initial aegis schema"),
]


def _ddl() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS aegis_schema_versions (
            version integer PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now(),
            note text
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS targets (
            id text PRIMARY KEY,
            organization_id text NOT NULL,
            project_id text NOT NULL,
            name text NOT NULL,
            target_type text NOT NULL,
            created_at timestamptz NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS target_versions (
            id text PRIMARY KEY,
            target_id text NOT NULL,
            organization_id text NOT NULL,
            project_id text NOT NULL,
            label text NOT NULL,
            config jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            commit_sha text,
            image_digest text,
            referenced boolean NOT NULL DEFAULT false
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS datasets (
            id text PRIMARY KEY,
            organization_id text NOT NULL,
            project_id text NOT NULL,
            name text NOT NULL,
            created_at timestamptz NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS dataset_versions (
            id text PRIMARY KEY,
            dataset_id text NOT NULL,
            organization_id text NOT NULL,
            project_id text NOT NULL,
            label text NOT NULL,
            status text NOT NULL,
            locked_at timestamptz
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS test_cases (
            id text PRIMARY KEY,
            dataset_version_id text NOT NULL,
            seq integer NOT NULL,
            input jsonb NOT NULL,
            expected jsonb,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_test_cases_dataset_version
            ON test_cases (dataset_version_id, seq)
        """,
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id text PRIMARY KEY,
            organization_id text NOT NULL,
            project_id text NOT NULL,
            name text NOT NULL,
            status text NOT NULL,
            clone_of text,
            created_at timestamptz NOT NULL,
            snapshot jsonb NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS runs (
            id text PRIMARY KEY,
            organization_id text NOT NULL,
            project_id text NOT NULL,
            experiment_id text NOT NULL,
            created_by text NOT NULL,
            created_at timestamptz NOT NULL,
            status text NOT NULL,
            started_at timestamptz,
            finished_at timestamptz,
            snapshot jsonb NOT NULL,
            evidence_summary jsonb,
            executions jsonb NOT NULL DEFAULT '[]'::jsonb,
            error jsonb,
            cancelled_by text,
            cancelled_at timestamptz,
            idempotency_key text UNIQUE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_runs_experiment ON runs (experiment_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS executions (
            id text PRIMARY KEY,
            run_id text NOT NULL,
            sequence integer NOT NULL,
            test_case_id text NOT NULL,
            target_version_id text NOT NULL,
            dataset_version_id text NOT NULL,
            status text NOT NULL,
            created_at timestamptz NOT NULL,
            started_at timestamptz,
            finished_at timestamptz,
            outcome jsonb,
            evidence_references jsonb NOT NULL DEFAULT '[]'::jsonb,
            failure jsonb,
            cancelled_by text,
            retries integer NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_executions_run ON executions (run_id, sequence)
        """,
        """
        CREATE TABLE IF NOT EXISTS metric_results (
            id text PRIMARY KEY,
            run_id text NOT NULL,
            execution_id text NOT NULL,
            test_case_id text NOT NULL,
            metric_name text NOT NULL,
            score double precision NOT NULL,
            evaluator_identity text NOT NULL,
            evaluator_version text NOT NULL,
            created_at timestamptz NOT NULL,
            confidence double precision NOT NULL,
            severity text NOT NULL,
            raw_value double precision,
            unit text,
            reason text,
            judge_model text,
            judge_prompt_version text,
            evidence jsonb NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_metric_results_run ON metric_results (run_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS evidence (
            id text PRIMARY KEY,
            metric_result_id text NOT NULL,
            run_id text NOT NULL,
            execution_id text NOT NULL,
            experiment_id text NOT NULL,
            evaluator_identity text NOT NULL,
            evaluator_version text NOT NULL,
            dataset_version_id text NOT NULL,
            target_version_id text NOT NULL,
            artifact_references jsonb NOT NULL DEFAULT '[]'::jsonb,
            provenance jsonb NOT NULL,
            classification text NOT NULL,
            created_at timestamptz NOT NULL,
            created_by text NOT NULL,
            judge_model text,
            judge_prompt_version text
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_evidence_run ON evidence (run_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_evidence_metric ON evidence (metric_result_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS evidence_artifacts (
            artifact_id text PRIMARY KEY,
            artifact_type text NOT NULL,
            storage_key text NOT NULL,
            content_hash text NOT NULL,
            size_bytes integer NOT NULL,
            content_type text NOT NULL,
            created_at timestamptz NOT NULL,
            payload bytea NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS gate_reports (
            run_id text PRIMARY KEY,
            verdict text NOT NULL,
            decisions jsonb NOT NULL,
            evaluated_at timestamptz NOT NULL,
            override jsonb
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS cancellations (
            run_id text PRIMARY KEY,
            identity text NOT NULL,
            cancelled_at timestamptz NOT NULL
        )
        """,
    ]


def _schema_statements() -> list[str]:
    return _ddl()


def apply_migrations(dsn: str) -> list[int]:
    """Apply pending migrations; returns the versions applied in this call."""
    applied: list[int] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS aegis_schema_versions (
                    version integer PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now(),
                    note text
                )
                """
            )
            cur.execute("SELECT version FROM aegis_schema_versions ORDER BY version")
            row = cur.fetchone()
        if row is None or row[0] != _MIGRATIONS[-1][0]:
            for version, note in _MIGRATIONS:
                if row is not None and version <= row[0]:
                    continue
                statements = _schema_statements() if version == 1 else []
                with conn.transaction(), conn.cursor() as cur:
                    for statement in statements:
                        cur.execute(statement)
                    cur.execute(
                        "INSERT INTO aegis_schema_versions (version, note) VALUES (%s, %s)",
                        (version, note),
                    )
                applied.append(version)
    return applied


__all__ = ["apply_migrations"]
