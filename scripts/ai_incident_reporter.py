import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv


load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def query_prometheus(query):
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("status") != "success":
            return 0.0

        data = result.get("data", {}).get("result", [])
        if not data:
            return 0.0

        return float(data[0]["value"][1])
    except Exception as exc:
        print(f"[Warn] Prometheus query failed: {query} ({exc})")
        return 0.0


def query_loki():
    try:
        end_ns = int(time.time() * 1e9)
        start_ns = end_ns - int(600 * 1e9)
        params = {
            "query": '{job=~".+"}',
            "start": start_ns,
            "end": end_ns,
            "limit": 50,
        }
        response = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params=params,
            timeout=5,
        )
        response.raise_for_status()

        logs = []
        result = response.json()
        if result.get("status") == "success":
            for stream in result.get("data", {}).get("result", []):
                for value in stream.get("values", []):
                    logs.append(value[1])
        return logs
    except Exception as exc:
        print(f"[Warn] Loki query failed: {exc}")
        return []


def build_rule_based_report(metrics, logs):
    total_reqs = metrics.get("total_requests", 0.0)
    error_rate = metrics.get("error_rate", 0.0)
    avg_latency = metrics.get("avg_latency", 0.0)
    cpu_usage = metrics.get("cpu_usage", 0.0)

    anomalies = []
    if error_rate > 5.0:
        anomalies.append(
            f"- HTTP 5xx 에러율이 {error_rate:.2f}%로 증가했습니다."
        )
    if avg_latency > 1.0:
        anomalies.append(
            f"- 평균 응답 시간이 {avg_latency:.3f}초로 증가했습니다."
        )
    if cpu_usage > 70.0:
        anomalies.append(
            f"- cAdvisor 기준 컨테이너 CPU 사용률 합계가 {cpu_usage:.2f}%로 높게 측정되었습니다."
        )
    if not anomalies:
        anomalies.append("- 현재 기준으로 큰 이상 징후는 확인되지 않았습니다.")

    interesting_logs = []
    for log in logs:
        lowered = log.lower()
        if any(keyword in lowered for keyword in ["error", "warning", "exception", "500"]):
            interesting_logs.append(log)

    if interesting_logs:
        log_summary = "\n".join(f"- `{log}`" for log in interesting_logs[:15])
    else:
        log_summary = "- 최근 수집 구간에서 주요 에러/경고 로그가 확인되지 않았습니다."

    if error_rate > 5.0:
        cause = (
            "- `/simulate/error` endpoint 호출로 HTTP 500 에러가 반복 발생했을 가능성이 큽니다.\n"
            "- 로그에 `DatabaseConnectionTimeout` 유형의 모의 오류가 기록되어 있는지 확인해야 합니다."
        )
        remediation = (
            "- 장애 트래픽 발생 여부를 먼저 확인합니다.\n"
            "- FastAPI 로그와 Nginx access log에서 5xx 요청 경로를 확인합니다.\n"
            "- 실제 환경이라면 DB 연결 상태, connection timeout, connection pool 설정을 함께 점검합니다."
        )
        prevention = (
            "- 5xx 에러율 기준 Alert Rule을 운영 기준에 맞게 조정합니다.\n"
            "- 장애 발생 시점 전후의 로그와 메트릭을 자동으로 모으는 절차를 보강합니다."
        )
    elif avg_latency > 1.0 or cpu_usage > 70.0:
        cause = (
            "- `/simulate/latency` 또는 `/simulate/cpu` 호출로 응답 지연이나 CPU 부하가 발생했을 가능성이 있습니다.\n"
            "- CPU 사용률은 cAdvisor의 컨테이너 CPU 메트릭 합계 기준으로 계산했습니다."
        )
        remediation = (
            "- 지연이 발생한 endpoint와 요청 시간을 확인합니다.\n"
            "- CPU bound 작업이 FastAPI 요청 처리 흐름을 막고 있는지 확인합니다.\n"
            "- 필요하면 비동기 작업 큐나 background job 분리를 검토합니다."
        )
        prevention = (
            "- CPU 사용률과 응답 지연에 대한 Alert Rule을 운영 기준에 맞게 조정합니다.\n"
            "- 부하 테스트 시나리오를 더 세분화해 병목 구간을 확인합니다."
        )
    else:
        cause = "- 현재 메트릭 기준으로 명확한 장애 원인은 확인되지 않았습니다."
        remediation = "- Prometheus, Grafana, Loki에서 최근 요청과 로그를 계속 확인합니다."
        prevention = "- 정상 상태 기준치를 더 수집해 이후 장애 판단 기준으로 활용합니다."

    return f"""# 장애 진단 리포트

**생성 시각**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**상태**: {"경고 / 장애 상황 감지" if len(anomalies) > 1 or "이상 징후" not in anomalies[0] else "정상"}

---

## 1. 최근 5분 메트릭 요약

- **총 요청 수**: {total_reqs:.0f}회
- **HTTP 5xx 에러율**: `{error_rate:.2f}%`
- **평균 응답 시간**: `{avg_latency:.4f}초`
- **컨테이너 CPU 사용률 합계**: `{cpu_usage:.2f}%`

## 2. 탐지된 이상 징후

{chr(10).join(anomalies)}

## 3. 로그 분석

{log_summary}

## 4. 원인 후보

{cause}

## 5. 권장 조치

{remediation}

## 6. 재발 방지 방안

{prevention}

## 7. 확인 근거

- Prometheus: `http_requests_total`, `http_request_duration_seconds_*`, `container_cpu_usage_seconds_total`
- Loki: 최근 10분 로그 중 error, warning, exception, 500 키워드가 포함된 로그
- CPU 사용률은 특정 app label이 아닌 cAdvisor 컨테이너 CPU 메트릭 합계를 기준으로 계산했습니다.
"""


def generate_ai_report(metrics, logs):
    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
다음은 Docker Compose 기반 로컬 인프라 실습 환경에서 수집한 장애 데이터입니다.
실무에서 사용했다고 과장하지 말고, 수집된 메트릭과 로그에 근거해 한국어 장애 진단 리포트를 작성해 주세요.
기술명은 Docker Compose, FastAPI, Nginx, Prometheus, Grafana, Loki, Promtail, cAdvisor처럼 영어 원문을 유지해 주세요.

메트릭:
- 총 요청 수: {metrics.get("total_requests")}
- HTTP 5xx 에러율: {metrics.get("error_rate")}%
- 평균 응답 시간: {metrics.get("avg_latency")}초
- 컨테이너 CPU 사용률 합계: {metrics.get("cpu_usage")}%

로그:
{chr(10).join(logs[:30])}

포함할 항목:
- 장애 요약
- 최근 5분 메트릭 요약
- 탐지된 이상 징후
- 로그 분석
- 원인 후보
- 권장 조치
- 재발 방지 방안
- 확인 근거
"""
        print("Sending incident context to Gemini API...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as exc:
        print(f"[Warn] Gemini report generation failed: {exc}")
        print("Falling back to rule-based report generator.")
        return build_rule_based_report(metrics, logs)


def main():
    print("==================================================")
    print("  Incident Reporter - Diagnostics Launching")
    print("==================================================")

    print("Querying Prometheus for incident metrics...")

    total_reqs = query_prometheus("sum(increase(http_requests_total[5m]))")
    error_reqs = query_prometheus('sum(increase(http_requests_total{status=~"5.."}[5m]))')
    error_rate = (error_reqs / total_reqs * 100) if total_reqs > 0 else 0.0

    duration_sum = query_prometheus("sum(increase(http_request_duration_seconds_sum[5m]))")
    duration_count = query_prometheus("sum(increase(http_request_duration_seconds_count[5m]))")
    avg_latency = (duration_sum / duration_count) if duration_count > 0 else 0.0

    # cAdvisor in Docker Desktop often does not expose a stable app/container label.
    # Use a label-independent total so the report does not show 0.00% due to label mismatch.
    cpu_usage = query_prometheus('sum(rate(container_cpu_usage_seconds_total{id!="/"}[1m])) * 100')

    metrics = {
        "total_requests": total_reqs,
        "error_rate": error_rate,
        "avg_latency": avg_latency,
        "cpu_usage": cpu_usage,
    }

    print("Metrics collected:")
    print(f"  - Requests: {total_reqs:.0f}")
    print(f"  - Error Rate: {error_rate:.2f}%")
    print(f"  - Avg Latency: {avg_latency:.4f}s")
    print(f"  - Container CPU Total: {cpu_usage:.2f}%")

    print("Querying Loki for recent logs...")
    logs = query_loki()
    print(f"Collected {len(logs)} log lines from Loki.")

    if GEMINI_API_KEY:
        print("Gemini API key detected. Generating AI report...")
        report_content = generate_ai_report(metrics, logs)
    else:
        print("Gemini API key not detected. Generating rule-based report...")
        report_content = build_rule_based_report(metrics, logs)

    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"reports/incident_report_{timestamp}.md"

    with open(report_filename, "w", encoding="utf-8") as file:
        file.write(report_content)

    print("==================================================")
    print(f"  Report generated successfully: {report_filename}")
    print("==================================================")


if __name__ == "__main__":
    main()
