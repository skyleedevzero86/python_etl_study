from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.domain.datetime_display import cell_value_display
from app.application.dashboard_service import DashboardApplicationService
from app.domain.display_labels import CLINICAL_CATEGORY_CODE_KR, STATUS_CODE_KR
from app.domain.dashboard_schema import (
    DashboardSnapshot,
    PgDashboardSnapshot,
    TableDetailSnapshot,
    TableStatsSnapshot,
)
from app.infrastructure.batch_jobs import (
    JOB_ETL_POSTGRES_TO_MYSQL,
    retry_due_batch_jobs,
    run_logged_batch_job,
)
from app.infrastructure.repositories.dashboard_mysql import _sanitize_row
from app.infrastructure.repositories.dashboard_postgres import PostgresDashboardRepository
from app.infrastructure.repositories.batch_job_log import BatchJobLogRepository
from app.presentation.dependencies import get_dashboard_service, get_db

router = APIRouter(tags=["대시보드"])

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES))
_TABLE_NAME_KR = {
    "department": "진료과",
    "kcd_code": "질병분류 코드",
    "Patient": "환자",
    "check_in": "접수",
    "Reservation": "예약",
    "treatments": "진료",
    "Out_Treatments": "외래 진료",
    "In_Treatments": "입원 진료",
    "Emergency_Treatments": "응급 진료",
    "doctor_treatment": "의사 진료 세션",
    "Prescription": "처방",
    "Prescription_Item": "처방 항목",
    "diagnosis_certificate": "진단서",
    "examination": "검사 마스터",
    "examination_schedule": "검사 일정",
    "examination_result": "검사 결과",
    "examination_journal": "검사 일지",
    "blood_bank": "혈액은행",
    "health_checkup_institution": "건강검진 기관",
    "disability": "장애 정보",
    "disability_care_institution": "장애인 돌봄 기관",
    "inpatient_statistics": "입원 통계",
    "treatment_department_statistics": "진료과 통계",
    "batch_job_log": "배치 실행 로그",
}
_COLUMN_NAME_KR = {
    "id": "아이디",
    "created_date": "생성일시",
    "last_modified_date": "수정일시",
    "intt_cd": "기관",
    "department_code": "진료과 코드",
    "department_name": "진료과명",
    "department_eng_name": "진료과 영문명",
    "department_type": "진료과 유형",
    "examination_id": "검사 아이디",
    "equipment_id": "장비 아이디",
    "examination_name": "검사명",
    "examination_type": "검사 유형",
    "examination_constraints": "검사 제약",
    "examination_location": "검사 위치",
    "examination_price": "검사 금액",
    "patient_no": "환자번호",
    "patient_name": "환자명",
    "patient_rrn": "주민등록번호",
    "patient_gender": "성별",
    "patient_birth": "생년월일",
    "patient_address": "주소",
    "patient_email": "이메일",
    "patient_tel": "전화번호",
    "checkIn_id": "접수 아이디",
    "checkIn_date": "접수일시",
    "checkIn_status": "접수 상태",
    "reservation_id": "예약 아이디",
    "reservation_datetime": "예약일시",
    "reservation_status": "예약 상태",
    "treatment_id": "진료 아이디",
    "treatment_doc": "진료의",
    "treatment_type": "진료 유형",
    "treatment_status": "진료 상태",
    "treatment_date": "진료일시",
    "prescription_id": "처방 아이디",
    "prescription_status": "처방 상태",
    "certificate_id": "진단서 아이디",
    "certificate_number": "진단서 번호",
    "diagnosis_name": "진단명",
    "diagnosis_date": "진단일",
    "clinical_findings": "임상 소견",
    "purpose": "발급 목적",
    "issued_at": "발급일시",
    "status": "상태",
    "kcd_code_id": "질병분류 코드 아이디",
    "doctor_id": "의사 아이디",
    "patient_id": "환자 아이디",
    "certificate_number": "진단서 번호",
    "reservation_YN": "예약 여부",
    "reservation_change_datetime": "예약 변경일시",
    "reservation_change_cause": "예약 변경사유",
    "treatment_start_time": "진료 시작시각",
    "treatment_end_time": "진료 종료시각",
    "treatment_comment": "진료 메모",
    "treatment_dept": "진료과명 스냅샷",
    "prescription_doc": "처방의",
    "prescription_date": "처방일시",
    "prescription_type": "처방 유형",
    "prescription_memo": "처방 메모",
    "prescription_item_id": "처방 항목 아이디",
    "drug_code": "약품 코드",
    "drug_name": "약품명",
    "dosage": "용법",
    "dose": "용량",
    "frequency": "복용 횟수",
    "days": "복용 일수",
    "total_quantity": "총 수량",
    "unit": "단위",
    "special_note": "특이사항",
    "examination_schedule_id": "검사 일정 아이디",
    "examination_date": "검사일",
    "examination_result_id": "검사 결과 아이디",
    "examination_result": "검사 결과",
    "examination_normal": "정상 여부",
    "examination_notes": "검사 비고",
    "examination_journal_id": "검사 일지 아이디",
    "examination_time": "검사 시각",
    "examination_equipment_usage": "장비 사용 여부",
    "blood_bank_id": "혈액은행 아이디",
    "blood_type": "혈액형",
    "institution_id": "기관 아이디",
    "institution_name": "기관명",
    "institution_type": "기관 유형",
    "region_code": "지역 코드",
    "region_name": "지역명",
    "address": "주소",
    "sido": "시도",
    "sigungu": "시군구",
    "latitude": "위도",
    "longitude": "경도",
    "phone_number": "전화번호",
    "is_active": "활성 여부",
    "data_source": "데이터 출처",
    "data_date": "데이터 기준일",
    "disability_id": "장애 아이디",
    "disability_grade": "장애 등급",
    "disability_type": "장애 유형",
    "assistive_device_YN": "보조기구 필요여부",
    "disability_device_type": "보조기구 종류",
    "service_type": "서비스 유형",
    "statistics_id": "통계 아이디",
    "statistics_year": "통계 연도",
    "visit_days": "내원 일수",
    "benefit_days": "급여 일수",
    "medical_fee": "진료비",
    "benefit_fee": "급여비",
    "patient_count": "환자 수",
    "treatment_count": "진료 건수",
    "user_id": "사용자 아이디",
    "doctorTreatment_id": "의사 진료 아이디",
    "doctorTreatment_starttime": "의사 진료 시작시각",
    "doctorTreatment_endtime": "의사 진료 종료시각",
    "pre_treatment_id": "이전 진료 아이디",
    "guardian": "보호자",
    "batch_log_id": "배치 로그 ID",
    "job_name": "작업명",
    "trigger_type": "실행 유형",
    "attempt_no": "시도 번호",
    "max_attempts": "최대 시도",
    "retry_of_log_id": "재처리 원본 로그",
    "started_at": "시작 시각",
    "finished_at": "종료 시각",
    "next_retry_at": "다음 재처리 시각",
    "request_payload": "요청 내용",
    "result_payload": "결과 내용",
    "error_message": "오류 메시지",
}
_VALUE_KR = {
    **STATUS_CODE_KR,
    **CLINICAL_CATEGORY_CODE_KR,
    "M": "남",
    "F": "여",
    "Y": "예",
    "N": "아니오",
    "1": "예",
    "0": "아니오",
    "RUNNING": "실행중",
    "RETRIED": "재처리됨",
    "scheduler": "스케줄러",
    "manual": "수동",
    "retry": "재처리",
}


def _column_label_kr(col: str) -> str:
    if col in _COLUMN_NAME_KR:
        return _COLUMN_NAME_KR[col]
    c = col.strip()
    if not c:
        return "항목"
    low = c.lower()
    if low.endswith("_id") or low == "id":
        return "식별자"
    if low.endswith("_no"):
        return "번호"
    if low.endswith("_yn"):
        return "여부"
    if low.endswith("_cd") or "code" in low:
        return "코드"
    if "status" in low:
        return "상태"
    if "date" in low or "time" in low:
        return "일시"
    if "name" in low:
        return "명칭"
    if "type" in low:
        return "유형"
    if "count" in low:
        return "건수"
    if "comment" in low or "memo" in low or "note" in low:
        return "메모"
    return "항목"


@router.get("/", include_in_schema=False)
def dashboard_root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
    summary="대시보드 화면",
    description="대시보드 HTML 페이지를 반환합니다. 실제 수치 데이터는 `/api/dashboard/stats`에서 가져옵니다.",
)
def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={},
    )


@router.get(
    "/dashboard/postgresql",
    response_class=HTMLResponse,
    summary="PostgreSQL 데이터 대시보드",
    description="PostgreSQL 테이블 건수·ETL·생체·진료 이벤트를 상세 표와 차트로 표시합니다.",
)
def dashboard_postgresql_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard_postgresql.html",
        context={},
    )


@router.get(
    "/api/dashboard/postgresql-stats",
    response_model=PgDashboardSnapshot,
    summary="PostgreSQL 집계 JSON",
    description="디비정리PostgreSql 스키마 기준 테이블 건수·요약·최근 행을 반환합니다.",
)
def dashboard_postgresql_stats_json(request: Request) -> PgDashboardSnapshot:
    eng = getattr(request.app.state, "postgres_engine", None)
    return PostgresDashboardRepository(eng).fetch_snapshot()


def _serialize_masked_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if str(k).endswith("_sha256"):
            continue
        out[k] = cell_value_display(v)
    return out


@router.get(
    "/api/dashboard/pg-patient/{patient_no}",
    summary="PostgreSQL 환자 요약(대시보드)",
)
def dashboard_pg_patient_detail(
    request: Request,
    patient_no: Annotated[int, ApiPath(description="환자번호", ge=1)],
) -> dict[str, Any]:
    eng = getattr(request.app.state, "postgres_engine", None)
    if eng is None:
        raise HTTPException(status_code=503, detail="PostgreSQL 연결이 없습니다.")
    with eng.connect() as conn:
        prow = conn.execute(
            text(
                'SELECT patient_no, patient_name, patient_rrn, patient_gender, patient_birth, '
                'patient_address, patient_email, patient_tel, patient_foreign, patient_passport, '
                'patient_hypass_YN, patient_last_visit, guardian, created_date, last_modified_date, intt_cd '
                'FROM "Patient" WHERE patient_no = :p'
            ),
            {"p": patient_no},
        ).mappings().first()
        if not prow:
            raise HTTPException(status_code=404, detail="환자를 찾을 수 없습니다.")
        patient = _serialize_masked_row(_sanitize_row("Patient", dict(prow)))
        prof_row = conn.execute(
            text(
                "SELECT patient_no, app_user_id, blood_type, height_cm, weight_kg, "
                "created_date, last_modified_date, intt_cd FROM user_app_profile WHERE patient_no = :p"
            ),
            {"p": patient_no},
        ).mappings().first()
        profile = (
            _serialize_masked_row(_sanitize_row("user_app_profile", dict(prof_row)))
            if prof_row
            else None
        )
    return {"patient": patient, "profile": profile}


@router.post(
    "/api/dashboard/etl/sync-postgres-to-mysql",
    summary="PostgreSQL → MySQL 동기화 수동 실행",
)
def dashboard_etl_sync_pg_to_mysql(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    pg = getattr(request.app.state, "postgres_engine", None)
    if pg is None:
        raise HTTPException(status_code=503, detail="PostgreSQL 연결이 없습니다.")
    return run_logged_batch_job(
        session=session,
        settings=request.app.state.settings,
        job_name=JOB_ETL_POSTGRES_TO_MYSQL,
        trigger_type="manual",
        postgres_engine=pg,
    )


@router.get(
    "/api/dashboard/batch-job-logs",
    summary="배치 실행 로그 목록",
)
def dashboard_batch_job_logs(
    session: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query(description="RUNNING/SUCCESS/FAILED/RETRIED")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    rows = BatchJobLogRepository(session).fetch_recent(status=status, limit=limit)
    return {"rows": rows}


@router.post(
    "/api/dashboard/batch-job-logs/retry-due",
    summary="실패 배치 즉시 재처리",
)
def dashboard_retry_due_batch_jobs(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    return retry_due_batch_jobs(
        settings=request.app.state.settings,
        session_factory=request.app.state.session_factory,
        postgres_engine=getattr(request.app.state, "postgres_engine", None),
        limit=limit,
    )


@router.get(
    "/api/dashboard/stats",
    response_model=DashboardSnapshot,
    summary="대시보드 집계 JSON",
    description="게이지, 월별 추이, 진료유형 비중, 상위 진료과, KPI를 한 번에 반환합니다.",
)
def dashboard_stats_json(
    service: Annotated[DashboardApplicationService, Depends(get_dashboard_service)],
) -> DashboardSnapshot:
    return service.get_snapshot()


@router.get(
    "/api/dashboard/table-stats",
    response_model=TableStatsSnapshot,
    summary="테이블별 통계 목록",
    description="주요 테이블별 전체 건수, 오늘 생성 건수, 마지막 생성 시각을 반환합니다.",
)
def dashboard_table_stats_json(
    service: Annotated[DashboardApplicationService, Depends(get_dashboard_service)],
) -> TableStatsSnapshot:
    return service.get_table_stats()


@router.get(
    "/api/dashboard/table-stats/{table_name}",
    response_model=TableDetailSnapshot,
    summary="테이블 통계 상세",
    description="단일 테이블의 기본 지표, 최근 14일 생성 추이, 최근 20개 레코드를 반환합니다.",
    responses={404: {"description": "알 수 없는 테이블 이름"}},
)
def dashboard_table_detail_json(
    table_name: Annotated[
        str,
        ApiPath(
            description="조회할 테이블명",
            examples=["treatments", "Patient", "examination_schedule"],
        ),
    ],
    service: Annotated[DashboardApplicationService, Depends(get_dashboard_service)],
) -> TableDetailSnapshot:
    try:
        return service.get_table_detail(table_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/dashboard/tables",
    response_class=HTMLResponse,
    summary="테이블 통계 페이지",
    description="테이블별 건수를 표 형태로 보여주는 HTML 페이지입니다.",
)
def dashboard_tables_page(
    request: Request,
    service: Annotated[DashboardApplicationService, Depends(get_dashboard_service)],
) -> HTMLResponse:
    stats = service.get_table_stats()
    chart_rows = [
        {
            "table_name": r.table_name,
            "table_name_kr": _TABLE_NAME_KR.get(r.table_name, r.table_name),
            "total_count": r.total_count,
            "today_count": r.today_count,
            "last_created_at": r.last_created_at,
        }
        for r in stats.rows
    ]
    return templates.TemplateResponse(
        request=request,
        name="dashboard_tables.html",
        context={"stats": stats, "table_name_kr": _TABLE_NAME_KR, "chart_rows": chart_rows},
    )


@router.get(
    "/dashboard/tables/{table_name}",
    response_class=HTMLResponse,
    summary="테이블 통계 상세 페이지",
    description="선택한 테이블의 지표와 최근 레코드를 보여주는 HTML 페이지입니다.",
    responses={404: {"description": "알 수 없는 테이블 이름"}},
)
def dashboard_table_detail_page(
    table_name: Annotated[
        str,
        ApiPath(
            description="조회할 테이블명",
            examples=["treatments", "Patient", "examination_schedule"],
        ),
    ],
    request: Request,
    service: Annotated[DashboardApplicationService, Depends(get_dashboard_service)],
) -> HTMLResponse:
    try:
        detail = service.get_table_detail(table_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    recent_daily_chart = [{"day": x.day, "count": x.count} for x in detail.recent_daily]
    column_label_kr = {col: _column_label_kr(col) for col in detail.columns}
    column_headers_kr = [_column_label_kr(col) for col in detail.columns]
    return templates.TemplateResponse(
        request=request,
        name="dashboard_table_detail.html",
        context={
            "detail": detail,
            "display_table_name": _TABLE_NAME_KR.get(table_name, table_name),
            "recent_daily_chart": recent_daily_chart,
            "column_name_kr": _COLUMN_NAME_KR,
            "value_kr": _VALUE_KR,
            "column_label_kr": column_label_kr,
            "column_headers_kr": column_headers_kr,
        },
    )
