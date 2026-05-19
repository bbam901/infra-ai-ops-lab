# 📖 인프라 장애 대응 런북 (Alert Runbook)

본 문서는 Prometheus Alertmanager로부터 발생한 경보(Alert)별 진단 방법 및 트러블슈팅 대응 절차를 정리한 주니어 인프라 엔지니어용 런북입니다.

---

## 1. 경보 목록 및 대응 절차

### 🚨 [Critical] High5xxErrorRate
- **경보 조건**: 최근 1분 동안 FastAPI 어플리케이션 호출 전체 중 HTTP 5xx 에러율이 10% 이상인 경우 발생
- **잠재적 영향**: 사용자 서비스 요청 실패, API 연동 에러 발생, 비즈니스 신뢰도 하락

#### 🛠️ 대응 절차
1. **중앙 로그 확인 (Loki)**:
   - Grafana 대시보드(`http://localhost:3050`)의 **"애플리케이션 및 인프라 로그 스트림"** 패널을 활용해 에러 시점 주변의 FastAPI 에러 로그(Exception stack trace)를 분석합니다.
2. **컨테이너 실시간 로그 조회**:
   - 터미널을 통해 실시간 컨테이너 표준 출력 로그를 확인합니다.
     ```bash
     docker compose logs -f app
     ```
3. **Nginx 프록시 상태 점검**:
   - Nginx가 FastAPI 어플리케이션으로 정상 중계하고 있는지 확인합니다. Nginx 에러 로그에서 `502 Bad Gateway` 혹은 `504 Gateway Timeout` 관련 이력이 없는지 체크합니다.
     ```bash
     docker compose logs nginx
     ```
4. **장애 유입 유무 판별**:
   - `chaos_injector.py --mode error` 등의 테스트 스크립트가 실행 중인지 확인하고, 의도된 시뮬레이션인 경우 시뮬레이션 프로세스를 중단하고 지표가 정상 복구되는지 관찰합니다.

---

### ⚠️ [Warning] HighContainerCPUUsage
- **경보 조건**: cAdvisor 감지 기준 컨테이너 CPU 사용률이 80%를 초과하는 경우 발생
- **잠재적 영향**: 서비스 응답 속도 지연(Latency 증가), 다른 컨테이너 자원 고갈 현상 초래

#### 🛠️ 대응 절차
1. **리소스 상태 모니터링**:
   - 터미널에서 `docker stats` 명령을 수행하여 실시간으로 가장 높은 CPU 자원을 점유하고 있는 개별 컨테이너를 식별합니다.
     ```bash
     docker stats
     ```
2. **cAdvisor 및 Grafana 시각화 점검**:
   - cAdvisor 대시보드(`http://localhost:8080`) 및 Grafana 대시보드의 **"컨테이너 CPU 사용률 합계 (%)"** 추이를 확인합니다.
3. **어플리케이션 지연 점검**:
   - FastAPI `/docs` 등의 응답 지연을 확인하거나, `chaos_injector.py --mode latency` 또는 `mixed`에 의해 CPU 스트레스 부하가 강제 유입되었는지 모니터링합니다. 시뮬레이션 종료 이후 CPU 점유율이 서서히 하락하는지 2~3분간 검증합니다.

---

## 2. 모니터링 시스템 아키텍처 연동 확인
- 모든 경보는 Prometheus(`http://localhost:9090`)에서 평가되어 Alertmanager(`http://localhost:9093`)로 전달됩니다.
- Alertmanager 웹 UI의 **Alerts** 페이지에서 활성(Active)/지연(Silenced) 상태를 손쉽게 확인할 수 있습니다.
