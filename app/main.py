import time
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pythonjsonlogger import jsonlogger

# 1. Setup Structured JSON Logging
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    json_ensure_ascii=False
)
log_handler.setFormatter(formatter)

logger = logging.getLogger("infra-ai-ops-app")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# Prevent log duplication
logger.propagate = False

app = FastAPI(title="Infra AI-Ops Lab FastAPI App")

# 2. Setup Prometheus Instrumentator
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=False,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)
instrumentator.instrument(app).expose(app, endpoint="/metrics")

# 3. App Endpoints
@app.get("/")
def read_root():
    logger.info("Handling root endpoint request", extra={"path": "/"})
    return {"message": "Welcome to the Infra AI-Ops Lab FastAPI App!"}

@app.get("/health")
def health_check():
    logger.info("Handling health check request", extra={"path": "/health"})
    return {"status": "healthy"}

@app.get("/simulate/error")
def simulate_error():
    logger.error(
        "Simulating an internal server error (HTTP 500) due to simulated DB failure",
        extra={"error_type": "DatabaseConnectionTimeout", "component": "database"}
    )
    raise HTTPException(
        status_code=500,
        detail="Simulated internal server error: Database connection timed out."
    )

@app.get("/simulate/latency")
async def simulate_latency():
    delay = 3.0
    logger.warning(
        f"Simulating latency. Sleeping for {delay} seconds",
        extra={"simulated_delay_seconds": delay, "component": "external_api"}
    )
    await asyncio.sleep(delay)
    return {"message": f"Successfully waited {delay} seconds."}

@app.get("/simulate/cpu")
def simulate_cpu():
    start_time = time.time()
    logger.warning("Simulating high CPU load", extra={"component": "cpu_simulator"})
    
    # Run a busy loop for about 1.5 seconds to burn CPU cycles
    duration = 1.5
    count = 0
    while time.time() - start_time < duration:
        # Perform some useless CPU-bound operations
        _ = 999999 * 999999
        count += 1
        
    execution_time = time.time() - start_time
    logger.info(
        "CPU simulation finished",
        extra={"iterations": count, "execution_time_seconds": execution_time}
    )
    return {
        "message": "High CPU load simulation completed.",
        "iterations": count,
        "execution_time_seconds": execution_time
    }
