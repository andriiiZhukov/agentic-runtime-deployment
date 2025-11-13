#!/usr/bin/env python3
import subprocess, sys, time, os, json, yaml, requests
from typing import List
from tools.preflight import PreflightConfig, run, need, kctl

def helm_install(cfg: PreflightConfig):
    print("[*] helm upgrade --install …")
    run(["helm","upgrade","--install",cfg.helm_release,cfg.helm_chart,
         "-f",cfg.values_file,"--namespace",cfg.namespace,"--create-namespace"])

def rollout_wait(deploy_name: str, ns: str, timeout_sec: int = 600):
    print(f"[*] waiting for rollout of deploy/{deploy_name} …")
    try:
        run(["kubectl","-n",ns,"rollout","status","deploy",deploy_name,"--timeout",f"{timeout_sec}s"])
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"[X] rollout failed: {e.stderr or e.stdout}")

def http_wait(url: str, expect_key="status", expect_val="ready", timeout_sec=120):
    print(f"[*] HTTP wait {url} …")
    t0 = time.time()
    while time.time()-t0 < timeout_sec:
        try:
            r = requests.get(url, timeout=5)
            if r.ok:
                data = r.json()
                if expect_key in data and (expect_val is None or data[expect_key]==expect_val):
                    print(f"[OK] {url} => {data}")
                    return
        except Exception:
            pass
        time.sleep(3)
    raise SystemExit(f"[X] not ready: {url}")

def smoke_execute(base_url: str):
    url = base_url.rstrip("/") + "/execute"
    print(f"[*] smoke POST {url}")
    r = requests.post(url, json={"query":"ping"}, timeout=15)
    if not r.ok:
        raise SystemExit(f"[X] execute failed: {r.status_code} {r.text}")
    print(f"[OK] execute: {r.json()}")

def main():
    if len(sys.argv) < 2:
        print("usage: deploy.py <preflight.yaml>")
        sys.exit(2)
    with open(sys.argv[1]) as f:
        raw = yaml.safe_load(f)
    cfg = PreflightConfig(**raw)

    # (optional) terraform apply
    if cfg.terraform_dir:
        need("terraform")
        print("[*] terraform apply …")
        run(["terraform","-chdir="+cfg.terraform_dir,"apply","-auto-approve"])

    helm_install(cfg)

    deploy_name = cfg.helm_release

    rollout_wait(deploy_name, cfg.namespace)
    base = f"https://{raw['ingress_host']}"
    http_wait(base + "/health/ready")
    smoke_execute(base)

    print("\n[OK] deploy is healthy & executable")

if __name__ == "__main__":
    main()
