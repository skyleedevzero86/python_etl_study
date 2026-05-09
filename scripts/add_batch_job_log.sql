/* =====================================================================
 기존 MySQL 스키마에 배치/ETL 실행 로그 테이블만 추가하는 패치
 ===================================================================== */

CREATE TABLE IF NOT EXISTS batch_job_log (
    batch_log_id       BIGINT       NOT NULL AUTO_INCREMENT COMMENT '배치 실행 로그 PK',
    job_name           VARCHAR(80)  NOT NULL                COMMENT '실행 작업명 예: etl.postgres_to_mysql',
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
