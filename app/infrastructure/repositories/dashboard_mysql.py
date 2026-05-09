import hashlib
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.datetime_display import format_datetime_kr, map_row_datetimes_to_kr
from app.domain.dashboard_schema import (
    DailyCount,
    DashboardSnapshot,
    GaugeBlock,
    KpiBlock,
    LeagueRow,
    PieSlice,
    ProductionBlock,
    TableDetailSnapshot,
    TableStatsRow,
    TableStatsSnapshot,
    TimelineBlock,
)

_TABLES = [
    "department",
    "kcd_code",
    "Patient",
    "check_in",
    "Reservation",
    "treatments",
    "Out_Treatments",
    "In_Treatments",
    "Emergency_Treatments",
    "doctor_treatment",
    "Prescription",
    "Prescription_Item",
    "diagnosis_certificate",
    "examination",
    "examination_schedule",
    "examination_result",
    "examination_journal",
    "blood_bank",
    "health_checkup_institution",
    "disability",
    "disability_care_institution",
    "inpatient_statistics",
    "treatment_department_statistics",
    "batch_job_log",
]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mask_name(value: str) -> str:
    v = value.strip()
    if not v:
        return value
    if len(v) == 1:
        return v + "*"
    return v[0] + ("*" * (len(v) - 1))


def _mask_rrn(value: str) -> str:
    v = value.strip()
    if not v:
        return value
    if len(v) >= 8:
        return v[:8] + "******"
    return v[0] + "******"


def _mask_email(value: str) -> str:
    v = value.strip()
    if "@" not in v:
        return _mask_name(v)
    local, domain = v.split("@", 1)
    if not local:
        return "***@" + domain
    return local[0] + "***@" + domain


def _mask_phone(value: str) -> str:
    v = value.strip()
    if len(v) <= 4:
        return "*" * len(v)
    return v[:3] + "****" + v[-4:]


def _mask_text(value: str) -> str:
    v = value.strip()
    if not v:
        return value
    if len(v) <= 2:
        return v[0] + "*"
    return v[:2] + "*" * (len(v) - 2)


def _sanitize_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key, raw in list(out.items()):
        key_l = str(key).lower()
        if key_l in {"patient_no", "patient_id", "doctor_id", "user_id", "treatment_doc"} and raw is not None:
            raw_s = str(raw)
            out[key] = "***" + raw_s[-2:] if len(raw_s) >= 2 else "***"
            out[f"{key}_sha256"] = _sha256_text(raw_s)
            continue
        if not isinstance(raw, str):
            continue
        if key_l in {"patient_rrn", "rrn", "resident_no"}:
            out[key] = _mask_rrn(raw)
            out[f"{key}_sha256"] = _sha256_text(raw)
            continue
        if key_l == "certificate_number":
            out[key] = _mask_text(raw)
            out[f"{key}_sha256"] = _sha256_text(raw)
            continue
        if "name" in key_l and key_l not in {"department_name", "institution_name", "drug_name", "job_name"}:
            out[key] = _mask_name(raw)
            out[f"{key}_sha256"] = _sha256_text(raw)
            continue
        if "email" in key_l:
            out[key] = _mask_email(raw)
            out[f"{key}_sha256"] = _sha256_text(raw)
            continue
        if key_l in {"patient_tel", "phone_number", "tel", "mobile"} or "phone" in key_l:
            out[key] = _mask_phone(raw)
            out[f"{key}_sha256"] = _sha256_text(raw)
            continue
        if "passport" in key_l:
            out[key] = "********"
            out[f"{key}_sha256"] = _sha256_text(raw)
            continue
        if key_l in {"patient_address", "address"}:
            out[key] = (raw[:2] + "***") if raw else raw
            out[f"{key}_sha256"] = _sha256_text(raw)
            continue
        if "birth" in key_l:
            out[key] = "****-**-**"
            continue
        if any(x in key_l for x in ("diagnosis", "finding", "purpose", "memo", "comment", "note")):
            out[key] = _mask_text(raw)
            out[f"{key}_sha256"] = _sha256_text(raw)
            continue
    return out


def _recent_months(n: int) -> list[tuple[str, str]]:
    keys: list[str] = []
    y, m = date.today().year, date.today().month
    for _ in range(n):
        keys.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    keys.reverse()
    labels: list[str] = []
    for k in keys:
        yy, mm = k.split("-")
        labels.append(f"{int(yy) % 100}년 {int(mm)}월")
    return list(zip(labels, keys))


class MysqlDashboardRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_snapshot(self) -> DashboardSnapshot:
        league = self._league_with_sparks(top_n=5)
        return DashboardSnapshot(
            gauge=self._gauge_block(),
            timeline=self._timeline_block(months_back=12),
            pie_sales=self._pie_by_treatment_type(),
            league_table=league,
            production=self._production_block(top_n=3),
            kpi=self._kpi_block(league_actual_sum=sum(r.actual for r in league)),
        )

    def fetch_table_stats(self) -> TableStatsSnapshot:
        out: list[TableStatsRow] = []
        for table_name in _TABLES:
            row = self._session.execute(
                text(
                    f"""
                    SELECT
                        COUNT(*) AS total_count,
                        COALESCE(SUM(CASE WHEN created_date >= CURDATE() THEN 1 ELSE 0 END), 0) AS today_count,
                        MAX(created_date) AS last_created_at
                    FROM `{table_name}`
                    """
                )
            ).one()
            out.append(
                TableStatsRow(
                    table_name=table_name,
                    total_count=int(row.total_count or 0),
                    today_count=int(row.today_count or 0),
                    last_created_at=(
                        format_datetime_kr(row.last_created_at)
                        if row.last_created_at is not None
                        else None
                    ),
                )
            )
        return TableStatsSnapshot(rows=out)

    def fetch_table_detail(self, table_name: str) -> TableDetailSnapshot:
        if table_name not in _TABLES:
            raise ValueError(f"unknown table: {table_name}")
        base = self._session.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS total_count,
                    COALESCE(SUM(CASE WHEN created_date >= CURDATE() THEN 1 ELSE 0 END), 0) AS today_count,
                    MAX(created_date) AS last_created_at
                FROM `{table_name}`
                """
            )
        ).one()
        trend_rows = self._session.execute(
            text(
                f"""
                SELECT DATE_FORMAT(created_date, '%Y-%m-%d') AS d, COUNT(*) AS c
                FROM `{table_name}`
                WHERE created_date >= DATE_SUB(CURDATE(), INTERVAL 13 DAY)
                GROUP BY d
                ORDER BY d
                """
            )
        ).all()
        cols = self._session.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                ORDER BY ORDINAL_POSITION
                """
            ),
            {"table_name": table_name},
        ).all()
        sample_rows = self._session.execute(
            text(f"SELECT * FROM `{table_name}` ORDER BY created_date DESC LIMIT 20")
        ).all()
        mapped_rows: list[dict] = []
        for r in sample_rows:
            mapped_rows.append(
                map_row_datetimes_to_kr(_sanitize_row(table_name, dict(r._mapping))),
            )
        return TableDetailSnapshot(
            table_name=table_name,
            total_count=int(base.total_count or 0),
            today_count=int(base.today_count or 0),
            last_created_at=(
                format_datetime_kr(base.last_created_at)
                if base.last_created_at is not None
                else None
            ),
            recent_daily=[DailyCount(day=str(r.d), count=int(r.c or 0)) for r in trend_rows],
            columns=[str(c.COLUMN_NAME) for c in cols],
            rows=mapped_rows,
        )

    def _gauge_block(self) -> GaugeBlock:
        row = self._session.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM treatments
                WHERE YEAR(treatment_date) = YEAR(CURRENT_DATE())
                """
            )
        ).one()
        current = int(row.cnt or 0)
        cap = max(30000, int(current * 1.15) + 5000)
        return GaugeBlock(current=current, max_value=cap, title="금년 진료 헤더 건수")

    def _timeline_block(self, months_back: int) -> TimelineBlock:
        pairs = _recent_months(months_back)
        keys_set = [p[1] for p in pairs]
        rows = self._session.execute(
            text(
                """
                SELECT DATE_FORMAT(treatment_date, '%Y-%m') AS ym, COUNT(*) AS c
                FROM treatments
                WHERE treatment_date >= DATE_SUB(
                    DATE_FORMAT(CURRENT_DATE(), '%Y-%m-01'), INTERVAL :mb MONTH
                )
                GROUP BY ym
                ORDER BY ym
                """
            ),
            {"mb": months_back - 1},
        ).all()
        by_ym = {str(r.ym): float(r.c) for r in rows}
        labels = [lbl for lbl, _ in pairs]
        values = [by_ym.get(k, 0.0) for k in keys_set]
        return TimelineBlock(labels=labels, values=values)

    def _pie_by_treatment_type(self) -> list[PieSlice]:
        rows = self._session.execute(
            text(
                """
                SELECT COALESCE(NULLIF(TRIM(treatment_type), ''), '미분류') AS t, COUNT(*) AS c
                FROM treatments
                GROUP BY t
                ORDER BY c DESC
                """
            )
        ).all()
        if not rows:
            return []
        mapping = {"OUTPATIENT": "외래", "INPATIENT": "입원", "EMERGENCY": "응급"}
        out: list[PieSlice] = []
        for r in rows:
            t_raw = str(r[0] if len(r) > 0 else "미분류")
            c_raw = float(r[1] if len(r) > 1 else 0.0)
            out.append(PieSlice(name=mapping.get(t_raw, t_raw), value=c_raw))
        return out

    def _production_block(self, top_n: int) -> ProductionBlock:
        rows = self._session.execute(
            text(
                """
                SELECT d.department_name AS n, COUNT(t.treatment_id) AS c
                FROM department d
                INNER JOIN treatments t ON t.department_id = d.id
                GROUP BY d.id, d.department_name
                ORDER BY c DESC
                LIMIT :lim
                """
            ),
            {"lim": top_n},
        ).all()
        if not rows:
            return ProductionBlock(categories=["데이터 없음"], values=[0.0])
        return ProductionBlock(
            categories=[str(r.n)[:24] for r in rows],
            values=[float(r.c) for r in rows],
        )

    def _league_with_sparks(self, top_n: int) -> list[LeagueRow]:
        pairs = _recent_months(6)
        ym_order = [k for _, k in pairs]

        dept_rows = self._session.execute(
            text(
                """
                SELECT d.id AS did, d.department_name AS n, COUNT(t.treatment_id) AS c
                FROM department d
                INNER JOIN treatments t ON t.department_id = d.id
                GROUP BY d.id, d.department_name
                ORDER BY c DESC
                LIMIT :lim
                """
            ),
            {"lim": top_n},
        ).all()

        if not dept_rows:
            return []

        ids = [int(r.did) for r in dept_rows]
        in_clause = ",".join(str(i) for i in ids)
        spark_rows = self._session.execute(
            text(
                f"""
                SELECT department_id AS did,
                       DATE_FORMAT(treatment_date, '%Y-%m') AS ym,
                       COUNT(*) AS c
                FROM treatments
                WHERE treatment_date >= DATE_SUB(
                    DATE_FORMAT(CURRENT_DATE(), '%Y-%m-01'), INTERVAL 5 MONTH
                )
                  AND department_id IN ({in_clause})
                GROUP BY department_id, ym
                """
            )
        ).all()

        by_dept_ym: dict[int, dict[str, float]] = {}
        for r in spark_rows:
            did = int(r.did)
            by_dept_ym.setdefault(did, {})[str(r.ym)] = float(r.c)

        out: list[LeagueRow] = []
        for r in dept_rows:
            did = int(r.did)
            cnt = int(r.c)
            actual = float(cnt * 150_000)
            target = actual * 1.08 if actual > 0 else 250_000.0
            series = [by_dept_ym.get(did, {}).get(ym, 0.0) for ym in ym_order]
            if sum(series) == 0:
                series = [max(1.0, cnt / 6.0)] * 6
            out.append(LeagueRow(name=str(r.n)[:32], actual=actual, target=target, spark=series))
        return out

    def _kpi_block(self, league_actual_sum: float) -> KpiBlock:
        rev = float(
            self._session.execute(
                text(
                    """
                    SELECT COALESCE(
                        (
                            SELECT SUM(e.examination_price)
                            FROM examination_schedule es
                            INNER JOIN examination e ON es.examination_id = e.examination_id
                        ),
                        0
                    ) AS rev
                    """
                )
            ).scalar_one()
        )
        if rev <= 0:
            rev = 0.0
        target = rev * 1.025 if rev > 0 else 0.0

        pair = self._session.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM treatments
                     WHERE treatment_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)) AS r30,
                    (SELECT COUNT(*) FROM treatments
                     WHERE treatment_date < DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
                       AND treatment_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY)) AS p30
                """
            )
        ).one()
        r30, p30 = int(pair.r30 or 0), int(pair.p30 or 0)
        if p30 <= 0:
            growth = 4.0 if r30 > 0 else 0.0
        else:
            growth = round((r30 - p30) / p30 * 100.0, 1)

        return KpiBlock(
            actual=rev,
            target=round(target, 2),
            growth_pct=growth,
            label="검사 일정과 검사 단가로 잡은 추정 매출",
        )
