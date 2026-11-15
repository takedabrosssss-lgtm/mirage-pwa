#!/usr/bin/env python3
"""One-time, root-only production configuration for the MIRAGE OCI host."""
from __future__ import annotations

import getpass
import json
import os
import pwd
import re
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
ACCOUNTS_FILE_NAME = "MIRAGE_ACCOUNTS.txt"


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def install_systemd_units() -> None:
    service = """[Unit]
Description=Update MIRAGE DuckDNS address
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/mirage
ExecStart=/bin/bash /opt/mirage/scripts/update_duckdns.sh
"""
    timer = """[Unit]
Description=Refresh MIRAGE DuckDNS address every five minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=5min
Unit=mirage-duckdns.service

[Install]
WantedBy=timers.target
"""
    backup_service = """[Unit]
Description=Back up the MIRAGE PostgreSQL database
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/mirage
ExecStart=/bin/bash /opt/mirage/scripts/backup_db.sh
"""
    backup_timer = """[Unit]
Description=Daily MIRAGE PostgreSQL backup

[Timer]
OnCalendar=*-*-* 03:15:00 UTC
Persistent=true
Unit=mirage-backup.service

[Install]
WantedBy=timers.target
"""
    units = {
        "/etc/systemd/system/mirage-duckdns.service": service,
        "/etc/systemd/system/mirage-duckdns.timer": timer,
        "/etc/systemd/system/mirage-backup.service": backup_service,
        "/etc/systemd/system/mirage-backup.timer": backup_timer,
    }
    for raw_path, content in units.items():
        Path(raw_path).write_text(content, encoding="utf-8")
        os.chmod(raw_path, 0o644)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "mirage-duckdns.timer"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "mirage-backup.timer"], check=True)


def main() -> None:
    if os.geteuid() != 0:
        fail("Run this once with sudo: sudo python3 scripts/prepare_server.py")
    if not (ROOT / "docker-compose.yml").is_file() or not (ROOT / "Caddyfile").is_file():
        fail("Run from the complete MIRAGE repository; docker-compose.yml or Caddyfile is missing.")
    if ENV_FILE.exists():
        fail(".env already exists. Refusing to overwrite secrets or account credentials.")

    print("MIRAGE production initialization")
    print("First create one DuckDNS subdomain at https://www.duckdns.org/ .")
    raw_domain = input("DuckDNS subdomain (example: mirage-demo or mirage-demo.duckdns.org): ").strip().lower()
    suffix = ".duckdns.org"
    subdomain = raw_domain[:-len(suffix)] if raw_domain.endswith(suffix) else raw_domain
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain):
        fail("Invalid DuckDNS name. Enter only the subdomain label, without spaces.")
    domain = f"{subdomain}{suffix}"
    token = getpass.getpass("DuckDNS token (input hidden): ").strip()
    if not token or any(ch.isspace() for ch in token):
        fail("DuckDNS token is empty or contains whitespace.")

    query = urllib.parse.urlencode({"domains": subdomain, "token": token, "ip": ""})
    request = urllib.request.Request(
        f"https://www.duckdns.org/update?{query}",
        headers={"User-Agent": "MIRAGE-OCI-setup/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            duckdns_result = response.read(100).decode("utf-8", "replace").strip()
    except (urllib.error.URLError, TimeoutError) as exc:
        fail(f"Could not contact DuckDNS from this server: {exc}")
    if duckdns_result != "OK":
        fail(f"DuckDNS rejected the domain/token. Response: {duckdns_result!r}")

    accounts = [
        {"username": "owner", "password": secrets.token_urlsafe(20), "role": "admin", "language": "ru"},
        {"username": "user2", "password": secrets.token_urlsafe(20), "role": "user", "language": "ru"},
        {"username": "user3", "password": secrets.token_urlsafe(20), "role": "user", "language": "ru"},
        {"username": "user4", "password": secrets.token_urlsafe(20), "role": "user", "language": "ru"},
    ]
    env_values = {
        "POSTGRES_DB": "mirage",
        "POSTGRES_USER": "mirage",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(36),
        "APP_SECRET": secrets.token_urlsafe(64),
        "APP_ENV": "production",
        "MARKET_REGION_LABEL": "OCI",
        "SERVER_REGION_LABEL": "OCI-ARM64",
        "MIRAGE_DOMAIN": domain,
        "DUCKDNS_SUBDOMAIN": subdomain,
        "DUCKDNS_TOKEN": token,
    }
    lines = [f"{key}={value}" for key, value in env_values.items()]
    # Passwords are URL-safe and contain no single quotes, making this valid
    # both as a Docker Compose .env value and as a shell assignment for systemd.
    accounts_json = json.dumps(accounts, separators=(",", ":"), ensure_ascii=True)
    lines.append(f"BOOTSTRAP_USERS_JSON='{accounts_json}'")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(ENV_FILE, 0o600)

    sudo_user = os.environ.get("SUDO_USER", "ubuntu")
    try:
        account = pwd.getpwnam(sudo_user)
        home = Path(account.pw_dir)
        os.chown(ENV_FILE, 0, 0)
    except KeyError:
        home = Path("/home/ubuntu")
        account = None
    credentials_path = home / ACCOUNTS_FILE_NAME
    credential_lines = [
        "MIRAGE — ПЕРВИЧНЫЕ УЧЁТНЫЕ ДАННЫЕ",
        "Сохраните этот файл в надёжном месте. Не загружайте его в GitHub.",
        "",
        f"Адрес приложения: https://{domain}",
        "Paper Trading: виртуальные средства, стартовый баланс каждого аккаунта — 10 000 USDT.",
        "",
    ]
    for user in accounts:
        credential_lines.extend([
            f"Логин: {user['username']}",
            f"Пароль: {user['password']}",
            f"Роль: {user['role']}",
            "",
        ])
    credentials_path.write_text("\n".join(credential_lines), encoding="utf-8")
    os.chmod(credentials_path, 0o600)
    if account:
        os.chown(credentials_path, account.pw_uid, account.pw_gid)

    try:
        install_systemd_units()
    except (subprocess.CalledProcessError, OSError) as exc:
        fail(f"Secrets were safely written, but systemd timer setup failed: {exc}. Do not rerun this script; report this error.")

    print("\nDuckDNS address updated successfully.")
    print(f"Production secrets written to: {ENV_FILE} (root-only permissions)")
    print(f"Account credentials saved to: {credentials_path} (owner-only permissions)")
    print("\n" + "=" * 60)
    print("SAVE THESE FOUR LOGINS AND PASSWORDS NOW:")
    print("=" * 60)
    for user in accounts:
        print(f"{user['username']}  |  {user['password']}  |  {user['role']}")
    print("=" * 60)
    print("\nNext command:")
    print("cd /opt/mirage && sudo docker compose up -d --build")
    print("Do not rerun this initializer and do not delete the mirage_postgres_data volume.")


if __name__ == "__main__":
    main()
