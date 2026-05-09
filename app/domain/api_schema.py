from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="서비스 상태 값", examples=["ok"])


class ClinicalEventOut(BaseModel):
    clinical_event_id: int = Field(description="진료 이벤트 PK")
    category: str = Field(description="유형: OUTPATIENT, EMERGENCY, INPATIENT, HEALTH_CHECKUP, LAB, IMAGING, PHARMACY, REHAB, TELEMEDICINE 등")
    occurred_on: str = Field(description="발생일 (YYYY-MM-DD)")
    department: str | None = Field(default=None, description="진료과")
    title: str = Field(description="제목")
    summary: str | None = Field(default=None, description="요약")
    status: str | None = Field(
        default=None,
        description="상태(화면 표시용 한글: 완료·예약·취소 등. DB 코드는 서버에서 변환)",
    )
    institution_name: str | None = Field(default=None, description="기관명")


class MyHealthResponse(BaseModel):
    patient_no: int = Field(description="환자번호")
    patient_name: str | None = Field(default=None, description="환자명")
    resolved_by: str = Field(description="조회에 사용한 식별 방식")
    profile: dict[str, object] | None = Field(default=None, description="혈액형·키·몸무게·앱 ID 등")
    disability: dict[str, object] | None = Field(default=None, description="장애 정보")
    clinical_events_by_category: dict[str, list[ClinicalEventOut]] = Field(
        description="진료·검사 이력을 category 별로 묶은 목록",
    )
    latest_vitals: dict[str, object] | None = Field(default=None, description="최근 웨어러블/앱 생체 측정 1건")
    daily_wellness_today: dict[str, object] | None = Field(default=None, description="당일 걸음·수면·스트레스 요약")


class PipelineRunResponse(BaseModel):
    job: str = Field(description="실행된 작업 타입", examples=["initial", "completion"])
    batch_log_id: int | None = Field(default=None, description="batch_job_log 실행 로그 ID")
    suffix: str | None = Field(default=None, description="실행 시각 기반 식별 접미사")
    patients_inserted_from: int | None = Field(default=None, description="초기 배치 환자 시작 번호")
    check_ins: dict[str, int] | None = Field(default=None, description="접수 생성 결과")
    treatments: dict[str, int] | None = Field(default=None, description="진료 생성 결과")
    prescription_ids: list[int] | None = Field(default=None, description="처방 ID 목록")
    extra: dict[str, Any] = Field(default_factory=dict, description="작업별 추가 반환 데이터")
