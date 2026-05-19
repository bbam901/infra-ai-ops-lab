import os
import sys
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load env variables from root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def query_prometheus(query):
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                data = result.get("data", {}).get("result", [])
                if data:
                    return float(data[0]["value"][1])
        return 0.0
    except Exception as e:
        print(f"[Warn] Error querying Prometheus for query '{query}': {e}")
        return 0.0

def query_loki():
    try:
        # Search app and nginx logs from the last 10 minutes
        query = '{job=~"app|nginx"}'
        end_ns = int(time.time() * 1e9)
        start_ns = end_ns - int(600 * 1e9)  # 10 minutes ago
        params = {
            "query": query,
            "start": start_ns,
            "end": end_ns,
            "limit": 50
        }
        response = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params, timeout=5)
        logs = []
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                streams = result.get("data", {}).get("result", [])
                for stream in streams:
                    for val in stream.get("values", []):
                        logs.append(val[1])
        return logs
    except Exception as e:
        print(f"[Warn] Error querying Loki: {e}")
        return []

def analyze_metrics_and_logs(metrics, logs):
    """
    Generate a rule-based diagnostic report if Gemini API key is missing.
    """
    total_reqs = metrics.get("total_requests", 0)
    error_rate = metrics.get("error_rate", 0.0)
    avg_latency = metrics.get("avg_latency", 0.0)
    cpu_usage = metrics.get("cpu_usage", 0.0)

    # Detect anomalies based on thresholds
    anomalies = []
    
    if error_rate > 5.0:
        anomalies.append(f"🚨 **HTTP 5xx 에러율 급증**: 전체 요청 중 {error_rate:.2f}%의 요청이 서버 에러로 인해 실패하고 있습니다.")
        
    if avg_latency > 1.0:
        anomalies.append(f"⏳ **평균 응답 시간 지연**: 평균 응답 속도가 {avg_latency:.3f}초로 임계치(1.0초)를 초과했습니다.")
        
    if cpu_usage > 70.0:
        anomalies.append(f"🔥 **컨테이너 CPU 사용률 위험**: FastAPI 앱 컨테이너의 CPU 사용률이 {cpu_usage:.2f}%에 도달했습니다.")

    # Rule-based logic for Cause, Remediation, Prevention
    if error_rate > 5.0:
        cause = "- FastAPI 애플리케이션 내 `/simulate/error` 호출에 따른 HTTP 500 에러 유발.\n- 시뮬레이션된 DB 커넥션 타임아웃 오류 로그 검출."
        remediation = "- FastAPI 애플리케이션 컨테이너의 스택 트레이스 분석 진행.\n- DB 커넥션 풀 고갈 여부 확인 및 세션 타임아웃 설정 조정."
        prevention = "- 서킷 브레이커 패턴 적용 및 DB 커넥션 풀 크기 최적화.\n- 에러 모니터링 임계치 기반 Prometheus 경고 알람 설정 연동."
    elif avg_latency > 1.0 or cpu_usage > 70.0:
        cause = "- `/simulate/latency` (비동기 대기) 혹은 `/simulate/cpu` (동기 math 연산) 호출로 인한 시스템 리소스 차단 및 지연 발생."
        remediation = "- FastAPI 동기 핸들러에서의 CPU Bound 블로킹 연산 배제 및 Celery 등 비동기 큐 이관.\n- Nginx Upstream 타임아웃 조율."
        prevention = "- Docker Compose 리소스 제한(Limits) 설정 조정.\n- 부하 발생 대비 오토스케일링 및 부하 분산 전략 설계 학습."
    else:
        cause = "- 모든 시스템 지표가 임계치 내에 있어 장애 원인이 식별되지 않았습니다."
        remediation = "- 정기 메트릭 및 로그 상시 모니터링 수행."
        prevention = "- 예방 점검을 위한 헬스 체크 자동화 주기 유지."

    # Filter out interesting logs (WARN/ERROR/EXCEPTION/HTTP 500)
    critical_logs = []
    for log in logs:
        log_lower = log.lower()
        if "error" in log_lower or "warning" in log_lower or "exception" in log_lower or "500" in log_lower:
            critical_logs.append(log)

    log_snippet = "\n".join([f"- `{log}`" for log in critical_logs[:15]]) if critical_logs else "*수집 기간 내 에러/경고 로그가 검출되지 않았습니다.*"

    report = f"""# 📊 장애 진단 리포트 (규칙 기반)
**생성 시각**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**상태**: {"⚠️ 경고 / 장애 진행 중" if len(anomalies) > 0 else "✅ 정상"}

---

## 1. 최근 5분 메트릭 요약
- **총 요청 수**: {total_reqs:.0f} 회
- **HTTP 5xx 에러율**: `{error_rate:.2f}%`
- **평균 응답 시간**: `{avg_latency:.4f}초`
- **컨테이너 CPU 사용률**: `{cpu_usage:.2f}%`

## 2. 탐지된 이상 징후
{chr(10).join(anomalies) if anomalies else "- 특이 사항 없음 (정상 상태)"}

## 3. 로그 분석
Loki 로그 스트림 검출 결과 (에러/경고성 로그 요약):
{log_snippet}

## 4. 원인 후보
{cause}

## 5. 권장 조치
{remediation}

## 6. 재발 방지 방안
{prevention}

## 7. 확인 근거
- **메트릭 데이터**: Prometheus를 통한 Nginx HTTP Status 5xx 카운팅 및 cAdvisor 컨테이너 리소스 모니터링 값
- **로그 데이터**: Loki 로그에 기록된 에러 스택 트레이스 및 Nginx 에러 로그
"""
    return report

def generate_ai_report(metrics, logs):
    """
    Generate an AI-powered diagnostic report using Gemini API.
    """
    try:
        from google import genai
        from google.genai import types
        
        # Initialize Google GenAI client
        # The SDK automatically uses GEMINI_API_KEY from environment
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
        당신은 뛰어난 인프라 운영 및 SRE 관점의 분석 엔진입니다.
        Nginx reverse proxy와 FastAPI App으로 구성된 Docker Compose 환경에서 발생한 장애를 진단하고 있습니다.
        
        Prometheus(최근 5분 메트릭) 및 Loki(최근 10분 로그)에서 수집한 데이터는 다음과 같습니다.
        
        --- 메트릭 정보 (Prometheus) ---
        - 총 요청 수: {metrics.get("total_requests")}
        - HTTP 5xx 에러율: {metrics.get("error_rate")}%
        - 평균 응답 시간: {metrics.get("avg_latency")} 초
        - 컨테이너 CPU 사용률: {metrics.get("cpu_usage")}%
        
        --- 로그 정보 (Loki) ---
        {chr(10).join(logs[:30])}
        
        --- 작성 태스크 ---
        위 데이터를 상세히 분석하여 채용담당자가 읽기 좋은 전문적하고 정직한 '장애 진단 리포트'를 한국어(Korean)로 작성해 주세요. 
        억지로 영어를 번역하지 말고, Docker Compose, FastAPI, Nginx, Prometheus, Grafana, Loki, Promtail, cAdvisor 등의 기술명은 영어 원문을 그대로 사용해 주세요.
        실무에서 직접 대규모 시스템을 다룬 것처럼 과장하지 말고, 이 실습 랩 환경에서 수집한 메트릭과 로그 데이터 분석에 근거하여 사실에 기반해 작성해 주세요.
        
        보고서는 반드시 다음 목차와 항목명을 대괄호나 볼드체 등의 형식을 활용해 포함해야 합니다:
        # 📊 장애 진단 리포트 (AI 생성)
        - **생성 시각**: [현재 날짜 및 시각 기입]
        - **상태**: [경고/장애 진행 중 또는 정상]
        
        ## 1. 최근 5분 메트릭 요약
        - **총 요청 수**: {metrics.get("total_requests")} 회
        - **HTTP 5xx 에러율**: {metrics.get("error_rate")}%
        - **평균 응답 시간**: {metrics.get("avg_latency")} 초
        - **컨테이너 CPU 사용률**: {metrics.get("cpu_usage")}%
        
        ## 2. 탐지된 이상 징후
        [에러율 급증, CPU 과부하, 지연 속도 증가 등 탐지된 이상 현상을 기술]
        
        ## 3. 로그 분석
        [Loki 로그 중 에러, 경고 로그나 스택 트레이스를 바탕으로 로그가 가리키는 실제 동작 오류 내용을 상세히 기술]
        
        ## 4. 원인 후보
        [수집된 메트릭과 로그의 연관 관계 분석을 통해 추정되는 근본 원인 후보들을 명확히 기술]
        
        ## 5. 권장 조치
        [즉각적 해결을 위한 긴급 대응 조치 방안 제시]
        
        ## 6. 재발 방지 방안
        [장기적으로 동일 장애의 재발을 방지할 수 있는 예방책 제안]
        
        ## 7. 확인 근거
        [메트릭 수치와 로그 파일 내용 중 이 진단에 결정적인 근거가 된 특정 데이터 라인을 요약 기입]
        
        중요: 목차와 항목명을 위의 요구사항에 맞게 완전히 일치시켜 한국어로 출력하고, 사실에만 기반해 구체적으로 작성해 주세요.
        """
        
        print("Sending incident context to Gemini API...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"[Error] Failed to generate AI report using Gemini: {e}")
        print("Falling back to Rule-Based report generator.")
        return analyze_metrics_and_logs(metrics, logs)

def main():
    print("==================================================")
    print("  AI Incident Reporter - Diagnostics Launching")
    print("==================================================")
    
    # 1. Fetch Prometheus metrics
    print("Querying Prometheus for incident metrics...")
    
    # Total requests
    total_reqs = query_prometheus("sum(increase(http_requests_total[5m]))")
    
    # HTTP 5xx requests
    error_reqs = query_prometheus("sum(increase(http_requests_total{status=~\"5..\"}[5m]))")
    error_rate = (error_reqs / total_reqs * 100) if total_reqs > 0 else 0.0
    
    # Avg request duration
    duration_sum = query_prometheus("sum(increase(http_request_duration_seconds_sum[5m]))")
    duration_count = query_prometheus("sum(increase(http_request_duration_seconds_count[5m]))")
    avg_latency = (duration_sum / duration_count) if duration_count > 0 else 0.0
    
    # Container CPU usage (cAdvisor)
    cpu_usage = query_prometheus("sum(rate(container_cpu_usage_seconds_total{container=\"app\"}[5m])) * 100")
    
    metrics = {
        "total_requests": total_reqs,
        "error_rate": error_rate,
        "avg_latency": avg_latency,
        "cpu_usage": cpu_usage
    }
    
    print(f"Metrics collected:")
    print(f"  - Requests: {total_reqs:.0f}")
    print(f"  - Error Rate: {error_rate:.2f}%")
    print(f"  - Avg Latency: {avg_latency:.4f}s")
    print(f"  - App Container CPU: {cpu_usage:.2f}%")

    # 2. Fetch Loki logs
    print("Querying Loki for error and app logs...")
    logs = query_loki()
    print(f"Collected {len(logs)} log lines from Loki.")

    # 3. Generate Report (AI or Rule-based)
    if GEMINI_API_KEY:
        print("Gemini API Key detected. Initializing AI Diagnosis...")
        report_content = generate_ai_report(metrics, logs)
    else:
        print("Gemini API Key NOT detected. Generating Rule-Based report...")
        report_content = analyze_metrics_and_logs(metrics, logs)

    # 4. Save report
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"reports/incident_report_{timestamp}.md"
    
    try:
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report_content)
        print("==================================================")
        print(f"  Report generated successfully: {report_filename}")
        print("==================================================")
    except Exception as e:
        print(f"[Error] Failed to write report file: {e}")

if __name__ == "__main__":
    main()
