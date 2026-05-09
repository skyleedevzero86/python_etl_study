import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.infrastructure.batch_jobs import (
    JOB_ETL_MYSQL_TO_POSTGRES,
    JOB_ETL_POSTGRES_TO_MYSQL,
    JOB_ETL_WEARABLE_SLOT,
    run_logged_batch_job,
)
from app.infrastructure.config import Settings

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)


def register_etl_jobs(
    sched: BackgroundScheduler,
    settings: Settings,
    session_factory: "sessionmaker[Session]",
    postgres_engine: "Engine",
) -> None:

    def _wearable_slot() -> None:
        session = session_factory()
        try:
            result = run_logged_batch_job(
                session=session,
                settings=settings,
                job_name=JOB_ETL_WEARABLE_SLOT,
                trigger_type="scheduler",
                postgres_engine=postgres_engine,
            )
            logger.info("ETL 웨어러블 슬롯 완료: %s", result)
        except Exception:
            logger.exception("ETL 웨어러블 슬롯 실패")
            raise
        finally:
            session.close()

    def _pg_to_mysql() -> None:
        session = session_factory()
        try:
            result = run_logged_batch_job(
                session=session,
                settings=settings,
                job_name=JOB_ETL_POSTGRES_TO_MYSQL,
                trigger_type="scheduler",
                postgres_engine=postgres_engine,
            )
            logger.info("ETL PostgreSQL→MySQL 완료: %s", result)
        except Exception:
            logger.exception("ETL PostgreSQL→MySQL 실패")
            raise
        finally:
            session.close()

    def _mysql_to_pg() -> None:
        session = session_factory()
        try:
            result = run_logged_batch_job(
                session=session,
                settings=settings,
                job_name=JOB_ETL_MYSQL_TO_POSTGRES,
                trigger_type="scheduler",
                postgres_engine=postgres_engine,
            )
            logger.info("ETL MySQL→PostgreSQL 완료: %s", result)
        except Exception:
            logger.exception("ETL MySQL→PostgreSQL 실패")
            raise
        finally:
            session.close()

    h0 = settings.etl_wearable_start_hour
    h1 = settings.etl_wearable_end_hour
    hour_range = f"{h0}-{h1}"

    sched.add_job(
        _wearable_slot,
        CronTrigger(minute="*/5", hour=hour_range, timezone="Asia/Seoul"),
        id="etl_wearable_round_robin",
        replace_existing=True,
    )
    sched.add_job(
        _pg_to_mysql,
        CronTrigger(
            hour=settings.etl_postgres_to_mysql_hour,
            minute=0,
            timezone="Asia/Seoul",
        ),
        id="etl_postgres_to_mysql_daily",
        replace_existing=True,
    )
    sched.add_job(
        _mysql_to_pg,
        CronTrigger(
            hour=settings.etl_mysql_to_postgres_hour,
            minute=0,
            timezone="Asia/Seoul",
        ),
        id="etl_mysql_to_postgres_daily",
        replace_existing=True,
    )
    logger.info(
        "ETL 작업 등록: 웨어러블 %s시~%s시 5분마다, PG→MySQL %02d:00, MySQL→PG %02d:00",
        h0,
        h1,
        settings.etl_postgres_to_mysql_hour,
        settings.etl_mysql_to_postgres_hour,
    )
