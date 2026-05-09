from contextlib import asynccontextmanager
from pathlib import Path

from app.infrastructure.logging_config import (
    configure_root_logging,
    log_dir,
    setup_uncaught_exception_logfile,
)

_CRASH_LOG = setup_uncaught_exception_logfile()
_APP_LOG = configure_root_logging()

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from app.infrastructure.config import Settings
from app.infrastructure.database import (
    create_engine_from_settings,
    create_postgres_engine_from_settings,
    create_session_factory,
)
from app.infrastructure.repositories.batch_job_log import ensure_batch_job_log_table
from app.infrastructure.scheduler import start_background_scheduler
from app.presentation.routers import dashboard, health, pg_my_health, pipeline

logger = logging.getLogger(__name__)

logger.info(
    "로그 디렉터리: %s | 앱 로그: %s | 마지막 크래시 덤프: %s",
    log_dir(),
    _APP_LOG,
    _CRASH_LOG,
)

_sched = None


def _fail_fast_if_db_secret_missing(settings: Settings) -> None:
    if (
        settings.database_user
        and settings.database_user.lower() not in {"root"}
        and settings.database_password == ""
    ):
        msg = (
            "DB 접속 정보가 비어 있습니다. "
            f"계정={settings.database_user} 호스트={settings.database_host} DB={settings.database_name} "
            f"| .env={settings.resolved_dotenv_files or '없음'} "
            "| DATABASE_PASSWORD 를 .env 에 설정하세요."
        )
        logger.error(msg)
        raise RuntimeError(msg) from None


def _mysql_errno_from_operational_error(exc: OperationalError) -> int | None:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    args = getattr(orig, "args", ())
    if not args:
        return None
    code = args[0]
    return code if isinstance(code, int) else None


def _verify_mysql_or_raise(engine, settings: Settings) -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as e:
        logger.error(
            "디비 접속 실패(MySQL). 디비에 문제가 있습니다. 계정=%s 호스트=%s 데이터베이스=%s",
            settings.database_user,
            settings.database_host,
            settings.database_name,
        )
        errno = _mysql_errno_from_operational_error(e)
        if errno == 1045:
            detail = str(getattr(e, "orig", e))
            using_password_no = "USING PASSWORD: NO" in detail.upper()
            hint = (
                "디비 접속 실패(MySQL). 디비에 문제가 있습니다. MySQL 1045 인증 실패. 사용자/비밀번호 또는 host 권한을 확인하세요. "
                f"계정={settings.database_user} 호스트={settings.database_host} DB={settings.database_name} "
                f"| .env={settings.resolved_dotenv_files or '없음'}"
            )
            if using_password_no:
                hint += (
                    " | 현재 비밀번호가 비어 있습니다. .env 의 DATABASE_PASSWORD 를 설정하세요."
                )
            logger.error(hint)
            raise RuntimeError(hint) from None
        logger.exception(
            "디비 접속 실패(MySQL). 디비에 문제가 있습니다. 계정=%s 호스트=%s DB=%s | .env=%s",
            settings.database_user,
            settings.database_host,
            settings.database_name,
            settings.resolved_dotenv_files or "없음",
        )
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sched
    settings = Settings()
    if settings.resolved_dotenv_files:
        logger.info("로드된 .env 경로: %s", settings.resolved_dotenv_files)
    else:
        logger.warning(
            ".env 없음—기대: %s",
            settings.project_root / ".env",
        )

    _fail_fast_if_db_secret_missing(settings)
    engine = create_engine_from_settings(settings)
    _verify_mysql_or_raise(engine, settings)
    logger.info("MySQL 연결 확인 완료")
    ensure_batch_job_log_table(engine)
    logger.info("배치 실행 로그 테이블 확인 완료")

    postgres_engine = None
    try:
        postgres_engine = create_postgres_engine_from_settings(settings)
        with postgres_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL 연결 확인 완료")
    except Exception as exc:
        pg_db = settings.postgres_database or settings.database_name
        logger.error(
            "디비 접속 실패(PostgreSQL). 호스트=%s 포트=%s 데이터베이스=%s 사용자=%s — "
            "서버 기동 여부, 방화벽, 해당 DB 생성(CREATE DATABASE), 스키마 적용(디비정리PostgreSql.sql), "
            "포트(도커 기본 5432 vs 설정 POSTGRES_PORT)를 확인하세요. 원인=%s",
            settings.database_host,
            settings.postgres_port,
            pg_db,
            settings.postgres_user,
            exc,
        )
        if postgres_engine is not None:
            postgres_engine.dispose()
            postgres_engine = None

    session_factory = create_session_factory(engine)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.postgres_engine = postgres_engine
    _sched = start_background_scheduler(settings, session_factory, postgres_engine)
    try:
        yield
    finally:
        if _sched is not None:
            _sched.shutdown(wait=False)
        engine.dispose()
        pe = getattr(app.state, "postgres_engine", None)
        if pe is not None:
            pe.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="파이프라인·통계 MVP",
        version="0.1.0",
        summary="배치 적재와 대시보드 통계 조회 API",
        description=(
            "MySQL 기반의 배치 데이터 적재와 통계 조회를 제공하는 API입니다.\n\n"
            "- 대시보드 HTML과 JSON 통계 제공\n"
            "- 테이블별 통계/상세 조회 제공\n"
            "- 수동 파이프라인 실행 제공\n"
            "- `/pipeline/run/{job}`은 `POST`만 허용되며, "
            "`ENABLE_PIPELINE_WRITE=true`일 때만 실행됩니다."
        ),
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def _log_request_failures(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("HTTP 요청 처리 중 예외 %s %s", request.method, request.url.path)
            raise

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(dashboard.router)
    app.include_router(health.router)
    app.include_router(pg_my_health.router)
    app.include_router(pipeline.router)
    return app


app = create_app()
