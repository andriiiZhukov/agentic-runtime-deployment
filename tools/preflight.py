#!/usr/bin/env python3
import subprocess, sys, time, json, shutil, os
from typing import List, Optional
from pydantic import BaseModel, Field, validator
import yaml

def run(cmd: List[str], check=True, capture=True, text=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=text)

def need(bin_name: str):
    if not shutil.which(bin_name):
        raise SystemExit(f"[X] required binary not found: {bin_name}")

class PreflightConfig(BaseModel):
    namespace: str
    helm_release: str
    helm_chart: str
    values_file: str
    ingress_host: str
    oci_refs: List[str] = Field(default_factory=list)      # OCI artifacts to check (agent-bundle, prompt packs, etc.)
    required_secrets: List[str] = Field(default_factory=list)  # names of K8s Secrets (OR ExternalSecret final names)
    required_crds: List[str] = Field(default_factory=list)     # e.g. ["scaledobjects.keda.sh","rayservices.ray.io"]
    terraform_dir: Optional[str] = None                         # if you run Terraform infra as part of deploy

    @validator("values_file","helm_chart")
    def file_exists(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"file not found: {v}")
        return v

def kctl(args: List[str]) -> subprocess.CompletedProcess:
    return run(["kubectl"] + args)

def check_kube_access(ns: str):
    print("[*] checking kubectl context and namespace access…")
    kctl(["cluster-info"])
    # ensure namespace exists (or create via helm later)
    try:
      out = kctl(["get","ns",ns,"-o","json"],)
      data = json.loads(out.stdout)
      print(f"[OK] namespace: {data['metadata']['name']}")
    except subprocess.CalledProcessError:
      print(f"[i] namespace '{ns}' does not exist yet (Helm will create it).")

def check_crds(crds: List[str]):
    if not crds: return
    print("[*] checking required CRDs…")
    missing = []
    for c in crds:
        try:
            kctl(["get","crd",c])
            print(f"  [OK] {c}")
        except subprocess.CalledProcessError:
            missing.append(c)
    if missing:
        raise SystemExit(f"[X] missing CRDs: {missing}")

def check_secrets(ns: str, names: List[str]):
    if not names: return
    print("[*] checking required Secrets…")
    missing = []
    for s in names:
        try:
            kctl(["-n",ns,"get","secret",s])
            print(f"  [OK] secret/{s}")
        except subprocess.CalledProcessError:
            missing.append(s)
    if missing:
        raise SystemExit(f"[X] missing secrets in ns/{ns}: {missing} "
                         f"(если используете ExternalSecrets — проверьте статус синхронизации)")

def check_oci(refs: List[str]):
    if not refs: return
    need("oras")
    print("[*] checking OCI artifacts via ORAS…")
    for ref in refs:
        try:
            out = run(["oras","manifest","fetch",ref])
            print(f"  [OK] {ref} manifest digest: {json.loads(out.stdout).get('config',{}).get('digest','<ok>')}")
        except Exception as e:
            raise SystemExit(f"[X] OCI not accessible: {ref}: {e}")

def helm_lint_template(cfg: PreflightConfig):
    need("helm")
    print("[*] helm lint/template…")
    run(["helm","lint",cfg.helm_chart,"-f",cfg.values_file])
    run(["helm","template",cfg.helm_release,cfg.helm_chart,"-f",cfg.values_file])

def helm_dry_run(cfg: PreflightConfig):
    print("[*] helm dry-run install…")
    run(["helm","upgrade","--install",cfg.helm_release,cfg.helm_chart,
         "-f",cfg.values_file,"--namespace",cfg.namespace,"--create-namespace",
         "--dry-run","--debug"])

def terraform_validate_apply(tf_dir: Optional[str]):
    if not tf_dir: return
    need("terraform")
    print("[*] terraform init/validate/plan…")
    run(["terraform","-chdir="+tf_dir,"init","-upgrade"])
    run(["terraform","-chdir="+tf_dir,"validate"])
    run(["terraform","-chdir="+tf_dir,"plan"])

def main():
    if len(sys.argv) < 2:
        print("usage: preflight.py <config.yaml>")
        sys.exit(2)
    with open(sys.argv[1]) as f:
        raw = yaml.safe_load(f)
    cfg = PreflightConfig(**raw)

    # tools
    for b in ["kubectl","helm"]:
        need(b)

    terraform_validate_apply(cfg.terraform_dir)
    check_kube_access(cfg.namespace)
    check_crds(cfg.required_crds)
    check_secrets(cfg.namespace, cfg.required_secrets)
    check_oci(cfg.oci_refs)
    helm_lint_template(cfg)
    helm_dry_run(cfg)

    print("\n[OK] preflight passed")

if __name__ == "__main__":
    main()
