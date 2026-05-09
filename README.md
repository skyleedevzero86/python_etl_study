# 진료 운영 비즈니스 통계 대시보드


<img width="1435" height="893" alt="image" src="https://github.com/user-attachments/assets/cc391939-8d1d-4e89-9c61-43d27994d0d5" />
<br/>
<img width="1312" height="892" alt="image" src="https://github.com/user-attachments/assets/34fbdc1b-e38c-4cfc-89cd-48bb0d3d795c" />
<br/>


PostgreSQL 에서 MySQL 로 전환 연습과 OLAP 학습을 정리하기 위한 저장소입니다. <br/>
FastAPI 기반으로 주간 배치 파이프라인, 통계 API, Jinja2 로 내려주는 대시보드 화면을 묶어 두었습니다.<br/>

---

## 요구 사항

### 런타임

- Python 3.10 이상 권장.
- pip 로 `requirements.txt` 패키지를 설치할 수 있는 환경.

### 데이터베이스

- MySQL 8.4, 기본 포트 3306.
- 사용자 인증이 **`caching_sha2_password`** 일 때 PyMySQL 이 RSA 핸드셰이크에 **`cryptography`** 패키지를 씁니다. `requirements.txt` 에 넣어 두었고, 패키지만 골라 깔았다면 `pip install cryptography` 로 보강하면 됩니다.
- 스키마는 저장소 루트의 `디비정리.sql` 과 일치해야 합니다.<br/>
  애플리케이션은 연결 문자열에서 지정한 데이터베이스 이름 예시로 `finsight2` 를 사용합니다.<br/>
- 앱에서 쓰는 DB 계정은 해당 데이터베이스에 `SELECT`, `INSERT` 등 필요한 권한이 있어야 합니다. <br/>
  최초 스키마 생성은 관리 계정으로 `scripts/apply_schema.py` 를 실행하는 흐름을 가정합니다.

### 네트워크

- 로컬에서만 쓸 때는 MySQL 과 앱이 같은 머신에 있으면 됩니다.
- 서버에 올릴 때는 방화벽에서 앱 리스닝 포트와 MySQL 포트 접근 정책을 맞춥니다.

---

## 아키텍처 요약

### 레이어 구조

클린 아키텍처에 가깝게 네 구역으로 나눴습니다. 안쪽은 비즈니스 규칙과 인터페이스, 바깥은 프레임워크와 DB 구현입니다.

| 계층         | 역할                                             | 이 저장소의 위치      |
| ------------ | ------------------------------------------------ | --------------------- |
| 도메인       | 열거형, 집계 모델, 저장소 포트 프로토콜          | `app/domain/`         |
| 애플리케이션 | 유즈케이스 조립, 파이프라인·대시보드 서비스      | `app/application/`    |
| 인프라       | 설정, SQLAlchemy, MySQL 저장소 구현, APScheduler | `app/infrastructure/` |
| 프레젠테이션 | FastAPI 앱, 라우터, Jinja 템플릿, 의존성 주입    | `app/presentation/`   |

의존성 방향은 **프레젠테이션 → 애플리케이션 → 도메인** 이고, 인프라는 포트를 구현해 애플리케이션에 주입합니다.

### 구성 요소

- **`app/presentation/main.py`**: FastAPI 앱 생성, 라우터 마운트, 수명 주기 안에서 엔진·세션 팩토리와 주간 스케줄러를 붙입니다.
- **`app/presentation/dependencies.py`**: 요청별 DB 세션과 파이프라인·대시보드 서비스 조립.
- **`app/infrastructure/repositories/pipeline_mysql.py`**: 초기 배치와 완료·실패 샘플 배치의 `INSERT` 로직.
- **`app/infrastructure/repositories/dashboard_mysql.py`**: 대시보드용 읽기 전용 집계 SQL.
- **`app/infrastructure/scheduler.py`**: APScheduler 로 매주 지정 요일의 두 시각에 배치 실행. OS 크론 대신 프로세스 안에서 도는 형태입니다.
- **`scripts/apply_schema.py`**: MySQL 에 데이터베이스 생성 후 `디비정리.sql` 문장을 순서대로 실행합니다.

### 데이터·요청 흐름

1. **주간 배치**  
   스케줄러가 `PipelineJob` 에 따라 저장소 메서드를 호출하고, 동일 진입점은 `POST /pipeline/run/{job}` 으로 수동 재현할 수 있습니다.<br/>
   초기 배치는 마스터·환자 쪽 행을, 오후 계열 배치는 접수·진료·처방의 완료·취소 패턴 샘플을 넣습니다.<br/>

2. **대시보드**  
   브라우저는 `/dashboard` HTML 을 받고, 클라이언트 스크립트가 `GET /api/dashboard/stats` 로 JSON 집계를 가져와 차트를 그립니다.<br/>
   집계는 `treatments`, `department`, `examination` 계열 테이블을 읽습니다.

3. **설정**  
   `pydantic-settings` 가 `.env` 를 읽어 접속 문자열과 스케줄 요일·시각을 결정합니다.<br/>
   샘플 키는 `.env.example` 에 있습니다.

```mermaid
flowchart LR
  subgraph presentation [프레젠테이션]
    HTTP[FastAPI 라우터]
    UI[Jinja 대시보드]
  end
  subgraph application [애플리케이션]
    PS[Pipeline 서비스]
    DS[Dashboard 서비스]
  end
  subgraph infrastructure [인프라]
    PR[Pipeline 저장소]
    DR[Dashboard 저장소]
    SCH[APScheduler]
    DB[(MySQL)]
  end
  HTTP --> PS
  HTTP --> DS
  UI --> HTTP
  PS --> PR
  DS --> DR
  PR --> DB
  DR --> DB
  SCH --> PS
```

### 디렉터리 개요

```text
app/
  domain/           도메인 모델·포트
  application/      유즈케이스 서비스
  infrastructure/   DB·설정·스케줄러
  presentation/     main, routers, templates
scripts/            스키마 적용 스크립트
디비정리.sql         MySQL DDL·주석 정리본
requirements.txt    Python 의존성
.env.example        환경 변수 예시
```

---

## 실행 메뉴얼

### 공통 준비

1. 저장소를 클론하거나 받은 디렉터리로 이동합니다.

2. 가상 환경을 쓰는 것을 권장합니다.

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. 패키지를 설치합니다.

   ```bash
   pip install -r requirements.txt
   ```

4. 저장소 **루트** 에 `.env` 를 만듭니다. `uvicorn` 실행 위치와 관계없이 `app/infrastructure/config.py` 기준 프로젝트 루트의 `.env` 를 읽습니다. 같은 이름이 실행 디렉터리에도 있으면 **루트 쪽 값이 우선**합니다. `DATABASE_USER` 가 `root` 가 아니면 `DATABASE_PASSWORD` 를 반드시 채웁니다. 비밀번호는 Git 에 올리지 않습니다.

5. 최초 한 번 관리 계정으로 스키마를 적용합니다. 대상 호스트와 DB 이름은 환경에 맞게 바꿉니다.

   ```bash
   python scripts/apply_schema.py --host 127.0.0.1 --port 3306 --user root --password "관리자비밀번호" --database finsight2
   ```

   이후 앱용 사용자에게 `finsight2` 에 대한 적절한 권한을 부여합니다.

---

### 서버 배포 실행

운영에서는 보통 재기동용 `--reload` 를 끕니다. 워커 수와 타임아웃은 트래픽에 맞게 조정합니다.

```bash
uvicorn app.presentation.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## 참고 링크

| 항목      | 경로 또는 URL 패턴         |
| --------- | -------------------------- |
| 헬스 확인 | `GET /health`              |
| OpenAPI   | `/docs`, `/openapi.json`   |
| 통계 JSON | `GET /api/dashboard/stats` |
