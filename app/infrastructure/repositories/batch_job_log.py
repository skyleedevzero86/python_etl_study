from __future__ import annotations

import json
import traceback
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


BATCH_JOB_LOG_DDL = """
CREATE TABLE IF NOT EXISTS batch_job_log (
    batch_log_id       BIGINT       NOT NULL AUTO_INCREMENT COMMENT '배치 실행 로그 PK',
    job_name           VARCHAR(80)  NOT NULL                COMMENT '실행 작업명',
    trigger_type       VARCHAR(30)  NOT NULL                COMMENT 'scheduler/manual/retry',
    status             VARCHAR(20)  NOT NULL                COMMENT 'RUNNING/SUCCESS/FAILED/RETRIED',
    attempt_no         INT          NOT NULL DEFAULT 1      COMMENT '시도 번호',
    max_attempts       INT          NOT NULL DEFAULT 3      COMMENT '최대 시도 횟수',
    retry_of_log_id    BIGINT       NULL                    COMMENT '재처리 원본 로그 ID',
    started_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '시작 시각',
    finished_at        DATETIME     NULL                    COMMENT '종료 시각',
    next_retry_at      DATETIME     NULL                    COMMENT '다음 재처리 예정 시각',
    request_payload    JSON         NULL                    COMMENT '실행 입력/옵션',
    result_payload     JSON         NULL                    COMMENT '성공 결과',
    error_message      TEXT         NULL                    COMMENT '실패 메시지',
    created_date       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    last_modified_date DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',
    intt_cd            VARCHAR(30)  NOT NULL DEFAULT 'BATCH' COMMENT '기관/시스템 코드',
    PRIMARY KEY (batch_log_id),
    KEY idx_batch_job_status_retry (status, next_retry_at),
    KEY idx_batch_job_name_started (job_name, started_at),
    KEY idx_batch_job_retry_of (retry_of_log_id),
    CONSTRAINT fk_batch_job_retry_of
        FOREIGN KEY (retry_of_log_id) REFERENCES batch_job_log(batch_log_id)
) COMMENT='배치·ETL 실행 이력 및 실패 재처리 큐';
"""


def ensure_batch_job_log_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(BATCH_JOB_LOG_DDL))


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _error_text(exc: BaseException) -> str:
    return "".join(traceback.format_exception_only(type(exc), exc)).strip()[:4000]


class BatchJobLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_running(
        self,
        *,
        job_name: str,
        trigger_type: str,
        attempt_no: int,
        max_attempts: int,
        retry_of_log_id: int | None = None,
        request_payload: dict[str, Any] | None = None,
    ) -> int:
        self._session.execute(
            text(
                """
                INSERT INTO batch_job_log (
                    job_name, trigger_type, status, attempt_no, max_attempts,
                    retry_of_log_id, started_at, request_payload
                ) VALUES (
                    :job_name, :trigger_type, 'RUNNING', :attempt_no, :max_attempts,
                    :retry_of_log_id, CURRENT_TIMESTAMP, :request_payload
                )
                """
            ),
            {
                "job_name": job_name,
                "trigger_type": trigger_type,
                "attempt_no": attempt_no,
                "max_attempts": max_attempts,
                "retry_of_log_id": retry_of_log_id,
                "request_payload": _json_or_none(request_payload),
            },
        )
        return int(self._session.execute(text("SELECT LAST_INSERT_ID()")).scalar_one())

    def mark_success(self, log_id: int, result_payload: dict[str, Any]) -> None:
        self._session.execute(
            text(
                """
                UPDATE batch_job_log
                SET status = 'SUCCESS',
                    finished_at = CURRENT_TIMESTAMP,
                    next_retry_at = NULL,
                    result_payload = :result_payload,
                    error_message = NULL
                WHERE batch_log_id = :log_id
                """
            ),
            {
                "log_id": log_id,
                "result_payload": _json_or_none(result_payload),
            },
        )

    def mark_failed(
        self,
        log_id: int,
        exc: BaseException,
        next_retry_at: datetime | None,
    ) -> None:
        self._session.execute(
            text(
                """
                UPDATE batch_job_log
                SET status = 'FAILED',
                    finished_at = CURRENT_TIMESTAMP,
                    next_retry_at = :next_retry_at,
                    error_message = :error_message
                WHERE batch_log_id = :log_id
                """
            ),
            {
                "log_id": log_id,
                "next_retry_at": next_retry_at,
                "error_message": _error_text(exc),
            },
        )

    def mark_retried(self, log_id: int) -> None:
        self._session.execute(
            text(
                """
                UPDATE batch_job_log
                SET status = 'RETRIED',
                    next_retry_at = NULL,
                    last_modified_date = CURRENT_TIMESTAMP
                WHERE batch_log_id = :log_id
                """
            ),
            {"log_id": log_id},
        )

    def fetch_due_failures(self, limit: int) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text(
                """
                SELECT batch_log_id, job_name, attempt_no, max_attempts
                FROM batch_job_log
                WHERE status = 'FAILED'
                  AND next_retry_at IS NOT NULL
                  AND next_retry_at <= CURRENT_TIMESTAMP
                  AND attempt_no < max_attempts
                ORDER BY next_retry_at ASC, batch_log_id ASC
                LIMIT :limit_rows
                """
            ),
            {"limit_rows": max(1, int(limit))},
        ).mappings()
        return [dict(row) for row in rows]

    def fetch_recent(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit_rows": max(1, min(int(limit), 200))}
        where = ""
        if status:
            where = "WHERE status = :status"
            params["status"] = status.upper()
        rows = self._session.execute(
            text(
                f"""
                SELECT batch_log_id, job_name, trigger_type, status, attempt_no,
                       max_attempts, retry_of_log_id, started_at, finished_at,
                       next_retry_at, error_message, created_date, last_modified_date
                FROM batch_job_log
                {where}
                ORDER BY batch_log_id DESC
                LIMIT :limit_rows
                """
            ),
            params,
        ).mappings()
        return [dict(row) for row in rows]
