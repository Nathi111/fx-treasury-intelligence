from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.load.postgres import finish_etl_run, start_etl_run
from src import pipeline


def _engine_with_connection():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    return engine, conn


def test_start_etl_run_returns_generated_run_id():
    engine, conn = _engine_with_connection()
    result = MagicMock()
    result.scalar_one.return_value = 42
    conn.execute.return_value = result

    run_id = start_etl_run(engine)

    assert run_id == 42
    sql_text = str(conn.execute.call_args.args[0])
    assert "INSERT INTO ops.etl_run" in sql_text
    assert "RETURNING run_id" in sql_text


def test_finish_etl_run_updates_status_counts_and_error():
    engine, conn = _engine_with_connection()
    result = MagicMock()
    result.rowcount = 1
    conn.execute.return_value = result

    finish_etl_run(
        engine,
        42,
        status="FAILED",
        fx_rows_processed=12,
        macro_rows_processed=8,
        po_rows_processed=180,
        error_message="RuntimeError: quality gate failed",
    )

    params = conn.execute.call_args.args[1]
    assert params == {
        "run_id": 42,
        "status": "FAILED",
        "fx_rows_processed": 12,
        "macro_rows_processed": 8,
        "po_rows_processed": 180,
        "error_message": "RuntimeError: quality gate failed",
    }


def test_finish_etl_run_rejects_running_status():
    engine, _ = _engine_with_connection()

    with pytest.raises(ValueError, match="SUCCESS or FAILED"):
        finish_etl_run(
            engine,
            42,
            status="RUNNING",
            fx_rows_processed=0,
            macro_rows_processed=0,
            po_rows_processed=0,
        )


def test_main_records_successful_run_counts():
    engine = MagicMock()
    settings = SimpleNamespace(database_url="postgresql://example")

    def successful_run(_engine, _settings, counts, _run_id):
        counts.update({"fx": 15, "macro": 8, "po": 180})

    with (
        patch.object(pipeline, "get_settings", return_value=settings),
        patch.object(pipeline, "make_engine", return_value=engine),
        patch.object(pipeline, "bootstrap_audit_database"),
        patch.object(pipeline, "start_etl_run", return_value=101),
        patch.object(pipeline, "run_pipeline", side_effect=successful_run),
        patch.object(pipeline, "finish_etl_run") as finish,
    ):
        pipeline.main()

    finish.assert_called_once_with(
        engine,
        101,
        status="SUCCESS",
        fx_rows_processed=15,
        macro_rows_processed=8,
        po_rows_processed=180,
    )


def test_main_records_failed_run_and_preserves_partial_counts():
    engine = MagicMock()
    settings = SimpleNamespace(database_url="postgresql://example")

    def failed_run(_engine, _settings, counts, _run_id):
        counts["fx"] = 15
        raise RuntimeError("Data-quality gate failed")

    with (
        patch.object(pipeline, "get_settings", return_value=settings),
        patch.object(pipeline, "make_engine", return_value=engine),
        patch.object(pipeline, "bootstrap_audit_database"),
        patch.object(pipeline, "start_etl_run", return_value=102),
        patch.object(pipeline, "run_pipeline", side_effect=failed_run),
        patch.object(pipeline, "finish_etl_run") as finish,
        pytest.raises(RuntimeError, match="Data-quality gate failed"),
    ):
        pipeline.main()

    finish.assert_called_once_with(
        engine,
        102,
        status="FAILED",
        fx_rows_processed=15,
        macro_rows_processed=0,
        po_rows_processed=0,
        error_message="RuntimeError: Data-quality gate failed",
    )
