# 📊 장애 진단 리포트 (예시)
- **생성 시각**: 2026-05-20 03:15:30
- **상태**: ⚠️ 경고 / 장애 진행 중 (임계치 초과)

---

## 1. 최근 5분 메트릭 요약
- **총 요청 수**: 248 회
- **HTTP 5xx 에러율**: `18.54%`
- **평균 응답 시간**: `1.2405초`
- **컨테이너 CPU 사용률**: `82.40%`

## 2. 탐지된 이상 징후
- 🚨 **HTTP 5xx 에러율 급증**: 정상 범위를 초과하여 전체 요청의 18.54%가 서버 에러(HTTP 500)로 응답하고 있습니다.
- ⏳ **평균 응답 시간 지연**: 임계값(1.0초)을 초과한 1.24초의 지연 시간이 발생했습니다.
- 🔥 **컨테이너 CPU 사용률 위험**: FastAPI 애플리케이션 컨테이너의 CPU 부하가 82.40%로 치솟았습니다.

## 3. 로그 분석
Loki 로그 스트림 검출 결과, 다음 에러 로그 및 경고 라인이 확인되었습니다:
- `[infra-ai-ops-app] ERROR: Simulating an internal server error (HTTP 500) due to simulated DB failure | error_type: DatabaseConnectionTimeout`
- `[infra-ai-ops-app] WARNING: Simulating high CPU load | component: cpu_simulator`
- `[nginx] "GET /simulate/error HTTP/1.1" 500 55 "-" "python-requests/2.31.0"`
- `[nginx] "GET /simulate/cpu HTTP/1.1" 200 120 "-" "python-requests/2.31.0"`

## 4. 원인 후보
1. **API 호출에 의한 강제 서버 에러 유입**:
   - `chaos_injector.py`를 통해 `/simulate/error` 엔드포인트에 대한 집중 호출이 수행되었으며, 이로 인해 FastAPI 내부에서 예외가 발생하고 Nginx가 500 에러를 반환했습니다.
2. **동기식 블로킹 연산으로 인한 CPU 병목 및 대기 시간 증가**:
   - `/simulate/cpu` 엔드포인트 호출 시 실행되는 CPU Bound 루프 연산이 메인 스레드를 장기 점유하여 전체 요청에 대한 평균 응답 시간이 지연된 것으로 보입니다.

## 5. 권장 조치
- **단기 조치**:
  - FastAPI 및 Nginx 컨테이너 리부팅을 통한 시스템 일시 안정화.
  - 에러를 유발하는 비정상 트래픽 발생 소스(시뮬레이터 스크립트 등) 차단.
- **장기 조치**:
  - 데이터베이스 커넥션 타임아웃 예외 처리를 정교화하여 연결 실패 시 즉각 실패 응답(Fast-fail)을 제공하거나 서킷 브레이커를 작동시킴.

## 6. 재발 방지 방안
- CPU 연산이 집중되는 무거운 로직은 동기 API 내부에서 직접 실행하지 않고 Celery, Redis 등을 활용해 백그라운드 비동기 태스크로 이관.
- Docker Compose 내 컨테이너 스펙에 CPU/메모리 하드웨어 제한(Limit/Reservations) 설정을 공식 적용하여 단일 서비스 장애가 호스트 전체로 전파되지 않도록 고립화.

## 7. 확인 근거
- **메트릭 데이터**: Prometheus에서 `sum(increase(http_requests_total{status=~"5.."}[5m]))` 쿼리를 통해 에러 수치 급증 확인 및 cAdvisor를 통한 컨테이너 CPU 지표 상승 교차 검증.
- **로그 데이터**: Loki에서 수집된 FastAPI 컨테이너 로그의 `DatabaseConnectionTimeout` 및 Nginx Access Log의 `status=500` 매칭 내역.
