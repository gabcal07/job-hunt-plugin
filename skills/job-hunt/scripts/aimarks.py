#!/usr/bin/env python3
"""Run the vendored watermarks-remover service and strip file metadata with it.

Usage:
  aimarks.py start [--port 8765] [--state DIR]
  aimarks.py clean FILE... [--port 8765] [--keep-backup]
  aimarks.py status [--port 8765] [--state DIR]
  aimarks.py stop [--state DIR]
  aimarks.py --self-test

Only used on generated PDF/DOCX files, never on text. Every command exits 0
(except a failed --self-test): the job-hunt pipeline must never stop because of it.
Stdlib only, Python 3.10+.
"""
import argparse
import base64
import io
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("Python 3.10 or newer is needed.")
for _s in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
    _s.reconfigure(encoding="utf-8", errors="replace")

# skills/job-hunt/scripts/aimarks.py -> up 3 = plugin root
ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "vendor" / "watermarks-remover" / "service" / "scripts"
SERVER = SCRIPTS / "server.py"
HOST = "127.0.0.1"
OPTIONAL_PDF_TOOLS = ("exiftool", "qpdf")


def default_state() -> Path:
    home = os.environ.get("JOB_HUNT_HOME")
    return (Path(home) if home else Path.home() / "job-hunt") / "state"


def call(port, path, body=None, timeout=10):
    """GET/POST JSON to the local service. Returns the parsed dict; raises on any failure."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"http://{HOST}:{port}{path}", data=data)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # the server puts the reason in {"error": ...}
        try:
            msg = json.load(e).get("error", "")
        except Exception:
            msg = ""
        raise RuntimeError(msg or f"HTTP {e.code}") from None


def is_up(port) -> bool:
    try:
        return bool(call(port, "/health", timeout=2).get("ok"))
    except Exception:
        return False


def missing_tools(port) -> list[str]:
    try:
        tools = call(port, "/capabilities", timeout=5).get("tools", {})
    except Exception:
        return []
    return [t for t in OPTIONAL_PDF_TOOLS if not tools.get(t)]


# ---------------------------------------------------------------- start / stop

def log_tail(log: Path, n=8) -> str:
    try:
        return "\n".join(log.read_text(errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def cmd_start(a):
    state = Path(a.state)
    if is_up(a.port):
        print(f"aimarks: up on {HOST}:{a.port} (already running, not started by us)")
        return
    try:
        if not SERVER.is_file():
            raise RuntimeError(f"server not found at {SERVER}")
        state.mkdir(parents=True, exist_ok=True)
        log = state / "aimarks.log"
        kw = {"start_new_session": True} if os.name != "nt" else {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
        with open(log, "ab") as lf:
            proc = subprocess.Popen(
                [sys.executable, str(SERVER), "--host", HOST, "--port", str(a.port)],
                cwd=SCRIPTS, stdin=subprocess.DEVNULL, stdout=lf, stderr=lf, **kw)
        deadline = time.time() + 20
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"server exited with code {proc.returncode}")
            if is_up(a.port):
                (state / "aimarks.pid").write_text(json.dumps(
                    {"pid": proc.pid, "port": a.port, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}))
                print(f"aimarks: up on {HOST}:{a.port}")
                return
            time.sleep(0.3)
        kill(proc.pid)
        raise RuntimeError("no /health answer within 20s")
    except Exception as e:
        tail = log_tail(state / "aimarks.log")
        if tail:
            print(tail)
        print(f"aimarks: unavailable ({e})")


def alive(pid) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # guard against a recycled pid: only treat it as ours if it runs server.py (zombies don't)
    cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
    return "server.py" in cmd


def kill(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        if not alive(pid):
            return
        time.sleep(0.1)
    os.kill(pid, signal.SIGKILL)


def read_pidfile(state: Path):
    try:
        return json.loads((state / "aimarks.pid").read_text())
    except (OSError, ValueError):
        return None


def cmd_stop(a):
    state = Path(a.state)
    info = read_pidfile(state)
    if not info:
        print("aimarks: not running")
        return
    try:
        if alive(info["pid"]):
            kill(info["pid"])
    except Exception as e:
        print(f"aimarks: stop problem ({e})")
    (state / "aimarks.pid").unlink(missing_ok=True)
    print("aimarks: stopped")


def cmd_status(a):
    info = read_pidfile(Path(a.state))
    port = info["port"] if info and a.port is None else (a.port or 8765)
    if not is_up(port):
        print(f"aimarks: not running (nothing on {HOST}:{port})")
        return
    owner = f"pid {info['pid']}, started {info['started']}" if info else "not started by us"
    print(f"aimarks: up on {HOST}:{port} ({owner})")
    miss = missing_tools(port)
    if miss:
        print(f"aimarks: PDF cleaning is partial: {', '.join(miss)} missing "
              "(install them, e.g. `brew install exiftool qpdf`)")
    else:
        print("aimarks: exiftool and qpdf present, full PDF cleaning")


# ----------------------------------------------------------------------- clean

def valid_output(name: str, data: bytes) -> bool:
    low = name.lower()
    if low.endswith(".pdf"):
        return data.startswith(b"%PDF")
    if low.endswith((".docx", ".odt", ".xlsx", ".pptx")):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return z.testzip() is None
        except zipfile.BadZipFile:
            return False
    return True


def clean_one(path: Path, port, miss, keep_backup) -> str:
    orig = path.read_bytes()
    body = {"file": base64.b64encode(orig).decode(), "name": path.name}
    insp = call(port, "/inspect", body, timeout=60)
    findings = [f for f, c in zip(insp.get("report", {}).get("findings", []),
                                  insp.get("report", {}).get("findings_confidence", []))
                if c != "informational"]
    res = call(port, "/clean", body, timeout=120)
    if not res.get("ok") or "cleaned" not in res:
        return f"failed ({res.get('error', 'no cleaned data in response')})"
    rep = res.get("report", {})
    kind = rep.get("format") or res.get("kind", "?")
    partial = f"partial: {', '.join(miss)} missing" if kind == "pdf" and miss else ""
    new = base64.b64decode(res["cleaned"])
    if not valid_output(path.name, new):
        return f"{kind} failed (output invalid)"
    if new == orig or rep.get("changed") is False:
        return f"{kind} unchanged" + (f" ({partial})" if partial else "")
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(new)
        shutil.copymode(path, tmp)
        if keep_backup:
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp:
            Path(tmp).unlink(missing_ok=True)
    detail = f"{len(findings)} findings removed" + (f", {partial}" if partial else "")
    return f"{kind} cleaned ({detail})"


def cmd_clean(a):
    up = is_up(a.port)
    miss = missing_tools(a.port) if up else []
    for f in a.files:
        if not up:
            print(f"aimarks: {f} skipped (server not running)")
            continue
        try:
            print(f"aimarks: {f} {clean_one(Path(f), a.port, miss, a.keep_backup)}")
        except Exception as e:
            print(f"aimarks: {f} failed ({e})")


# ------------------------------------------------------------------- self-test

def tiny_pdf() -> bytes:
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] >>",
            b"<< /Producer (aimarks self-test) /Creator (aimarks self-test) >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R /Info 4 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


def self_test():
    with socket.socket() as s:
        s.bind((HOST, 0))
        port = s.getsockname()[1]
    me = [sys.executable, str(Path(__file__).resolve())]
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "t.pdf"
        pdf.write_bytes(tiny_pdf())
        try:
            run = lambda *args: subprocess.run(me + list(args), capture_output=True, text=True, check=True).stdout  # noqa: E731
            out = run("start", "--port", str(port), "--state", tmp)
            print(out, end="")
            assert f"up on {HOST}:{port}" in out, "server did not start"
            assert is_up(port), "/health failed"
            print(run("clean", str(pdf), "--port", str(port)), end="")
            assert pdf.read_bytes().startswith(b"%PDF"), "cleaned file is not a PDF"
        finally:
            print(subprocess.run(me + ["stop", "--state", tmp], capture_output=True, text=True).stdout, end="")
        with socket.socket() as s:
            assert s.connect_ex((HOST, port)) != 0, "port still open after stop"
    print("self-test OK")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-test", action="store_true")
    sub = p.add_subparsers(dest="cmd")
    for name, fn in (("start", cmd_start), ("clean", cmd_clean), ("status", cmd_status), ("stop", cmd_stop)):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        if name != "clean":
            sp.add_argument("--state", default=str(default_state()))
        if name != "stop":
            sp.add_argument("--port", type=int, default=None if name == "status" else 8765)
        if name == "clean":
            sp.add_argument("files", nargs="+")
            sp.add_argument("--keep-backup", action="store_true")
    a = p.parse_args()
    if a.self_test:
        try:
            self_test()
        except Exception as e:
            print(f"self-test FAILED: {e!r}")
            return 1
        return 0
    if not a.cmd:
        p.print_help()
        return 0
    try:
        a.fn(a)
    except Exception as e:  # the pipeline must never stop because of this
        print(f"aimarks: unavailable ({e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
