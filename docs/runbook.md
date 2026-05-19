# 📖 인프라 장애 대응 런북 (Alert Runbook)

본 문서는 실무 인프라 운영 환경을 가정하여 모니터링 시스템에서 경보가 발생했을 때 신속하게 원인을 분석하고 장애를 조치하기 위한 상세 절차를 담고 있습니다.

---

## 1. 장애 대응 기본 절차 (Incident Response Workflow)

장애가 감지되면 다음 4단계에 걸쳐 대응 프로세스를 수행합니다.

```
[1단계: 장애 감지 및 확인] ➔ [2단계: 원인 분석 및 진단] ➔ [3단계: 긴급 조치 및 복구] ➔ [4단계: 사후 보고 및 재발방지]
```

1. **1단계: 장애 감지 및 확인**
   - Alertmanager 웹 UI(`http://localhost:9093`) 및 Prometheus Alert 탭에서 활성화된 경보를 식별하고 등급(Critical / Warning)을 판별합니다.
2. **2단계: 원인 분석 및 진단**
   - 아래의 상황별 확인 순서에 따라 Grafana 대시보드 및 컨테이너 로그, 시계열 지표를 분석합니다.
3. **3단계: 긴급 조치 및 복구**
   - 트래픽 제어, 컨테이너 재시작, 리소스 증설 등 적절한 조치를 통해 정상 상태로 복구시킵니다.
4. **4단계: 사후 보고 및 재발방지**
   - 장애 진단 리포트 생성 스크립트를 수행하고 사후 검토(Post-Mortem)를 진행하여 예방 체크리스트를 점검합니다.

---

## 2. 상황별 진단 및 확인 순서

### A. HTTP 5xx 에러 증가 시
1. **Prometheus 경보 확인**: `High5xxErrorRate` 경보가 Firing 상태인지 확인합니다.
2. **Nginx 인그레스 로그 검사**:
   - Nginx가 수신한 요청의 상태 코드와 백엔드 포워딩 성공 여부를 봅니다.
     ```bash
     docker compose logs nginx | grep -E "500|502|503|504"
     ```
3. **FastAPI 애플리케이션 추적**:
   - FastAPI가 발생시킨 예외 Stack Trace를 Loki 또는 컨테이너 표준 출력을 통해 수집합니다.
     ```bash
     docker compose logs app --tail=100
     ```

### B. 서비스 응답 지연(Latency) 증가 시
1. **애플리케이션 응답 속도 메트릭 확인**:
   - Prometheus에서 각 API 핸들러별 지연 시간 지표(`http_request_duration_seconds_sum` / `http_request_duration_seconds_count`)를 조회합니다.
2. **컨테이너 자원 고하중 상태 검사**:
   - 아래 CPU 및 메모리 고하중 점검 로직으로 연계하여 애플리케이션 응답 병목이 리소스 고갈 때문인지 판별합니다.
3. **인프라 네트워킹 점검**:
   - Docker Bridge 네트워크 내부 병목 유무 및 외부 API 호출 지연 여부를 프로깅합니다.

### C. 컨테이너 CPU/메모리 사용률 증가 시
1. **경보 식별**: Alertmanager에서 `HighContainerCPUUsage` 경보 대상 컨테이너 ID를 파악합니다.
2. **실시간 자원 사용량 프로파일링**:
   - CLI 환경에서 즉시 `docker stats`를 구동해 메모리/CPU 점유율 상위 프로세스를 추적합니다.
     ```bash
     docker stats
     ```
3. **cAdvisor 웹 UI 조회**:
   - `http://localhost:8080`에 접속하여 각 서브 컨테이너 cgroup 서브시스템 레벨의 상세 리소스 점유 상태를 시각적으로 추적합니다.

---

## 3. 관찰 가능성(Observability) 디버깅 쿼리 가이드

### 📊 Prometheus 주요 분석 쿼리 (PromQL)
* **전체 컨테이너 CPU 사용률 합계 (%)**:
  ```promql
  sum(rate(container_cpu_usage_seconds_total[1m])) * 100
  ```
* **전체 컨테이너 메모리 사용량 합계 (MB)**:
  ```promql
  sum(container_memory_usage_bytes) / 1024 / 1024
  ```
* **API 핸들러별 초당 요청량 (RPS)**:
  ```promql
  sum(rate(http_requests_total[1m])) by (handler)
  ```
* **초당 HTTP 5xx 에러 발생 빈도**:
  ```promql
  sum(rate(http_requests_total{status=~"5.."}[1m])) by (handler)
  ```

### 📝 Grafana Loki 주요 로그 분석 쿼리 (LogQL)
* **FastAPI 어플리케이션 에러 로그 필터링**:
  ```logql
  {container="app"} |= "ERROR"
  ```
* **Nginx 프록시 에러 로그(Bad Gateway 등) 필터링**:
  ```logql
  {container="nginx"} |= "error"
  ```
* **애플리케이션 스택 트레이스 추적**:
  ```logql
  {container="app"} |~ "Traceback|Exception"
  ```

---

## 4. Alertmanager 알림 확인 방법
1. 브라우저에서 Alertmanager 웹 UI(`http://localhost:9093`)에 접속합니다.
2. 상단 메뉴의 **Alerts** 항목을 클릭해 현재 Firing 및 Pending 상태인 모든 알림 규칙 목록을 확인합니다.
3. 특정 장애 경보의 발송을 일시 유예하려면 알림 옆의 **Silence** 버튼을 눌러 지정된 시간 동안 무음 처리(Mute)를 지정할 수 있습니다.
4. 검색창에서 라벨 필터링(예: `{alertname="High5xxErrorRate"}`)을 적용하여 특정 경보 정보만 필터링 조회합니다.

---

## 5. 장애 진단 리포트 자동 생성 프로세스
본 프로젝트는 장애 발생 후 포스트모템 리포트를 코드 수준에서 자동화하기 위해 자동 분석 및 AI 프롬프트 스크립트를 내장하고 있습니다.

1. **스크립트 구동**:
   ```bash
   python scripts/ai_incident_reporter.py
   ```
2. **동작 원리**:
   - Prometheus API를 호출해 최근 에러율 및 자원 지표를 판독합니다.
   - Loki API를 조회해 에러 스택 트레이스를 자동으로 덤프합니다.
   - `.env`에 `GEMINI_API_KEY`가 제공된 경우 Gemini 2.5 Flash 모델이 지표와 에러 추이를 바탕으로 종합 원인 분석과 조치 방안을 한글 마크다운 보고서로 출력합니다. (API Key가 없거나 호출이 실패한 경우 룰 기반 알고리즘을 사용한 마크다운 보고서가 대체 작동합니다.)
3. **산출물 확인**:
   - `reports/` 폴더 내에 `incident_report_YYYYMMDD_HHMMSS.md` 형태로 타임스탬프와 함께 자동 저장됩니다.

---

## 6. 재발 방지 체크리스트 (Post-Mortem Checklist)

장애가 조치 및 종결된 후, 재발 방지를 위해 다음의 체크리스트를 정기적으로 수행합니다.

- [ ] **메트릭 임계치 튜닝**: 발생한 Alert의 임계치와 평가 주기가 실제 운영 장애 상황을 적시에 대변하도록 적절히 튜닝되었는가?
- [ ] **런북 최신화**: 이번 장애 처리 과정에서 발견한 새로운 트러블슈팅 패턴이 런북에 반영되었는가?
- [ ] **리소스 한도 재조정**: 컨테이너 CPU/메모리 부하가 빈번할 경우 `docker-compose.yml` 리소스 한도(Limits) 상향을 고려했는가?
- [ ] **로그 파이프라인 무결성**: 어플리케이션의 신규 에러 유형이 JSON 구조를 깨뜨리지 않고 Loki에 잘 전달되는가?
- [ ] **룰 기반 폴백 검증**: Gemini API 미연동 상태에서도 백업 보고서가 최신 장애 지표를 올바르게 명세하는가?
