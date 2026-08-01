#!/usr/bin/env python3
"""
Multi-user stateful simulation against an egress proxy pool.

Each simulated user opens a session (sets a cookie via postman-echo), then
browses P pages. Every page = one cookie-echo request + one exit-IP check.
A BoundedSemaphore enforces max-concurrent in-flight requests. Results,
errors, and per-user IP lists are written to /tmp as JSON for analysis.

Stdlib only — shells out to `curl` per request. No pip deps.

Usage:
    python3 proxy_pool_sim.py [USERS] [PAGES] [MAX_CONCURRENT]
Env overrides: PROXY, COOKIE_URL, ECHO_URL, IP_URL, USERS, PAGES, MAX_CONCURRENT, TIMEOUT

Example:
    PROXY=http://192.168.4.120:10908 python3 proxy_pool_sim.py 10 6 3
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import threading
import time

PROXY = os.environ.get("PROXY", "http://192.168.4.120:10908")
COOKIE_URL = os.environ.get("COOKIE_URL", "https://postman-echo.com/cookies/set?session={uid}")
ECHO_URL = os.environ.get("ECHO_URL", "https://postman-echo.com/cookies")
IP_URL = os.environ.get("IP_URL", "https://api.ipify.org")

def _arg(idx, default):
    return int(sys.argv[idx]) if len(sys.argv) > idx else int(os.environ.get(default.split(":")[0], default.split(":")[1]))

USERS = int(os.environ.get("USERS", sys.argv[1] if len(sys.argv) > 1 else "10"))
PAGES = int(os.environ.get("PAGES", sys.argv[2] if len(sys.argv) > 2 else "6"))
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", sys.argv[3] if len(sys.argv) > 3 else "3"))
TIMEOUT = int(os.environ.get("TIMEOUT", "12"))
THINK_MIN, THINK_MAX = 0.4, 1.6  # seconds of browsing jitter between requests

sem = threading.BoundedSemaphore(MAX_CONCURRENT)
lock = threading.Lock()
results = []  # {user, page, kind, value, latency, code}
errors = []
start_time = time.time()


def now():
    return time.time() - start_time


def curl(args, jar, timeout=TIMEOUT):
    """curl through the proxy with per-user jar; returns (latency, code, body)."""
    cmd = ["curl", "-s", "-m", str(timeout), "-x", PROXY,
           "-c", jar, "-b", jar, "-o", "-", "-w", "\n__CODE__%{http_code}"] + args
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        lat = time.time() - t0
        out = p.stdout
        body, _, code = out.rpartition("__CODE__")
        return lat, code.strip(), body
    except subprocess.TimeoutExpired:
        return time.time() - t0, "000", ""


def record(user, page, kind, value, lat, code):
    with lock:
        results.append({"user": user, "page": page, "kind": kind,
                        "value": value, "latency": round(lat, 3), "code": code})


def user_session(uid):
    """One simulated user's stateful browsing session."""
    jar = os.path.join(tempfile.gettempdir(), f"proxy-sim-{uid}.jar")
    user_ips = []

    # 1. Establish session cookie
    with sem:
        lat, code, _ = curl([COOKIE_URL.format(uid=uid)], jar)
    record(uid, "login", "cookie-set", code, lat, code)
    if code not in ("200", "302"):
        errors.append((uid, "login", code))
    time.sleep(random.uniform(THINK_MIN, THINK_MAX))

    # 2. Browse pages; each page verifies cookie persistence + records exit IP
    for page in range(1, PAGES + 1):
        with sem:
            lat, code, body = curl([ECHO_URL], jar)
        cookie_echo = "session" in body
        record(uid, page, "cookie-echo", str(cookie_echo), lat, code)
        if code != "200":
            errors.append((uid, page, f"echo:{code}"))
        time.sleep(random.uniform(THINK_MIN, THINK_MAX))

        with sem:
            lat, code, body = curl([IP_URL], jar)
        ip = body.strip()
        user_ips.append(ip)
        record(uid, page, "exit-ip", ip, lat, code)
        if code != "200" or not ip:
            errors.append((uid, page, f"ip:{code}"))
        time.sleep(random.uniform(THINK_MIN, THINK_MAX))

    return user_ips


def main():
    print(f"=== Proxy sim: {USERS} users, max {MAX_CONCURRENT} concurrent, {PAGES} pages/user ===", flush=True)
    threads = []
    all_ips = {}
    for uid in range(1, USERS + 1):
        t = threading.Thread(target=lambda u=uid: all_ips.update({u: user_session(u)}), daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    print(f"=== DONE in {now():.1f}s ===", flush=True)
    return all_ips


if __name__ == "__main__":
    ips = main()
    with open("/tmp/proxy-sim-ips.json", "w") as f:
        json.dump(ips, f, indent=1)
    with open("/tmp/proxy-sim-results.json", "w") as f:
        json.dump(results, f, indent=1)
    with open("/tmp/proxy-sim-errors.json", "w") as f:
        json.dump(errors, f, indent=1)
    print("saved: /tmp/proxy-sim-{ips,results,errors}.json")
