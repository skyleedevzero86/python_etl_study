import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.domain.enums import PipelineJob
from app.infrastructure.batch_jobs import (
    pipeline_job_name,
    retry_due_batch_jobs,
    run_logged_batch_job,
)
from app.infrastructure.config import Settings
from app.infrastructure.etl_scheduler import register_etl_jobs

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)


def _run_job(factory: "sessionmaker[Session]", settings: Settings, job: PipelineJob) -> None:
    session = factory()
    try:
        result = run_logged_batch_job(
            session=session,
            settings=settings,
            job_name=pipeline_job_name(job),
            trigger_type="scheduler",
            request_payload={"pipeline_daily_rows": settings.pipeline_daily_rows},
        )
        logger.info("파이프라인 작업 정상 종료, 유형=%s, 결과=%s", job.value, result)
    except Exception:
        logger.exception("파이프라인 작업 실패, 유형=%s", job.value)
        raise
    finally:
        session.close()


def _retry_jobs(
    settings: Settings,
    factory: "sessionmaker[Session]",
    postgres_engine: "Engine | None",
) -> None:
    result = retry_due_batch_jobs(
        settings=settings,
        session_factory=factory,
        postgres_engine=postgres_engine,
        limit=settings.batch_retry_limit,
    )
    if result["retried"]:
        logger.info("배치 실패 재처리 완료: %s", result)


def start_background_scheduler(
    settings: Settings,
    session_factory: "sessionmaker[Session]",
    postgres_engine: "Engine | None" = None,
) -> BackgroundScheduler | None:

    pipeline_on = settings.enable_pipeline_scheduler
    etl_on = settings.enable_etl_scheduler and postgres_engine is not None

    retry_on = settings.enable_batch_retry

    if not pipeline_on and not etl_on and not retry_on:
        logger.info("파이프라인·ETL·재처리 스케줄러 모두 비활성화되어 시작하지 않습니다.")
        return None

    if settings.enable_etl_scheduler and postgres_engine is None:
        logger.warning(
            "ETL 스케줄러가 켜져 있으나 PostgreSQL 엔진이 없습니다. ETL 작업은 등록되지 않습니다."
        )

    sched = BackgroundScheduler(timezone="Asia/Seoul")

    if pipeline_on:
        wd = settings.scheduler_weekday.lower()
        sched.add_job(
            _run_job,
            CronTrigger(day_of_week=wd, hour=settings.scheduler_initial_hour, minute=0),
            args=(session_factory, settings, PipelineJob.INITIAL),
            id="pipeline_initial_weekly",
            replace_existing=True,
        )
        sched.add_job(
            _run_job,
            CronTrigger(day_of_week=wd, hour=settings.scheduler_completion_hour, minute=0),
            args=(session_factory, settings, PipelineJob.COMPLETION),
            id="pipeline_completion_weekly",
            replace_existing=True,
        )
        logger.info(
            "파이프라인 작업 등록, 요일토큰=%s, 초기 시각=%02d시, 완료 계열 시각=%02d시",
            wd,
            settings.scheduler_initial_hour,
            settings.scheduler_completion_hour,
        )

    if etl_on:
        register_etl_jobs(sched, settings, session_factory, postgres_engine)

    if retry_on:
        interval = max(1, int(settings.batch_retry_interval_minutes))
        sched.add_job(
            _retry_jobs,
            IntervalTrigger(minutes=interval, timezone="Asia/Seoul"),
            args=(settings, session_factory, postgres_engine),
            id="batch_retry_due_failures",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("배치 실패 재처리 작업 등록, 주기=%d분", interval)

    sched.start()
    logger.info("백그라운드 스케줄러 기동")
    return sched


def start_weekly_pipeline_scheduler(
    settings: Settings,
    session_factory: "sessionmaker[Session]",
) -> BackgroundScheduler | None:

    return start_background_scheduler(settings, session_factory, postgres_engine=None)
