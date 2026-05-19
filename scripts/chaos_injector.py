import time
import random
import argparse
import requests

TARGET_URL = "http://localhost"  # Hits Nginx reverse proxy

def send_request(endpoint, mode_name):
    url = f"{TARGET_URL}{endpoint}"
    try:
        start_time = time.time()
        response = requests.get(url, timeout=5)
        duration = time.time() - start_time
        print(f"[{mode_name.upper()}] GET {endpoint} | Status: {response.status_code} | Time: {duration:.3f}s")
    except requests.exceptions.RequestException as e:
        print(f"[{mode_name.upper()}] GET {endpoint} | Failed: {e}")

def run_normal(duration):
    print(f"Starting normal traffic simulation for {duration}s...")
    start = time.time()
    endpoints = ["/", "/health"]
    while time.time() - start < duration:
        endpoint = random.choice(endpoints)
        send_request(endpoint, "normal")
        time.sleep(random.uniform(0.1, 0.5))

def run_error(duration):
    print(f"Starting error injection simulation for {duration}s...")
    start = time.time()
    while time.time() - start < duration:
        # Simulate some normal traffic mixed with heavy error injection
        if random.random() < 0.8:
            send_request("/simulate/error", "error")
        else:
            send_request("/", "normal")
        time.sleep(random.uniform(0.1, 0.4))

def run_latency(duration):
    print(f"Starting latency/CPU load injection simulation for {duration}s...")
    start = time.time()
    while time.time() - start < duration:
        # Alternates between latency endpoint and cpu simulator endpoint
        endpoint = random.choice(["/simulate/latency", "/simulate/cpu"])
        send_request(endpoint, "latency")
        time.sleep(random.uniform(0.2, 0.5))

def run_mixed(duration):
    print(f"Starting mixed incident traffic simulation for {duration}s...")
    start = time.time()
    endpoints = ["/", "/health", "/simulate/error", "/simulate/latency", "/simulate/cpu"]
    weights = [0.4, 0.2, 0.2, 0.1, 0.1]  # 60% normal, 20% errors, 20% latency/CPU load
    while time.time() - start < duration:
        endpoint = random.choices(endpoints, weights=weights)[0]
        mode = "normal" if endpoint in ["/", "/health"] else "incident"
        send_request(endpoint, mode)
        time.sleep(random.uniform(0.1, 0.4))

def main():
    parser = argparse.ArgumentParser(description="Chaos & Load Injector for infra-ai-ops-lab")
    parser.add_argument(
        "--mode",
        choices=["normal", "error", "latency", "mixed"],
        default="normal",
        help="Simulation traffic mode (default: normal)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration of the traffic simulation in seconds (default: 60)"
    )
    args = parser.parse_args()

    print("==================================================")
    print(f"  Chaos Injector Started | Target: {TARGET_URL}")
    print(f"  Mode: {args.mode.upper()} | Duration: {args.duration}s")
    print("==================================================")

    if args.mode == "normal":
        run_normal(args.duration)
    elif args.mode == "error":
        run_error(args.duration)
    elif args.mode == "latency":
        run_latency(args.duration)
    elif args.mode == "mixed":
        run_mixed(args.duration)

    print("==================================================")
    print("  Traffic Simulation Completed successfully.")
    print("==================================================")

if __name__ == "__main__":
    main()
