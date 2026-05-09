from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, TYPE_CHECKING

from app.application.etl_service import EtlApplicationService
from app.application.pipeline_service import PipelineApplicationService
from app.domain.enums import PipelineJob
from app.infrastructure.config import Settings
from app.infrastructure.repositories.batch_job_log import BatchJobLogRepository
from app.infrastructure.repositories.etl_sync_repository import EtlSyncRepository
from app.infrastructure.repositories.pipeline_mysql import MysqlPipelineRepository

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

JOB_PIPELINE_INITIAL = "pipeline.initial"
JOB_PIPELINE_COMPLETION = "pipeline.completion"
JOB_ETL_WEARABLE_SLOT = "etl.wearable_slot"
JOB_ETL_POSTGRES_TO_MYSQL = "etl.postgres_to_mysql"
JOB_ETL_MYSQL_TO_POSTGRES = "etl.mysql_to_postgres"


def pipeline_job_name(job: PipelineJob) -> str:
    if job is PipelineJob.INITIAL:
        return JOB_PIPELINE_INITIAL
    return JOB_PIPELINE_COMPLETION


def _execute_batch_job(
    *,
    session: "Session",
    settings: Settings,
    job_name: str,
    postgres_engine: "Engine | None",
) -> dict[str, Any]:
    if job_name == JOB_PIPELINE_INITIAL:
        repo = MysqlPipelineRepository(session, daily_rows=settings.pipeline_daily_rows)
        return PipelineApplicationService(repo).execute(PipelineJob.INITIAL)
    if job_name == JOB_PIPELINE_COMPLETION:
        repo = MysqlPipelineRepository(session, daily_rows=settings.pipeline_daily_rows)
        return PipelineApplicationService(repo).execute(PipelineJob.COMPLETION)

    if postgres_engine is None:
        raise RuntimeError("PostgreSQL 연결이 없어 ETL 작업을 실행할 수 없습니다.")

    repo = EtlSyncRepository(session, postgres_engine)
    svc = EtlApplicationService(repo)
    if job_name == JOB_ETL_WEARABLE_SLOT:
        return svc.generate_wearable_slot()
    if job_name == JOB_ETL_POSTGRES_TO_MYSQL:
        return svc.sync_postgres_to_mysql()
    if job_name == JOB_ETL_MYSQL_TO_POSTGRES:
        return svc.sync_mysql_treatments_to_postgres()

    raise ValueError(f"알 수 없는 배치 작업명입니다: {job_name}")


def run_logged_batch_job(
    *,
    session: "Session",
    settings: Settings,
    job_name: str,
    trigger_type: str,
    postgres_engine: "Engine | None" = None,
    attempt_no: int = 1,
    retry_of_log_id: int | None = None,
    request_payload: dict[str, Any] | None = None,
    execute: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    max_attempts = max(1, int(settings.batch_retry_max_attempts))
    retry_delay = max(1, int(settings.batch_retry_delay_minutes))
    log_repo = BatchJobLogRepository(session)
    log_id = log_repo.create_running(
        job_name=job_name,
        trigger_type=trigger_type,
        attempt_no=max(1, int(attempt_no)),
        max_attempts=max_attempts,
        retry_of_log_id=retry_of_log_id,
        request_payload=request_payload,
    )
    session.commit()

    try:
        runner = execute or (
            lambda: _execute_batch_job(
                session=session,
                settings=settings,
                job_name=job_name,
                postgres_engine=postgres_engine,
            )
        )
        result = runner()
        result_with_log = {**result, "batch_log_id": log_id}
        log_repo.mark_success(log_id, result_with_log)
        session.commit()
        return result_with_log
    except Exception as exc:
        session.rollback()
        next_retry_at = None
        if attempt_no < max_attempts:
            next_retry_at = datetime.now().replace(microsecond=0) + timedelta(minutes=retry_delay)
        BatchJobLogRepository(session).mark_failed(log_id, exc, next_retry_at)
        session.commit()
        raise


def retry_due_batch_jobs(
    *,
    settings: Settings,
    session_factory: "sessionmaker[Session]",
    postgres_engine: "Engine | None",
    limit: int,
) -> dict[str, Any]:
    scan_session = session_factory()
    try:
        due = BatchJobLogRepository(scan_session).fetch_due_failures(limit)
    finally:
        scan_session.close()

    results: list[dict[str, Any]] = []
    for item in due:
        log_id = int(item["batch_log_id"])
        job_name = str(item["job_name"])
        attempt_no = int(item["attempt_no"]) + 1
        session = session_factory()
        try:
            BatchJobLogRepository(session).mark_retried(log_id)
            session.commit()
            result = run_logged_batch_job(
                session=session,
                settings=settings,
                job_name=job_name,
                trigger_type="retry",
                postgres_engine=postgres_engine,
                attempt_no=attempt_no,
                retry_of_log_id=log_id,
                request_payload={"retry_of_log_id": log_id, "previous_attempt": item["attempt_no"]},
            )
            results.append({"retry_of_log_id": log_id, "job_name": job_name, "ok": True, "result": result})
        except Exception as exc:
            logger.exception("배치 재처리 실패, 원본 로그=%s, 작업=%s", log_id, job_name)
            results.append(
                {
                    "retry_of_log_id": log_id,
                    "job_name": job_name,
                    "ok": False,
                    "error": str(exc),
                }
            )
        finally:
            session.close()

    return {"ok": True, "retried": len(results), "results": results}
