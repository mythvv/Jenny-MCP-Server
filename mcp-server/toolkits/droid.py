"""
Droid 工具包 - 文件管道模式

实现方式：tail -f input.jsonl | droid exec --input-format stream-jsonrpc
"""

import asyncio
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseToolkit


class DroidToolkit(BaseToolkit):
    """Droid 工具包 - 文件管道模式"""

    name = "droid"
    description = "Factory Droid - 文件管道模式（tail -f input.jsonl | droid exec）"

    # Droid 二进制路径
    DROID_BIN = os.environ.get("DROID_BIN", "droid")

    def __init__(self, sessions_dir: Path, workspace_dir: Path, default_config: dict = None):
        self.sessions_dir = Path(sessions_dir)
        self.workspace_dir = Path(workspace_dir)
        self.default_config = default_config or {}
        self.sessions: dict[str, dict] = {}
        self._last_activity: dict[str, float] = {}
        self._idle_timeout = 1800  # 30 分钟空闲自动回收
        self._gc_task: Optional[asyncio.Task] = None

    def start_gc(self):
        """启动后台回收任务"""
        if self._gc_task is None or self._gc_task.done():
            self._gc_task = asyncio.ensure_future(self._gc_loop())

    async def _gc_loop(self):
        """每 60 秒检查一次空闲会话"""
        import time
        while True:
            await asyncio.sleep(60)
            now = time.time()
            expired = [
                sid for sid, ts in self._last_activity.items()
                if now - ts > self._idle_timeout and sid in self.sessions
            ]
            for sid in expired:
                info = self.sessions.get(sid)
                if info and not self._is_alive(info["proc"]):
                    # 进程已死，直接清理
                    await self.stop_session(sid)
                    del self._last_activity[sid]

    def _touch(self, session_id: str):
        """记录会话活动时间"""
        import time
        self._last_activity[session_id] = time.time()

    async def cleanup_orphan_sessions(self):
        """启动时清理孤儿会话：目录存在但没有对应活进程的会话"""
        if not self.sessions_dir.exists():
            return
        for sdir in self.sessions_dir.iterdir():
            if not sdir.is_dir():
                continue
            pid_file = sdir / "pid"
            if not pid_file.exists():
                # 没有 pid 文件，无法确认，跳过
                continue
            try:
                pid = int(pid_file.read_text().strip())
                # 检查进程是否还活着
                os.kill(pid, 0)
            except (ProcessLookupError, PermissionError, ValueError):
                # 进程已死，清理目录
                import shutil
                shutil.rmtree(sdir, ignore_errors=True)

    def _session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / session_id

    def _is_alive(self, proc: subprocess.Popen) -> bool:
        return proc.poll() is None

    def get_config_schema(self) -> dict:
        return {
            "model": "模型 ID，如 custom:gpt-4o",
            "auto_level": "自动级别 low/medium/high",
            "cwd": "工作目录",
            "reasoning_effort": "推理深度",
        }

    async def start_session(self, config: dict) -> dict:
        model = config.get("model") or self.default_config.get("model", "custom:your-model-id")
        auto_level = config.get("auto_level") or self.default_config.get("auto_level", "high")
        cwd = config.get("cwd") or config.get("workdir") or self.default_config.get("cwd", str(self.workspace_dir))
        reasoning = config.get("reasoning_effort") or self.default_config.get("reasoning_effort", "")
        session_id = config.get("session_id")

        if session_id and session_id in self.sessions:
            proc = self.sessions[session_id]["proc"]
            if self._is_alive(proc):
                return {"session_id": session_id, "status": "already_running"}

        sid = session_id or str(uuid.uuid4())
        sdir = self._session_dir(sid)
        sdir.mkdir(parents=True, exist_ok=True)

        input_file = sdir / "input.jsonl"
        output_file = sdir / "output.jsonl"
        stderr_file = sdir / "stderr.log"
        log_file = sdir / "log.md"

        if not session_id:
            machine_id = f"jenny-droid-{os.uname().nodename}"
            init_msg = {
                "type": "request",
                "jsonrpc": "2.0",
                "factoryApiVersion": "1.0.0",
                "factoryProtocolVersion": "1.28.0",
                "id": "init-1",
                "method": "droid.initialize_session",
                "params": {
                    "machineId": machine_id,
                    "cwd": cwd,
                    "sessionId": sid,
                    "autonomyLevel": auto_level,
                    "modelId": model,
                },
            }
            input_file.write_text(json.dumps(init_msg) + "\n")
            log_file.write_text(
                f"# Session: {sid}\n\n"
                f"**Started:** {datetime.now(timezone.utc).isoformat()}\n"
                f"**Model:** {model}\n**Auto:** {auto_level}\n\n---\n\n"
            )
        else:
            if not input_file.exists():
                input_file.touch()
            if not output_file.exists():
                output_file.touch()

        cmd = [self.DROID_BIN, "exec",
               "--input-format", "stream-jsonrpc",
               "--output-format", "stream-jsonrpc",
               "--auto", auto_level,
               "--model", model,
               "--cwd", cwd]
        if reasoning and reasoning not in ("none", "null", ""):
            cmd += ["--reasoning-effort", reasoning]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=open(output_file, "a"),
            stderr=open(stderr_file, "a"),
        )

        tail_proc = subprocess.Popen(
            ["tail", "-n", "+1", "-f", str(input_file)],
            stdout=proc.stdin,
            stderr=subprocess.DEVNULL,
        )

        self.sessions[sid] = {
            "proc": proc,
            "tail_proc": tail_proc,
            "sdir": str(sdir),
            "model": model,
            "auto_level": auto_level,
            "cwd": cwd,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        (sdir / "pid").write_text(str(proc.pid))
        self._touch(sid)
        return {"session_id": sid, "status": "started", "pid": proc.pid}

    async def send_message(self, session_id: str, message: str) -> dict:
        sdir = self._session_dir(session_id)
        if not sdir.exists():
            return {"error": f"Session {session_id} not found"}

        info = self.sessions.get(session_id, {})
        proc = info.get("proc")
        if proc and not self._is_alive(proc):
            return {"error": "Droid process has exited", "exit_code": proc.returncode}

        input_file = sdir / "input.jsonl"
        log_file = sdir / "log.md"

        ts = int(datetime.now(timezone.utc).timestamp())
        msg = {
            "type": "request",
            "jsonrpc": "2.0",
            "factoryApiVersion": "1.0.0",
            "factoryProtocolVersion": "1.28.0",
            "id": f"msg-{ts}",
            "method": "droid.add_user_message",
            "params": {"text": message},
        }

        with open(input_file, "a") as f:
            f.write(json.dumps(msg) + "\n")

        now = datetime.now().strftime("%H:%M")
        with open(log_file, "a") as f:
            f.write(f"**[{now}] user:** {message}\n")

        self._touch(session_id)
        return {"status": "sent", "session_id": session_id}

    async def poll_output(self, session_id: str, last_line: int = 0) -> dict:
        self._touch(session_id)
        output_file = self._session_dir(session_id) / "output.jsonl"
        if not output_file.exists():
            return {"lines": [], "total_lines": 0}

        all_lines = output_file.read_text().splitlines()
        total = len(all_lines)

        if last_line >= total:
            return {"lines": [], "total_lines": total}

        new_lines = all_lines[last_line:]
        results = []
        for line in new_lines:
            try:
                obj = json.loads(line)
                entry = {"raw_type": obj.get("type", "unknown")}

                if obj.get("type") == "response":
                    result = obj.get("result", {})
                    if "finalText" in result:
                        entry["text"] = result["finalText"]
                    elif "error" in obj:
                        entry["error"] = obj["error"].get("message", "unknown")

                elif obj.get("type") == "notification":
                    params = obj.get("params", {})
                    notif = params.get("notification", {})
                    ntype = notif.get("type", "")
                    if ntype == "assistant_text_delta":
                        entry["delta"] = notif.get("textDelta", "")
                    elif ntype == "create_message":
                        role = notif.get("role", notif.get("message", {}).get("role", ""))
                        entry["role"] = role
                    elif ntype == "tool_use":
                        entry["tool"] = notif.get("name", "")
                    else:
                        entry["notification_type"] = ntype

                results.append(entry)
            except json.JSONDecodeError:
                results.append({"raw": line[:200]})

        return {"lines": results, "total_lines": total}

    async def check_status(self, session_id: Optional[str] = None) -> dict:
        if session_id:
            info = self.sessions.get(session_id)
            if not info:
                return {"error": f"Session {session_id} not found"}
            proc = info["proc"]
            tail = info.get("tail_proc")

            output_file = self._session_dir(session_id) / "output.jsonl"
            msg_count = 0
            if output_file.exists():
                msg_count = len(output_file.read_text().splitlines())

            return {
                "session_id": session_id,
                "alive": self._is_alive(proc),
                "pid": proc.pid,
                "model": info["model"],
                "auto_level": info["auto_level"],
                "cwd": info["cwd"],
                "started_at": info["started_at"],
                "output_lines": msg_count,
                "tail_alive": tail is not None and self._is_alive(tail) if tail else False,
            }

        result = []
        for sid, info in self.sessions.items():
            proc = info["proc"]
            output_file = self._session_dir(sid) / "output.jsonl"
            msg_count = 0
            if output_file.exists():
                msg_count = len(output_file.read_text().splitlines())
            result.append({
                "session_id": sid,
                "alive": self._is_alive(proc),
                "model": info["model"],
                "started_at": info["started_at"],
                "output_lines": msg_count,
            })
        return {"sessions": result}

    async def stop_session(self, session_id: str) -> dict:
        info = self.sessions.get(session_id)
        if not info:
            return {"error": f"Session {session_id} not found"}

        proc = info["proc"]
        tail = info.get("tail_proc")

        if tail and self._is_alive(tail):
            tail.terminate()

        if self._is_alive(proc):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        log_file = self._session_dir(session_id) / "log.md"
        with open(log_file, "a") as f:
            f.write(f"\n---\n**Session ended:** {datetime.now(timezone.utc).isoformat()}\n")

        self.sessions.pop(session_id, None)
        self._last_activity.pop(session_id, None)
        return {"status": "stopped", "session_id": session_id}

    async def _wait_for_completion(self, session_id: str, timeout: int) -> dict:
        import time
        start = time.time()
        all_text = []
        last_line = 0

        while True:
            elapsed = time.time() - start
            if elapsed > timeout:
                await self.stop_session(session_id)
                return {"success": False, "error": "timeout", "output": "\n".join(all_text),
                        "session_id": session_id, "duration_seconds": int(elapsed)}

            info = self.sessions.get(session_id)
            if not info:
                return {"success": False, "error": "session_lost", "output": "\n".join(all_text),
                        "session_id": session_id, "duration_seconds": int(elapsed)}

            proc = info["proc"]
            proc_dead = not self._is_alive(proc)

            result = await self.poll_output(session_id, last_line)
            for line in result.get("lines", []):
                if "text" in line:
                    all_text.append(line["text"])
                elif "delta" in line:
                    all_text.append(line["delta"])
                elif "error" in line:
                    all_text.append(f"[error] {line['error']}")
            last_line = result.get("total_lines", last_line)

            if proc_dead:
                result = await self.poll_output(session_id, last_line)
                for line in result.get("lines", []):
                    if "text" in line:
                        all_text.append(line["text"])
                    elif "delta" in line:
                        all_text.append(line["delta"])
                    elif "error" in line:
                        all_text.append(f"[error] {line['error']}")

                await self.stop_session(session_id)
                elapsed = time.time() - start
                return {"success": True, "output": "\n".join(all_text),
                        "session_id": session_id, "duration_seconds": int(elapsed)}

            await asyncio.sleep(1.5)

    async def exec_and_wait(self, message: str, timeout: int, config: dict) -> dict:
        start_result = await self.start_session(config)
        if "error" in start_result:
            return start_result
        session_id = start_result["session_id"]

        await asyncio.sleep(2)

        send_result = await self.send_message(session_id, message)
        if "error" in send_result:
            await self.stop_session(session_id)
            return send_result

        return await self._wait_for_completion(session_id, timeout)
