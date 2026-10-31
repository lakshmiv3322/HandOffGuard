"""
Security & Credential Audit Scanner for HandoffGuard
===================================================
Scans tracked repository files, frontend assets, and Git history for credentials.
Never outputs secret values -- only file paths and matched pattern types.
"""

import os
import re
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SUSPICIOUS_PATTERNS = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("Hardcoded Secret / Auth Token", re.compile(r'(?:api[_-]?key|auth[_-]?token|secret[_-]?key)\s*[:=]\s*["\'][0-9a-zA-Z\-_]{16,}["\']', re.I)),
]

DB_CREDENTIAL_PATTERNS = [
    ("Hardcoded Database Password", re.compile(r'(?:EXASOL_PASSWORD|password|pwd)\s*[:=]\s*["\'](?!exasol|CHANGE_ME|<.*>)[^"\']{4,}["\']', re.I)),
]

def scan_tracked_files():
    print("[1/3] Scanning tracked files...")
    tracked = subprocess.check_output(["git", "-C", REPO_ROOT, "ls-files"], text=True).splitlines()
    findings = []

    for rel_path in tracked:
        full_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for name, pat in SUSPICIOUS_PATTERNS:
                    if pat.search(content):
                        findings.append((rel_path, name))
        except Exception:
            pass

    return findings, len(tracked)

def scan_frontend():
    print("[2/3] Verifying frontend contains no database credentials...")
    tracked = subprocess.check_output(["git", "-C", REPO_ROOT, "ls-files"], text=True).splitlines()
    frontend_files = [p for p in tracked if p.startswith("frontend/")]
    findings = []

    for rel_path in frontend_files:
        full_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.isfile(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                for term in ["exasol_password", "exasol_user", "localhost:8563", "dsn="]:
                    if term in content:
                        findings.append((rel_path, term))
        except Exception:
            pass

    return findings, len(frontend_files)

def scan_git_history():
    print("[3/3] Scanning Git log for credential exposures in commit history...")
    log = subprocess.check_output(
        ["git", "-C", REPO_ROOT, "log", "-p", "-n", "30", "--", ":!package-lock.json", ":!pnpm-lock.yaml"],
        text=True,
        errors="ignore",
    )
    findings = []
    for line in log.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            for name, pat in SUSPICIOUS_PATTERNS:
                if pat.search(line):
                    findings.append(name)
    return findings

def main():
    print("=" * 60)
    print("HandoffGuard Security & Credential Audit")
    print("=" * 60)

    tracked_findings, total_tracked = scan_tracked_files()
    print(f"  Tracked files scanned: {total_tracked}")
    if tracked_findings:
        print(f"  [FAIL] Discovered {len(tracked_findings)} potential secret patterns in tracked files:")
        for path, pat_name in tracked_findings:
            print(f"    - {path}: {pat_name}")
    else:
        print("  [PASS] Zero production secrets or private keys found in tracked files.")

    frontend_findings, total_fe = scan_frontend()
    print(f"  Frontend files scanned: {total_fe}")
    if frontend_findings:
        print(f"  [FAIL] Frontend files containing database credentials/hostnames:")
        for path, term in frontend_findings:
            print(f"    - {path}: term '{term}'")
    else:
        print("  [PASS] Frontend is completely decoupled from database credentials.")

    history_findings = scan_git_history()
    if history_findings:
        print(f"  [WARN] Git history contains {len(history_findings)} suspicious diff patterns (check commit history).")
    else:
        print("  [PASS] Recent Git history clean of high-risk key patterns.")

    print("=" * 60)

if __name__ == "__main__":
    main()
