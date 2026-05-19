# 🛠️ 인프라 운영 트러블슈팅 가이드 (Troubleshooting Guide)

본 문서는 실무 모니터링 시스템 구축 및 테스트 시 흔히 발생하는 인프라성 장애 및 설정 오류에 대한 대처 요령을 정리한 주니어 엔지니어용 트러블슈팅 가이드입니다.

---

## 1. 파이썬 환경 및 의존성 문제

### 💡 `pip` 명령어가 동작하지 않거나 패키지 버전이 꼬일 때
* **증상**: 터미널에 `pip` 명령 실행 시 명령을 찾을 수 없거나 버전 충돌 오류가 발생합니다.
* **해결 방안**:
  - 파이썬 실행 바이너리와 직접 매핑된 모듈 실행 옵션을 사용하여 라이브러리를 설치합니다.
    ```bash
    python -m pip install -r scripts/requirements.txt
    ```
  - 가상환경(venv)을 활성화하여 전역 패키지 영향도를 원천 차단하는 것을 적극 권장합니다.
    ```bash
    python -m venv venv
    .\venv\Scripts\activate   # Windows PowerShell
    pip install -r scripts/requirements.txt
    ```

---

## 2. Docker 및 볼륨 권한 관련 이슈

### 💡 Loki 컨테이너 기동 실패: `mkdir /tmp/loki/chunks: permission denied`
* **원인**: Loki 컨테이너 내부의 비루트(Non-root) 실행 계정이 호스트의 임시 스토리지 마운트 디렉터리에 쓰기 작업을 수행할 권한이 없어서 발생합니다.
* **해결 방안**:
  - `loki-config.yml`의 모든 로컬 스토리지 루트 경로를 `/tmp/loki`에서 독립 볼륨 경로인 `/loki` 하위로 일괄 수정하고, `docker-compose.yml`에서 해당 경로를 Named Volume (`loki-data`)에 마운트하여 컨테이너 스토리지 격리 권한 문제를 원천 해결합니다.

---

## 3. Grafana 대시보드 관리 이슈

### 💡 Grafana UI에서 대시보드 삭제 시도 시 `provisioned dashboard cannot be deleted` 발생
* **원인**: 본 시스템의 대시보드는 코드 기반 인프라(IaC) 원칙에 따라 파일 프로비저닝(File Provisioning) 방식으로 마운트 및 배포되어 있으므로 UI상에서의 임의 삭제가 원천 차단됩니다.
* **해결 방안**:
  - 대시보드의 영구적인 수정을 원할 때는 호스트 상의 설정 파일인 `grafana/provisioning/dashboards/dashboard.json`을 직접 편집하고, 아래 대시보드 갱신 프로세스를 이행해야 합니다.

### 💡 Grafana 대시보드 JSON 파일을 수정하고 재시작했으나 화면에 반영되지 않을 때
* **원인**: Grafana가 기존 대시보드 정보(UID 및 버전)를 DB 세션 캐시에 보관하고 있어 새 파일 로드를 감지하지 못하는 현상입니다.
* **해결 방안**:
  1. `dashboard.json` 내부의 `uid`를 기존과 다른 새 문자열(예: `infra-ai-ops-v6` 등)로 바꿉니다.
  2. `version` 번호를 이전 값보다 1 이상 증량합니다.
  3. `docker-compose.yml`에 프로비저닝 최상위 디렉터리(`./grafana/provisioning:/etc/grafana/provisioning:ro`)가 올바르게 바인딩되었는지 검토합니다.
  4. 터미널에서 다음 명령을 실행해 서비스를 재기동하면 새로운 대시보드가 정상 주입됩니다.
     ```bash
     docker compose restart grafana
     ```

---

## 4. 로그 수집 및 탐색기(Explore) 쿼리 이슈

### 💡 Grafana Loki Explore에서 쿼리 작성 시 로그가 보이지 않거나 오류가 날 때
* **주의사항**:
  - Loki 쿼리(LogQL) 작성 시 중괄호 안에 들어가는 스트림 셀렉터 키(예: `container`) 및 값(예: `app`)은 **반드시 큰따옴표(`"`)를 사용**해야 하며, 대소문자를 엄격하게 구분합니다.
    - **올바른 쿼리**: `{container="app"}`
    - **잘못된 쿼리**: `{container='app'}` (홑따옴표 사용 불가)
  - 파이프라인에서 정적 라벨이 올바르게 수집되도록 `promtail-config.yml`의 `relabel_configs` 설정에서 타겟 라벨 파싱 룰이 유효한지 확인합니다.

---

## 5. Windows Docker Desktop 실행 특이사항

### 💡 Windows 환경에서 리소스 모니터링 지표가 `No data`로 보일 때
* **원인**: WSL2 백엔드 기반의 Windows Docker Desktop 환경에서는 리눅스 커널 cgroup 경로 구조 차이로 인해 cAdvisor가 개별 컨테이너 레벨의 `container` 또는 `name` 라벨 필터를 매핑하지 못할 수 있습니다.
* **해결 방안**:
  - 특정 개별 컨테이너를 필터링하는 쿼리 대신 전체 리소스의 누적 사용률을 추적하는 `sum(rate(container_cpu_usage_seconds_total[1m])) * 100` 및 `sum(container_memory_usage_bytes)` 쿼리를 활용하도록 구성합니다.
  - Windows의 호스트 포트 충돌(예: 80, 3000 포트가 타 프로세스나 IIS에 의해 사용 중인 경우) 상태를 점검하고, `.env` 및 `docker-compose.yml`에서 각각 `8001:8000`, `3050:3000` 처럼 포트 맵 우회 구성을 검토합니다.

---

## 6. 서비스 중계 및 상태 이슈

### 💡 Nginx 게이트웨이 접속 시 `502 Bad Gateway` 에러가 발생할 때
* **원인**: 프록시 대상인 FastAPI `app` 컨테이너가 정상적으로 가동되어 포트가 리스닝 중이지 않거나 Nginx의 업스트림 도메인 해석에 문제가 생겼을 때 발생합니다.
* **해결 방안**:
  - FastAPI 컨테이너의 기동 상태를 점검합니다.
    ```bash
    docker compose ps
    ```
  - 컨테이너가 비정상 종료(Exited) 상태인 경우 내부 로그를 추적합니다.
    ```bash
    docker compose logs app
    ```
  - Docker Compose 네트워크 설정 상에서 Nginx와 FastAPI가 동일한 `monitoring-network` 브리지에 명확하게 연결되어 있는지 `docker-compose.yml` 명세를 교차 체크합니다.

---

## 7. 모니터링 및 경보 설정 이슈

### 💡 Prometheus 대상(Targets) 목록에 메트릭 상태가 `Down`이거나 안 보일 때
* **원인**: Prometheus가 타겟 컨테이너의 수집 포트(`app:8000`, `cadvisor:8080`)로 네트워크 패킷을 도달시킬 수 없을 때 발생합니다.
* **해결 방안**:
  - `prometheus.yml` 스크랩 설정 내 `targets` 목록의 도메인(컨테이너 서비스명)과 포트 번호가 올바른지 확인합니다.
  - 각 컨테이너 내부에서 메트릭이 실제로 서빙되는 경로(예: `/metrics`)로 HTTP 호출이 가능한지 검증합니다.

### 💡 Alertmanager 알림창에 경보가 활성화되지 않을 때
* **원인**: Prometheus의 경보 규칙 평가(Evaluation)가 이루어지지 않았거나 Alertmanager로 전달하는 엔드포인트 바인딩이 누락된 경우입니다.
* **해결 방안**:
  - [Prometheus Targets](http://localhost:9090/targets) 및 [Alerts 탭](http://localhost:9090/alerts)에 진입하여 `High5xxErrorRate` 등의 알림 규칙이 정상 로드되어 있는지 확인합니다.
  - `prometheus.yml`의 `rule_files` 및 `alerting.alertmanagers`의 호스트 정보가 `alertmanager:9093`으로 정확히 입력되었는지 검수합니다.
