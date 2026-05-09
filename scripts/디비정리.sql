/* =====================================================================
 환자 / 진료 / 건강 관련 테이블 정리 SQL
 ---------------------------------------------------------------------
 범위 : 도메인·임상·지원 모듈의 지속성 엔티티 정의 기준
 환자·진료·처방·검사·진단서·건강검진·장애·통계 영역 포함
 ===================================================================== */


/* =====================================================================
 1. 공통/코드 영역
 ===================================================================== */

-- 진료과 참조용 마스터 
CREATE TABLE department (
    id                  BIGINT          NOT NULL AUTO_INCREMENT COMMENT '진료과 PK',
    department_code     VARCHAR(10)     NOT NULL                COMMENT '진료과 코드, 중복 불가',
    department_name     VARCHAR(100)    NOT NULL                COMMENT '진료과 명, 중복 불가',
    department_eng_name VARCHAR(100)    NULL                    COMMENT '진료과 영문명, 중복 불가',
    department_type     VARCHAR(30)     NOT NULL                COMMENT '진료과 분류 도메인 열거형 진료과 분류값',
    created_date        DATETIME        NULL                    COMMENT '생성일시',
    last_modified_date  DATETIME        NULL                    COMMENT '수정일시',
    intt_cd             VARCHAR(10)     NULL                    COMMENT '기관 코드 멀티테넌시',
    PRIMARY KEY (id),
    UNIQUE KEY uk_department_code     (department_code),
    UNIQUE KEY uk_department_name     (department_name),
    UNIQUE KEY uk_department_eng_name (department_eng_name)
) COMMENT='진료과 마스터';


-- 한국표준질병분류 KCD 코드
CREATE TABLE kcd_code (
    id                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT 'KCD PK',
    code               VARCHAR(10)  NOT NULL                COMMENT 'KCD 코드, 중복 불가',
    name_korean        VARCHAR(200) NOT NULL                COMMENT '질병명 한글',
    name_english       VARCHAR(200) NULL                    COMMENT '질병명 영문',
    category           VARCHAR(20)  NULL                    COMMENT '대분류 카테고리',
    description        VARCHAR(500) NULL                    COMMENT '상세 설명',
    active             TINYINT(1)   NOT NULL DEFAULT 1      COMMENT '사용 여부 1=활성, 0=비활성',
    created_date       DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date DATETIME     NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (id),
    UNIQUE KEY uk_kcd_code        (code),
    KEY        idx_kcd_code       (code),
    KEY        idx_kcd_name_korean(name_korean)
) COMMENT='한국표준질병분류 KCD 마스터';


/* =====================================================================
 2. 환자 영역, 도메인 패키지
 ===================================================================== */

-- 환자 마스터
CREATE TABLE Patient (
    patient_no          BIGINT        NOT NULL                COMMENT '환자번호 PK, 8자리 환자식별자',
    patient_name        VARCHAR(50)   NOT NULL                COMMENT '환자명',
    patient_rrn         VARCHAR(14)   NOT NULL                COMMENT '주민등록번호 암호화 저장 권장, 유일값 권장',
    patient_gender      VARCHAR(10)   NOT NULL                COMMENT '성별 코드, 남성 여성 등',
    patient_birth       DATE          NULL                    COMMENT '생년월일',
    patient_address     VARCHAR(200)  NULL                    COMMENT '주소',
    patient_email       VARCHAR(100)  NOT NULL                COMMENT '이메일 필드 중복 불가, 값 객체 패턴',
    patient_tel         VARCHAR(20)   NOT NULL                COMMENT '연락처 필드 중복 불가, 값 객체 패턴',
    patient_foreign     CHAR(1)       NOT NULL DEFAULT '0'    COMMENT '외국인 여부, 예 아니오 또는 1과 0 코드',
    patient_passport    VARCHAR(50)   NULL                    COMMENT '여권번호, 외국인인 경우 유일해야 함',

    patient_hypass_YN   CHAR(1)       NULL                    COMMENT '하이패스 자동수납 사용 여부',
    patient_last_visit  DATE          NULL                    COMMENT '최근 방문일',
    guardian            VARCHAR(50)   NULL                    COMMENT '보호자 정보',
    created_date        DATETIME      NULL                    COMMENT '생성일시',
    last_modified_date  DATETIME      NULL                    COMMENT '수정일시',
    intt_cd             VARCHAR(10)   NULL                    COMMENT '기관 코드',
    PRIMARY KEY (patient_no),
    UNIQUE KEY uk_patient_rrn      (patient_rrn),
    UNIQUE KEY uk_patient_email    (patient_email),
    UNIQUE KEY uk_patient_tel      (patient_tel),
    UNIQUE KEY uk_patient_passport (patient_passport)
) COMMENT='환자 마스터';


/* =====================================================================
 2-1. 앱·웨어러블 미러 (PostgreSQL 동기화 대상, ETL 10시 적재)
 ===================================================================== */

CREATE TABLE user_app_profile (
    patient_no        BIGINT        NOT NULL                COMMENT '환자번호 Patient FK',
    app_user_id       VARCHAR(32)   NULL                    COMMENT '앱 사용자 ID',
    blood_type        VARCHAR(10)   NULL                    COMMENT '혈액형',
    height_cm         DECIMAL(5,1)  NULL                    COMMENT '키 cm',
    weight_kg         DECIMAL(5,1)  NULL                    COMMENT '몸무게 kg',
    created_date      DATETIME      NULL                    COMMENT '생성일시',
    last_modified_date DATETIME     NULL                    COMMENT '수정일시',
    intt_cd           VARCHAR(10)   NULL                    COMMENT '기관 코드',
    PRIMARY KEY (patient_no),
    CONSTRAINT fk_user_app_profile_patient FOREIGN KEY (patient_no) REFERENCES Patient(patient_no)
) COMMENT='앱·웨어러블 확장 프로필 PostgreSQL 미러';


CREATE TABLE wearable_vital (
    vital_id                   BIGINT        NOT NULL AUTO_INCREMENT COMMENT '측정 PK',
    patient_no                 BIGINT        NOT NULL                COMMENT '환자번호',
    measured_at                DATETIME      NOT NULL                COMMENT '측정 시각',
    heart_rate_bpm             INT           NULL                    COMMENT '심박',
    blood_pressure_systolic    INT           NULL                    COMMENT '수축기',
    blood_pressure_diastolic   INT           NULL                    COMMENT '이완기',
    body_temp_c                DECIMAL(4,1)  NULL                    COMMENT '체온',
    stress_score               DECIMAL(6,2)  NULL                    COMMENT '스트레스',
    source_channel             VARCHAR(32)   NULL                    COMMENT '출처 wearable/app',
    created_date               DATETIME      NULL                    COMMENT '적재일시',
    intt_cd                    VARCHAR(10)   NULL                    COMMENT '기관 코드',
    PRIMARY KEY (vital_id),
    UNIQUE KEY uk_wearable_patient_measured (patient_no, measured_at),
    KEY idx_wearable_patient (patient_no),
    CONSTRAINT fk_wearable_vital_patient FOREIGN KEY (patient_no) REFERENCES Patient(patient_no)
) COMMENT='웨어러블 생체 측정 PostgreSQL→MySQL 적재';


CREATE TABLE wearable_daily_wellness (
    patient_no       BIGINT        NOT NULL                COMMENT '환자번호',
    summary_date     DATE          NOT NULL                COMMENT '기준일',
    step_count       INT           NOT NULL DEFAULT 0       COMMENT '걸음 수',
    step_goal        INT           NOT NULL DEFAULT 1000    COMMENT '목표 걸음',
    sleep_hours      DECIMAL(4,1)  NULL                    COMMENT '수면 시간',
    stress_level     DECIMAL(6,2)  NULL                    COMMENT '스트레스 요약',
    created_date     DATETIME      NULL                    COMMENT '생성일시',
    last_modified_date DATETIME    NULL                    COMMENT '수정일시',
    intt_cd          VARCHAR(10)   NULL                    COMMENT '기관 코드',
    PRIMARY KEY (patient_no, summary_date),
    CONSTRAINT fk_wearable_daily_patient FOREIGN KEY (patient_no) REFERENCES Patient(patient_no)
) COMMENT='일별 웰니스 PostgreSQL→MySQL 적재';


/* =====================================================================
 3. 진료 흐름 영역, 임상 패키지
 ===================================================================== */

-- 접수 체크인 
CREATE TABLE check_in (
    checkIn_id         BIGINT        NOT NULL AUTO_INCREMENT COMMENT '접수 PK',
    patient_no         BIGINT        NOT NULL                COMMENT '환자번호 참조 Patient.patient_no',
    user_id            BIGINT        NULL                    COMMENT '담당 사용자 ID 참조 users.id',
    checkIn_date       DATETIME      NOT NULL                COMMENT '접수 일시',
    checkIn_status     VARCHAR(20)   NOT NULL                COMMENT '접수 상태 코드, 대기·완료·취소 등',
    checkIn_comment    VARCHAR(500)  NULL                    COMMENT '접수 메모',
    created_date       DATETIME      NULL                    COMMENT '생성일시',
    last_modified_date DATETIME      NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)   NULL                    COMMENT '기관 코드',
    PRIMARY KEY (checkIn_id),
    KEY idx_checkin_patient (patient_no),
    KEY idx_checkin_date    (checkIn_date),
    CONSTRAINT fk_checkin_patient FOREIGN KEY (patient_no) REFERENCES Patient(patient_no)
) COMMENT='환자 접수 체크인';


-- 예약
CREATE TABLE Reservation (
    reservation_id              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '예약 PK',
    patient_no                  BIGINT        NOT NULL                COMMENT '환자번호 참조 Patient.patient_no',
    user_id                     BIGINT        NULL                    COMMENT '담당 사용자 ID 참조 users.id',
    reservation_datetime        DATETIME      NOT NULL                COMMENT '예약 일시',
    reservation_status          VARCHAR(20)   NOT NULL                COMMENT '예약 상태 코드, 대기·확정·취소·완료 등',
    reservation_YN              CHAR(1)       NULL                    COMMENT '예약 활성 여부 코드, 과거 호환 필드',
    reservation_change_datetime DATETIME      NULL                    COMMENT '예약 변경 일시',
    reservation_change_cause    VARCHAR(500)  NULL                    COMMENT '예약 변경 사유',
    created_date                DATETIME      NULL                    COMMENT '생성일시',
    last_modified_date          DATETIME      NULL                    COMMENT '수정일시',
    intt_cd                     VARCHAR(10)   NULL                    COMMENT '기관 코드',
    PRIMARY KEY (reservation_id),
    KEY idx_reservation_patient (patient_no),
    KEY idx_reservation_datetime(reservation_datetime),
    CONSTRAINT fk_reservation_patient FOREIGN KEY (patient_no) REFERENCES Patient(patient_no)
) COMMENT='환자 예약';


-- 진료 외래/입원/응급 공통 헤더 
CREATE TABLE treatments (
    treatment_id         BIGINT        NOT NULL AUTO_INCREMENT COMMENT '진료 PK',
    checkIn_id           BIGINT        NULL                    COMMENT '연결된 접수 ID FK',
    patient_no           BIGINT        NULL                    COMMENT '환자번호 참조 Patient.patient_no',
    treatment_doc        BIGINT        NOT NULL                COMMENT '진료 의사 ID 참조 users.id',
    department_id        BIGINT        NULL                    COMMENT '진료과 ID 참조 department.id',
    treatment_type       VARCHAR(20)   NOT NULL                COMMENT '진료 유형 코드, 외래·입원·응급 등',

    treatment_status     VARCHAR(20)   NOT NULL                COMMENT '진료 상태 코드, 대기·진행중·완료·취소 등',
    treatment_date       DATETIME      NOT NULL                COMMENT '진료 일시',
    treatment_start_time DATETIME      NULL                    COMMENT '진료 시작 시각',
    treatment_end_time   DATETIME      NULL                    COMMENT '진료 종료 시각',
    treatment_comment    TEXT          NULL                    COMMENT '진료 소견/메모',
    treatment_dept       VARCHAR(100)  NULL                    COMMENT '진료과명 캐싱 department.name 스냅샷',
    synced_to_postgres_at DATETIME     NULL                    COMMENT 'PostgreSQL patient_clinical_event 반영 시각 ETL',
    created_date         DATETIME      NULL                    COMMENT '생성일시',
    last_modified_date   DATETIME      NULL                    COMMENT '수정일시',
    intt_cd              VARCHAR(10)   NULL                    COMMENT '기관 코드',
    PRIMARY KEY (treatment_id),
    KEY idx_treatments_patient    (patient_no),
    KEY idx_treatments_doc        (treatment_doc),
    KEY idx_treatments_date       (treatment_date),
    KEY idx_treatments_department (department_id),
    KEY idx_treatments_sync_pg    (patient_no, synced_to_postgres_at),
    CONSTRAINT fk_treatments_checkin    FOREIGN KEY (checkIn_id)    REFERENCES check_in(checkIn_id),
    CONSTRAINT fk_treatments_patient    FOREIGN KEY (patient_no)    REFERENCES Patient(patient_no),
    CONSTRAINT fk_treatments_department FOREIGN KEY (department_id) REFERENCES department(id)
) COMMENT='진료 헤더 외래/입원/응급 공통';


-- 외래 진료
CREATE TABLE Out_Treatments (
    treatment_id        BIGINT       NOT NULL                COMMENT '진료 PK treatments.treatment_id 와 1:1',
    checkIn_id          BIGINT       NOT NULL                COMMENT '접수 ID FK',
    treatment_status    VARCHAR(20)  NULL                    COMMENT '외래 진료 상태',
    pre_treatment_id    BIGINT       NULL                    COMMENT '이전 외래 진료 ID 재방문 추적',
    treatment_comment   TEXT         NULL                    COMMENT '외래 진료 소견',
    created_date        DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date  DATETIME     NULL                    COMMENT '수정일시',
    intt_cd             VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (treatment_id),
    KEY idx_out_treatment_checkin (checkIn_id),
    CONSTRAINT fk_out_treatment_treatment FOREIGN KEY (treatment_id) REFERENCES treatments(treatment_id),
    CONSTRAINT fk_out_treatment_checkin   FOREIGN KEY (checkIn_id)   REFERENCES check_in(checkIn_id),
    CONSTRAINT fk_out_treatment_pre       FOREIGN KEY (pre_treatment_id) REFERENCES Out_Treatments(treatment_id)
) COMMENT='외래 진료';


-- 입원 진료
CREATE TABLE In_Treatments (
    treatment_id       BIGINT       NOT NULL                COMMENT '진료 PK treatments.treatment_id 와 1:1',
    checkIn_id         BIGINT       NOT NULL                COMMENT '접수 ID FK',
    treatment_status   VARCHAR(20)  NULL                    COMMENT '입원 진료 상태',
    created_date       DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date DATETIME     NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (treatment_id),
    KEY idx_in_treatment_checkin (checkIn_id),
    CONSTRAINT fk_in_treatment_treatment FOREIGN KEY (treatment_id) REFERENCES treatments(treatment_id),
    CONSTRAINT fk_in_treatment_checkin   FOREIGN KEY (checkIn_id)   REFERENCES check_in(checkIn_id)
) COMMENT='입원 진료';


-- 응급 진료
CREATE TABLE Emergency_Treatments (
    treatment_id       BIGINT       NOT NULL                COMMENT '진료 PK treatments.treatment_id 와 1:1',
    checkIn_id         BIGINT       NOT NULL                COMMENT '접수 ID FK',
    treatment_status   VARCHAR(20)  NULL                    COMMENT '응급 진료 상태',
    created_date       DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date DATETIME     NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (treatment_id),
    KEY idx_em_treatment_checkin (checkIn_id),
    CONSTRAINT fk_em_treatment_treatment FOREIGN KEY (treatment_id) REFERENCES treatments(treatment_id),
    CONSTRAINT fk_em_treatment_checkin   FOREIGN KEY (checkIn_id)   REFERENCES check_in(checkIn_id)
) COMMENT='응급 진료';


-- 의사 진료 세션 실제 의사가 환자를 본 시간 단위 로그 
CREATE TABLE doctor_treatment (
    doctorTreatment_id        BIGINT       NOT NULL AUTO_INCREMENT COMMENT '의사 진료 세션 PK',
    patient_no                BIGINT       NOT NULL                COMMENT '환자번호 FK',
    user_id                   BIGINT       NOT NULL                COMMENT '의사 사용자 ID FK',
    doctorTreatment_starttime DATETIME     NOT NULL                COMMENT '진료 시작 시각',
    doctorTreatment_endtime   DATETIME     NULL                    COMMENT '진료 종료 시각',
    created_date              DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date        DATETIME     NULL                    COMMENT '수정일시',
    intt_cd                   VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (doctorTreatment_id),
    KEY idx_doctor_treatment_patient (patient_no),
    KEY idx_doctor_treatment_user    (user_id),
    KEY idx_doctor_treatment_start   (doctorTreatment_starttime),
    CONSTRAINT fk_doctor_treatment_patient FOREIGN KEY (patient_no) REFERENCES Patient(patient_no)
) COMMENT='의사 진료 세션 로그 실제 진료 수행 시간 단위';


/* =====================================================================
 4. 처방 영역, 임상 패키지
 ===================================================================== */

-- 처방 헤더
CREATE TABLE Prescription (
    prescription_id     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '처방 PK',
    treatment_id        BIGINT       NOT NULL                COMMENT '진료 ID 참조 treatments',
    patient_no          BIGINT       NOT NULL                COMMENT '환자번호 참조 Patient',
    prescription_doc    BIGINT       NOT NULL                COMMENT '처방 의사 사용자 ID 참조 users.id',
    prescription_date   DATETIME     NOT NULL                COMMENT '처방 일시',
    prescription_status VARCHAR(20)  NOT NULL                COMMENT '처방 상태 코드, 대기·처방·조제완료·취소 등',
    prescription_type   VARCHAR(20)  NOT NULL                COMMENT '처방 유형 코드, 외래·입원·응급 등',

    prescription_memo   TEXT         NULL                    COMMENT '처방 메모/취소 사유',
    created_date        DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date  DATETIME     NULL                    COMMENT '수정일시',
    intt_cd             VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (prescription_id),
    KEY idx_prescription_treatment (treatment_id),
    KEY idx_prescription_patient   (patient_no),
    KEY idx_prescription_doc       (prescription_doc),
    CONSTRAINT fk_prescription_treatment FOREIGN KEY (treatment_id) REFERENCES treatments(treatment_id),
    CONSTRAINT fk_prescription_patient   FOREIGN KEY (patient_no)   REFERENCES Patient(patient_no)
) COMMENT='처방 헤더';


-- 처방 항목 약물 단위 
CREATE TABLE Prescription_Item (
    prescription_item_id BIGINT       NOT NULL AUTO_INCREMENT COMMENT '처방 항목 PK',
    prescription_id      BIGINT       NOT NULL                COMMENT '처방 ID 참조 Prescription',
    drug_code            VARCHAR(50)  NOT NULL                COMMENT '약물 코드 식약처/EDI 코드',
    drug_name            VARCHAR(200) NOT NULL                COMMENT '약물명',
    dosage               VARCHAR(500) NOT NULL                COMMENT '용법 예: 식후 30분',
    dose                 VARCHAR(100) NOT NULL                COMMENT '용량 예: 500mg',
    frequency            INT          NOT NULL                COMMENT '1일 복용 횟수 1~10',
    days                 INT          NOT NULL                COMMENT '총 복용 일수 1~365',
    total_quantity       INT          NOT NULL                COMMENT '총 수량',
    unit                 VARCHAR(20)  NOT NULL                COMMENT '수량 단위 정, mL 등',
    special_note         TEXT         NULL                    COMMENT '특이사항/복용 주의',
    created_date         DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date   DATETIME     NULL                    COMMENT '수정일시',
    intt_cd              VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (prescription_item_id),
    KEY idx_prescription_item_prescription (prescription_id),
    KEY idx_prescription_item_drug         (drug_code),
    CONSTRAINT fk_prescription_item_prescription FOREIGN KEY (prescription_id) REFERENCES Prescription(prescription_id)
) COMMENT='처방 항목 약물별 상세';


/* =====================================================================
 5. 진단서 영역, 임상 패키지
 ===================================================================== */

-- 진단서 발급
CREATE TABLE diagnosis_certificate (
    certificate_id     BIGINT        NOT NULL AUTO_INCREMENT COMMENT '진단서 PK',
    certificate_number VARCHAR(20)   NOT NULL                COMMENT '진단서 번호, 중복 불가',
    patient_id         BIGINT        NOT NULL                COMMENT '환자 ID 참조 Patient.patient_no',
    doctor_id          BIGINT        NOT NULL                COMMENT '발급 의사 ID 참조 users.id',
    kcd_code_id        BIGINT        NOT NULL                COMMENT 'KCD 코드 ID 참조 kcd_code.id',
    diagnosis_name     VARCHAR(200)  NOT NULL                COMMENT '진단명 확정 진단',
    diagnosis_date     DATE          NOT NULL                COMMENT '진단일',
    clinical_findings  VARCHAR(1000) NULL                    COMMENT '임상 소견',
    purpose            VARCHAR(500)  NULL                    COMMENT '진단서 발급 목적',
    issued_at          DATETIME      NOT NULL                COMMENT '진단서 발급 일시',
    status             VARCHAR(20)   NOT NULL DEFAULT 'ISSUED' COMMENT '상태 코드, 최초발급·재발급·폐기 등',
    created_date       DATETIME      NULL                    COMMENT '생성일시',
    last_modified_date DATETIME      NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)   NULL                    COMMENT '기관 코드',
    PRIMARY KEY (certificate_id),
    UNIQUE KEY uk_certificate_number (certificate_number),
    KEY idx_certificate_patient (patient_id),
    KEY idx_certificate_doctor  (doctor_id),
    KEY idx_certificate_kcd     (kcd_code_id),
    CONSTRAINT fk_certificate_patient FOREIGN KEY (patient_id)  REFERENCES Patient(patient_no),
    CONSTRAINT fk_certificate_kcd     FOREIGN KEY (kcd_code_id) REFERENCES kcd_code(id)
) COMMENT='진단서 발급 이력';


/* =====================================================================
 6. 검사·검진 영역, 지원 패키지
 ===================================================================== */

-- 검사 항목 마스터 검사 종류 정의 
CREATE TABLE examination (
    examination_id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '검사 PK',
    equipment_id            BIGINT       NULL                    COMMENT '검사 장비 ID 참조 equipment.equipment_id',
    examination_name        VARCHAR(100) NOT NULL                COMMENT '검사명 예: 흉부 X-ray',
    examination_type        VARCHAR(50)  NOT NULL                COMMENT '검사 유형 영상/혈액/생리 등',
    examination_constraints TEXT         NULL                    COMMENT '검사 시 주의/제약 사항',
    examination_location    VARCHAR(100) NOT NULL                COMMENT '검사 위치/실 명',
    examination_price       BIGINT       NOT NULL DEFAULT 0      COMMENT '검사 가격 원',
    created_date            DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date      DATETIME     NULL                    COMMENT '수정일시',
    intt_cd                 VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (examination_id),
    KEY idx_examination_type (examination_type)
) COMMENT='검사 항목 마스터';


-- 검사 일정 검사 예약/스케줄 
CREATE TABLE examination_schedule (
    examination_schedule_id BIGINT       NOT NULL AUTO_INCREMENT COMMENT '검사 일정 PK',
    examination_id          BIGINT       NOT NULL                COMMENT '검사 ID 참조 examination',
    patient_no              BIGINT       NOT NULL                COMMENT '환자번호 참조 Patient',
    treatment_id            BIGINT       NOT NULL                COMMENT '진료 ID 참조 treatments',
    user_id                 BIGINT       NOT NULL                COMMENT '담당자 ID 참조 users.id',
    examination_date        DATE         NULL                    COMMENT '검사 예정일 yyyy-MM-dd',
    created_date            DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date      DATETIME     NULL                    COMMENT '수정일시',
    intt_cd                 VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (examination_schedule_id),
    KEY idx_exam_sched_examination (examination_id),
    KEY idx_exam_sched_patient     (patient_no),
    KEY idx_exam_sched_treatment   (treatment_id),
    KEY idx_exam_sched_date        (examination_date),
    CONSTRAINT fk_exam_sched_examination FOREIGN KEY (examination_id) REFERENCES examination(examination_id),
    CONSTRAINT fk_exam_sched_patient     FOREIGN KEY (patient_no)     REFERENCES Patient(patient_no),
    CONSTRAINT fk_exam_sched_treatment   FOREIGN KEY (treatment_id)   REFERENCES treatments(treatment_id)
) COMMENT='검사 일정/예약';


-- 검사 결과
CREATE TABLE examination_result (
    examination_result_id BIGINT      NOT NULL AUTO_INCREMENT COMMENT '검사 결과 PK',
    examination_id        BIGINT      NOT NULL                COMMENT '검사 ID 참조 examination',
    patient_no            BIGINT      NOT NULL                COMMENT '환자번호 참조 Patient',
    treatment_id          BIGINT      NOT NULL                COMMENT '진료 ID 참조 treatments',
    examination_date      DATE        NULL                    COMMENT '검사 시행일',
    examination_result    TEXT        NULL                    COMMENT '검사 결과 본문',
    examination_normal    TINYINT(1)  NULL                    COMMENT '정상 여부 1=정상, 0=이상',
    examination_notes     TEXT        NULL                    COMMENT '검사 결과 비고',
    created_date          DATETIME    NULL                    COMMENT '생성일시',
    last_modified_date    DATETIME    NULL                    COMMENT '수정일시',
    intt_cd               VARCHAR(10) NULL                    COMMENT '기관 코드',
    PRIMARY KEY (examination_result_id),
    KEY idx_exam_result_examination (examination_id),
    KEY idx_exam_result_patient     (patient_no),
    KEY idx_exam_result_treatment   (treatment_id),
    CONSTRAINT fk_exam_result_examination FOREIGN KEY (examination_id) REFERENCES examination(examination_id),
    CONSTRAINT fk_exam_result_patient     FOREIGN KEY (patient_no)     REFERENCES Patient(patient_no),
    CONSTRAINT fk_exam_result_treatment   FOREIGN KEY (treatment_id)   REFERENCES treatments(treatment_id)
) COMMENT='검사 결과';


-- 검사 수행 일지 검사 시행 시점/장비 사용 로그 
CREATE TABLE examination_journal (
    examination_journal_id     BIGINT      NOT NULL AUTO_INCREMENT COMMENT '검사 일지 PK',
    examination_id             BIGINT      NOT NULL                COMMENT '검사 ID 참조 examination',
    patient_no                 BIGINT      NOT NULL                COMMENT '환자번호 참조 Patient',
    treatment_id               BIGINT      NOT NULL                COMMENT '진료 ID 참조 treatments',
    user_id                    BIGINT      NOT NULL                COMMENT '검사 수행자 ID 참조 users.id',
    equipment_id               BIGINT      NOT NULL                COMMENT '사용 장비 ID 참조 equipment',
    examination_time           DATETIME    NULL                    COMMENT '검사 수행 시각',
    examination_equipment_usage TINYINT(1) NULL                    COMMENT '장비 사용 여부 1/0',
    examination_notes          TEXT        NULL                    COMMENT '수행 시 비고',
    created_date               DATETIME    NULL                    COMMENT '생성일시',
    last_modified_date         DATETIME    NULL                    COMMENT '수정일시',
    intt_cd                    VARCHAR(10) NULL                    COMMENT '기관 코드',
    PRIMARY KEY (examination_journal_id),
    KEY idx_exam_journal_examination (examination_id),
    KEY idx_exam_journal_patient     (patient_no),
    KEY idx_exam_journal_treatment   (treatment_id),
    CONSTRAINT fk_exam_journal_examination FOREIGN KEY (examination_id) REFERENCES examination(examination_id),
    CONSTRAINT fk_exam_journal_patient     FOREIGN KEY (patient_no)     REFERENCES Patient(patient_no),
    CONSTRAINT fk_exam_journal_treatment   FOREIGN KEY (treatment_id)   REFERENCES treatments(treatment_id)
) COMMENT='검사 수행 일지';


-- 혈액은행 혈액형/수혈 검사 기록 
CREATE TABLE blood_bank (
    blood_bank_id      BIGINT      NOT NULL AUTO_INCREMENT COMMENT '혈액은행 PK',
    examination_id     BIGINT      NOT NULL                COMMENT '검사 ID 참조 examination',
    patient_no         BIGINT      NOT NULL                COMMENT '환자번호 참조 Patient',
    treatment_id       BIGINT      NOT NULL                COMMENT '진료 ID 참조 treatments',
    user_id            BIGINT      NOT NULL                COMMENT '담당자 ID 참조 users.id',
    examination_time   DATETIME    NULL                    COMMENT '혈액 검사/수집 시각',
    blood_type         VARCHAR(10) NULL                    COMMENT '혈액형 A+, B-, O+, AB- 등',
    created_date       DATETIME    NULL                    COMMENT '생성일시',
    last_modified_date DATETIME    NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10) NULL                    COMMENT '기관 코드',
    PRIMARY KEY (blood_bank_id),
    KEY idx_blood_bank_patient (patient_no),
    CONSTRAINT fk_blood_bank_examination FOREIGN KEY (examination_id) REFERENCES examination(examination_id),
    CONSTRAINT fk_blood_bank_patient     FOREIGN KEY (patient_no)     REFERENCES Patient(patient_no),
    CONSTRAINT fk_blood_bank_treatment   FOREIGN KEY (treatment_id)   REFERENCES treatments(treatment_id)
) COMMENT='혈액은행 혈액형/수혈 검사';


/* =====================================================================
 7. 건강검진·장애 관련 영역, 지원 패키지
 ===================================================================== */

-- 건강검진 기관 전국 건강검진 가능 의료기관 목록 
CREATE TABLE health_checkup_institution (
    institution_id     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '검진 기관 PK',
    region_code        VARCHAR(10)  NULL                    COMMENT '지역 코드',
    region_name        VARCHAR(50)  NULL                    COMMENT '지역명',
    institution_name   VARCHAR(200) NOT NULL                COMMENT '기관명',
    institution_type   VARCHAR(50)  NOT NULL                COMMENT '기관 유형 병원/의원/검진센터 등',
    address            VARCHAR(500) NOT NULL                COMMENT '주소',
    sido               VARCHAR(50)  NULL                    COMMENT '시도',
    sigungu            VARCHAR(50)  NULL                    COMMENT '시군구',
    latitude           DOUBLE       NULL                    COMMENT '위도',
    longitude          DOUBLE       NULL                    COMMENT '경도',
    phone_number       VARCHAR(20)  NULL                    COMMENT '대표 전화번호',
    is_active          TINYINT(1)   NOT NULL DEFAULT 1      COMMENT '활성 여부 1/0',
    data_source        VARCHAR(100) NULL                    COMMENT '데이터 출처 공공데이터 포털 등',
    data_date          DATE         NULL                    COMMENT '데이터 기준일',
    created_date       DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date DATETIME     NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (institution_id),
    KEY idx_hci_region_code      (region_code),
    KEY idx_hci_institution_type (institution_type),
    KEY idx_hci_institution_name (institution_name),
    KEY idx_hci_is_active        (is_active),
    KEY idx_hci_region_type      (region_code, institution_type)
) COMMENT='건강검진 가능 기관 마스터';


-- 환자 장애 정보
CREATE TABLE disability (
    disability_id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '장애 정보 PK',
    patient_no             BIGINT       NOT NULL                COMMENT '환자번호, Patient 참조, 환자당 하나',
    disability_grade       VARCHAR(10)  NOT NULL                COMMENT '장애 등급 1급 ~ 6급',
    disability_type        VARCHAR(50)  NULL                    COMMENT '장애 유형 지체/시각/청각 등',
    assistive_device_YN    CHAR(1)      NOT NULL                COMMENT '보조기구 필요 여부, 예 아니오 코드',

    disability_device_type VARCHAR(100) NULL                    COMMENT '보조기구 종류 휠체어/보청기 등',
    created_date           DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date     DATETIME     NULL                    COMMENT '수정일시',
    intt_cd                VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (disability_id),
    UNIQUE KEY uk_disability_patient (patient_no),
    CONSTRAINT fk_disability_patient FOREIGN KEY (patient_no) REFERENCES Patient(patient_no)
) COMMENT='환자 장애 정보';


-- 장애인 돌봄/지원 기관
CREATE TABLE disability_care_institution (
    institution_id     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '돌봄 기관 PK',
    institution_type   VARCHAR(20)  NOT NULL                COMMENT '기관 분류',
    institution_name   VARCHAR(200) NOT NULL                COMMENT '기관명',
    service_type       VARCHAR(50)  NOT NULL                COMMENT '서비스 유형 활동지원/재활/주간보호 등',
    address            VARCHAR(500) NOT NULL                COMMENT '주소',
    sido               VARCHAR(50)  NULL                    COMMENT '시도',
    sigungu            VARCHAR(50)  NULL                    COMMENT '시군구',
    latitude           DOUBLE       NULL                    COMMENT '위도',
    longitude          DOUBLE       NULL                    COMMENT '경도',
    is_active          TINYINT(1)   NOT NULL DEFAULT 1      COMMENT '활성 여부 1/0',
    created_date       DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date DATETIME     NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (institution_id),
    KEY idx_dci_service_type     (service_type),
    KEY idx_dci_sido             (sido),
    KEY idx_dci_institution_type (institution_type),
    KEY idx_dci_is_active        (is_active)
) COMMENT='장애인 돌봄/지원 기관';


/* =====================================================================
 8. 건강관련 통계 영역, 임상에서 분석 도구로 이어지는 집계 
 ===================================================================== */

-- 입원 진료 통계 연도/지역/기관유형별 집계 
CREATE TABLE inpatient_statistics (
    statistics_id      BIGINT       NOT NULL AUTO_INCREMENT COMMENT '통계 PK',
    statistics_year    VARCHAR(4)   NOT NULL                COMMENT '통계 연도 예: 2024',
    institution_type   VARCHAR(50)  NOT NULL                COMMENT '의료기관 유형 상급/종합/병원/의원 등',
    region_code        VARCHAR(10)  NULL                    COMMENT '지역 코드',
    region_name        VARCHAR(50)  NULL                    COMMENT '지역명',
    visit_days         BIGINT       NOT NULL DEFAULT 0      COMMENT '내원 일수',
    benefit_days       BIGINT       NOT NULL DEFAULT 0      COMMENT '급여 일수',
    medical_fee        BIGINT       NOT NULL DEFAULT 0      COMMENT '진료비 총액 원',
    benefit_fee        BIGINT       NOT NULL DEFAULT 0      COMMENT '급여비 총액 원',
    data_source        VARCHAR(100) NULL                    COMMENT '데이터 출처',
    data_date          DATE         NULL                    COMMENT '데이터 기준일',
    created_date       DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date DATETIME     NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (statistics_id),
    KEY idx_ips_statistics_year  (statistics_year),
    KEY idx_ips_institution_type (institution_type),
    KEY idx_ips_region_code      (region_code),
    KEY idx_ips_year_region      (statistics_year, region_code)
) COMMENT='입원 진료 통계';


-- 진료과별 진료 통계
CREATE TABLE treatment_department_statistics (
    statistics_id      BIGINT       NOT NULL AUTO_INCREMENT COMMENT '통계 PK',
    statistics_year    VARCHAR(4)   NOT NULL                COMMENT '통계 연도',
    region_code        VARCHAR(10)  NULL                    COMMENT '지역 코드',
    region_name        VARCHAR(50)  NULL                    COMMENT '지역명',
    department_name    VARCHAR(100) NOT NULL                COMMENT '진료과명',
    patient_count      BIGINT       NOT NULL DEFAULT 0      COMMENT '환자 수',
    treatment_count    BIGINT       NOT NULL DEFAULT 0      COMMENT '진료 건수',
    medical_fee        BIGINT       NOT NULL DEFAULT 0      COMMENT '진료비 총액 원',
    benefit_fee        BIGINT       NOT NULL DEFAULT 0      COMMENT '급여비 총액 원',
    data_source        VARCHAR(100) NULL                    COMMENT '데이터 출처',
    data_date          DATE         NULL                    COMMENT '데이터 기준일',
    created_date       DATETIME     NULL                    COMMENT '생성일시',
    last_modified_date DATETIME     NULL                    COMMENT '수정일시',
    intt_cd            VARCHAR(10)  NULL                    COMMENT '기관 코드',
    PRIMARY KEY (statistics_id),
    UNIQUE KEY uk_tds_year_region_department (statistics_year, region_code, department_name),
    KEY idx_tds_statistics_year (statistics_year),
    KEY idx_tds_department_name (department_name),
    KEY idx_tds_region_code     (region_code),
    KEY idx_tds_year_department (statistics_year, department_name),
    KEY idx_tds_year_region     (statistics_year, region_code)
) COMMENT='진료과목별 진료 통계';
