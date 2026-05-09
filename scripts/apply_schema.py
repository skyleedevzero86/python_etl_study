from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

import sqlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MYSQL_SCHEMA = PROJECT_ROOT / "scripts" / "디비정리.sql"
DEFAULT_POSTGRES_SCHEMA = PROJECT_ROOT / "scripts" / "디비정리PostgreSql.sql"


def _statements(sql_path: Path) -> list[str]:
    sql = sql_path.read_text(encoding="utf-8")
    return [stmt.strip() for stmt in sqlparse.split(sql) if stmt.strip()]


def _password(arg_value: str | None) -> str:
    if arg_value is not None:
        return arg_value
    return getpass("DB password: ")


def apply_mysql(args: argparse.Namespace) -> None:
    import pymysql

    schema_path = Path(args.schema_file or DEFAULT_MYSQL_SCHEMA)
    password = _password(args.password)
    conn = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            if args.create_database:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{args.database}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            cur.execute(f"USE `{args.database}`")
            for stmt in _statements(schema_path):
                cur.execute(stmt)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"MySQL schema applied: {schema_path} -> {args.host}:{args.port}/{args.database}")


def apply_postgres(args: argparse.Namespace) -> None:
    import psycopg2

    schema_path = Path(args.schema_file or DEFAULT_POSTGRES_SCHEMA)
    password = _password(args.password)
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        dbname=args.database,
    )
    try:
        with conn.cursor() as cur:
            for stmt in _statements(schema_path):
                cur.execute(stmt)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"PostgreSQL schema applied: {schema_path} -> {args.host}:{args.port}/{args.database}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MySQL/PostgreSQL 스키마 SQL 적용 도구")
    parser.add_argument("--dialect", choices=["mysql", "postgres"], default="mysql")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", default=None)
    parser.add_argument("--database", required=True)
    parser.add_argument("--schema-file", default=None)
    parser.add_argument(
        "--create-database",
        action="store_true",
        help="MySQL 실행 시 대상 데이터베이스가 없으면 생성합니다.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.port is None:
        args.port = 3306 if args.dialect == "mysql" else 5432
    if args.dialect == "mysql":
        apply_mysql(args)
    else:
        apply_postgres(args)


if __name__ == "__main__":
    main()
