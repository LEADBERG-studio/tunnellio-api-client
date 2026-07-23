from __future__ import annotations

import http.server
import json
import os
import shutil
import socketserver
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "src")

from tunnellio.client import ApiClient
from tunnellio.config import load_runtime_config
from tunnellio.planner import Planner, PlanOptions

TOKEN = "tnl_RrvwZTDXHrnqZe5_mB8lnP9hpI8eidfa"
BASE_URL = "https://api.tunnellio.ru"
TEST_ID = str(int(time.time()))
KEY_NAME = f"e2e-{TEST_ID}"
DOMAIN_NAME = f"e2e-{TEST_ID}"
LOCAL_PORT = 32123
MARKER = f"tunnellio-e2e-{TEST_ID}"
KEY_DIR = Path.home() / ".tunnellio" / "keys"
KEY_PATH = KEY_DIR / KEY_NAME
PUB_PATH = KEY_DIR / f"{KEY_NAME}.pub"

summary: dict[str, object] = {
    "secureTlsApi": {"ok": False},
    "insecureTlsFallbackUsed": False,
    "meta": None,
    "capabilities": None,
    "ssh": {},
    "cli": {},
    "persistentFlow": {},
    "ephemeralFlow": {},
    "cleanup": {},
    "errors": [],
}

created_key_id = None
created_domain_id = None
created_session_id = None
ssh_process = None
httpd = None


def record_error(stage: str, exc: Exception) -> None:
    summary.setdefault("errors", []).append({"stage": stage, "error": repr(exc)})


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = MARKER.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_http_server() -> None:
    global httpd

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    httpd = ReusableTCPServer(("127.0.0.1", LOCAL_PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()


def stop_http_server() -> None:
    global httpd
    if httpd is not None:
        httpd.shutdown()
        httpd.server_close()
        httpd = None


def stop_ssh() -> None:
    global ssh_process
    if ssh_process is None:
        return
    if ssh_process.poll() is None:
        try:
            ssh_process.terminate()
            ssh_process.wait(timeout=10)
        except Exception:
            try:
                ssh_process.kill()
            except Exception:
                pass
    ssh_process = None


def wait_for_url(url: str, timeout_seconds: int = 30) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    attempts = []
    ctx = ssl.create_default_context()
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5, context=ctx) as response:
                body = response.read().decode("utf-8", errors="replace")
                attempts.append({"status": response.status, "body": body[:200]})
                if MARKER in body:
                    return {"ok": True, "attempts": attempts}
        except Exception as exc:
            attempts.append({"error": repr(exc)})
        time.sleep(2)
    return {"ok": False, "attempts": attempts}


def get_clients() -> tuple[ApiClient, ApiClient]:
    secure_cfg = load_runtime_config(token=TOKEN, base_url=BASE_URL, state_dir=None, insecure_tls=False)
    insecure_cfg = load_runtime_config(token=TOKEN, base_url=BASE_URL, state_dir=None, insecure_tls=True)
    return ApiClient(secure_cfg), ApiClient(insecure_cfg)


def main() -> int:
    global created_key_id, created_domain_id, created_session_id, ssh_process

    KEY_DIR.mkdir(parents=True, exist_ok=True)
    secure_client, insecure_client = get_clients()

    active_client = secure_client
    try:
        summary["meta"] = secure_client.fetch_meta()
        summary["capabilities"] = secure_client.fetch_capabilities()
        summary["secureTlsApi"] = {"ok": True}
    except Exception as exc:
        summary["secureTlsApi"] = {"ok": False, "error": repr(exc)}
        summary["insecureTlsFallbackUsed"] = True
        active_client = insecure_client
        summary["meta"] = active_client.fetch_meta()
        summary["capabilities"] = active_client.fetch_capabilities()

    cli_meta = subprocess.run(
        [sys.executable, "-m", "tunnellio.cli", "--token", TOKEN, "--insecure-tls", "meta"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    summary["cli"] = {
        "metaRc": cli_meta.returncode,
        "metaStdout": cli_meta.stdout[:500],
        "metaStderr": cli_meta.stderr[:500],
    }

    ssh_path = shutil.which("ssh")
    ssh_keygen_path = shutil.which("ssh-keygen")
    summary["ssh"] = {
        "sshPath": ssh_path,
        "sshKeygenPath": ssh_keygen_path,
        "keyPath": str(KEY_PATH),
    }
    if not ssh_path or not ssh_keygen_path:
        raise RuntimeError("ssh or ssh-keygen is not available in the execution environment")

    gen = subprocess.run(
        [ssh_keygen_path, "-q", "-t", "ed25519", "-N", "", "-f", str(KEY_PATH), "-C", KEY_NAME],
        capture_output=True,
        text=True,
        timeout=30,
    )
    summary["ssh"]["sshKeygenRc"] = gen.returncode
    summary["ssh"]["sshKeygenStderr"] = gen.stderr[:500]
    if gen.returncode != 0:
        raise RuntimeError(f"ssh-keygen failed: {gen.stderr}")

    public_key = PUB_PATH.read_text(encoding="utf-8").strip()

    created = active_client.create_key(name=KEY_NAME, public_key=public_key, requested_lifetime_days=1)
    created_key_id = int(created["id"])
    summary["persistentFlow"]["createdKey"] = created

    check = active_client.check_domain_availability(DOMAIN_NAME)
    summary["persistentFlow"]["domainCheck"] = check
    if not check.get("available"):
        raise RuntimeError(f"test hostname not available: {DOMAIN_NAME}")

    domain = active_client.create_domain(
        hostname=DOMAIN_NAME,
        key_id=created_key_id,
        local_port=LOCAL_PORT,
        note="e2e persistent test",
        requested_lifetime_days=1,
    )
    created_domain_id = int(domain["id"])
    summary["persistentFlow"]["createdDomain"] = domain

    profile = active_client.get_connection_profile(domain_id=created_domain_id, local_host="127.0.0.1", local_port=LOCAL_PORT)
    summary["persistentFlow"]["connectionProfile"] = profile

    planner = Planner(active_client, load_runtime_config(token=TOKEN, base_url=BASE_URL, state_dir=None, insecure_tls=True))
    persistent_plan = planner.build_plan(
        PlanOptions(
            domain_selector=f"existing:{DOMAIN_NAME}",
            local_host="127.0.0.1",
            local_port=LOCAL_PORT,
            mode="plan",
        )
    )
    summary["persistentFlow"]["planSummary"] = {
        "domain": persistent_plan.domain.to_dict(),
        "publicUrl": persistent_plan.connection_profile.public_url,
    }

    start_http_server()
    ephemeral_plan = planner.build_plan(
        PlanOptions(
            domain_selector="random",
            key_selector=f"existing:{KEY_NAME}",
            local_host="127.0.0.1",
            local_port=LOCAL_PORT,
            note="e2e ephemeral tunnel",
            mode="connect",
        )
    )
    if ephemeral_plan.session is None:
        raise RuntimeError("ephemeral launch-spec did not return a session")
    created_session_id = ephemeral_plan.session.id
    summary["ephemeralFlow"]["plan"] = {
        "domain": ephemeral_plan.domain.to_dict(),
        "session": ephemeral_plan.session.to_dict(),
        "publicUrl": ephemeral_plan.connection_profile.public_url,
    }

    ssh_args = [os.path.expanduser(arg) if "~" in arg else arg for arg in ephemeral_plan.connection_profile.ssh_args]
    ssh_log = Path("ssh-e2e.log")
    ssh_err = Path("ssh-e2e.err.log")
    with ssh_log.open("w", encoding="utf-8") as out, ssh_err.open("w", encoding="utf-8") as err:
        ssh_process = subprocess.Popen(ssh_args, stdout=out, stderr=err)
        summary["ephemeralFlow"]["sshPid"] = ssh_process.pid
        probe = wait_for_url(ephemeral_plan.connection_profile.public_url)
        summary["ephemeralFlow"]["probe"] = probe
        summary["ephemeralFlow"]["sshReturnCodeDuringProbe"] = ssh_process.poll()

    if not summary["ephemeralFlow"]["probe"].get("ok"):
        err_text = Path("ssh-e2e.err.log").read_text(encoding="utf-8", errors="replace") if Path("ssh-e2e.err.log").exists() else ""
        summary["ephemeralFlow"]["sshErrTail"] = err_text[-2000:]
        raise RuntimeError("public URL did not start serving the expected content")

    stop_ssh()
    completed = active_client.complete_session(created_session_id)
    summary["ephemeralFlow"]["completedSession"] = completed
    created_session_id = None

    if created_domain_id is not None:
        summary["cleanup"]["deletedDomain"] = active_client._request("/v1/domains/delete", {"domainId": created_domain_id})
        created_domain_id = None
    if created_key_id is not None:
        summary["cleanup"]["deletedKey"] = active_client._request("/v1/keys/delete", {"keyId": created_key_id})
        created_key_id = None

    if KEY_PATH.exists():
        KEY_PATH.unlink()
    if PUB_PATH.exists():
        PUB_PATH.unlink()

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        record_error("main", exc)
        try:
            secure_client, insecure_client = get_clients()
            active_client = insecure_client
            stop_ssh()
            stop_http_server()
            if created_session_id is not None:
                try:
                    summary["cleanup"]["completedSessionOnError"] = active_client.complete_session(created_session_id)
                except Exception as inner_exc:
                    record_error("cleanup-complete-session", inner_exc)
            if created_domain_id is not None:
                try:
                    summary["cleanup"]["deletedDomainOnError"] = active_client._request("/v1/domains/delete", {"domainId": created_domain_id})
                except Exception as inner_exc:
                    record_error("cleanup-delete-domain", inner_exc)
            if created_key_id is not None:
                try:
                    summary["cleanup"]["deletedKeyOnError"] = active_client._request("/v1/keys/delete", {"keyId": created_key_id})
                except Exception as inner_exc:
                    record_error("cleanup-delete-key", inner_exc)
        finally:
            if KEY_PATH.exists():
                KEY_PATH.unlink()
            if PUB_PATH.exists():
                PUB_PATH.unlink()
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        raise
