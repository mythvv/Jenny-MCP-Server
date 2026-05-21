"""
Droid Toolkit - File pipe mode

Implementation: tail -f input.jsonl | droid exec --input-format stream-jsonrpc
"""

import asyncio
import json
import os
import signal
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from toolkits.base import BaseToolkit


class DroidToolkit(BaseToolkit):

    name = "droid"
    description = "Factory Droid - File pipe mode (tail -f input.jsonl | droid exec)"

    DROID_BIN = os.environ.get("DROID_BIN", "/root/.local/bin/droid")
    _CONFIG_FILE = Path(__file__).resolve().parent / "droid_config.json"

    NOISE_TYPES = frozenset({
        "thinking_text_delta", "thinking_text_complete",
        "mcp_status_changed", "settings_updated",
        "session_token_usage_changed", "session_title_updated",
    })

    def __init__(self, ctx=None):
        super().__init__()
        ctx = ctx or {}
        base = Path(ctx.get("base_dir", "/tmp/jenny-droid"))
        self.sessions_dir = base / "sessions"
        self.workspace_dir = base / "workspace"
        self.default_config = self._load_config()
        self.sessions: dict[str, dict] = {}
        self._idle_timeout = 1800
        self._active_session_id: Optional[str] = None

    def _load_config(self) -> dict:
        if self._CONFIG_FILE.exists():
            try:
                return json.loads(self._CONFIG_FILE.read_text())
            except Exception:
                pass
        return {}

    def startup(self):
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.cleanup_orphan_sessions())
            else:
                loop.run_until_complete(self.cleanup_orphan_sessions())
        except RuntimeError:
            asyncio.ensure_future(self.cleanup_orphan_sessions())
        print(f"[droid] startup: sessions={self.sessions_dir}, workspace={self.workspace_dir}")

    async def cleanup_orphan_sessions(self):
        import shutil
        if not self.sessions_dir.exists():
            return
        for sdir in self.sessions_dir.iterdir():
            if not sdir.is_dir():
                continue
            pid_file = sdir / "pid"
            if not pid_file.exists():
                continue
            try:
                pid = int(pid_file.read_text().strip())
                try:
                    os.kill(pid, signal.SIGTERM)
                    await asyncio.sleep(0.5)
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                except (ProcessLookupError, PermissionError):
                    pass
            except (ValueError, PermissionError):
                pass
            shutil.rmtree(sdir, ignore_errors=True)

    def _session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / session_id

    def _is_alive(self, proc: subprocess.Popen) -> bool:
        return proc.poll() is None

    async def _wait_for_init(self, session_id: str, timeout: float = 10.0) -> dict:
        import time
        start = time.time()
        output_file = self._session_dir(session_id) / "output.jsonl"

        while time.time() - start < timeout:
            info = self.sessions.get(session_id)
            if not info or not self._is_alive(info["proc"]):
                return {"success": False, "error": "droid process exited during init"}
            if output_file.exists():
                for line in output_file.read_text().splitlines():
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "response" and obj.get("id") == "init-1":
                            if "error" in obj:
                                return {"success": False, "error": obj["error"].get("message", "init failed")}
                            return {"success": True}
                    except json.JSONDecodeError:
                        pass
            await asyncio.sleep(0.3)

        return {"success": False, "error": "init timeout"}

    def _resolve_session(self, session_id: Optional[str]) -> Optional[str]:
        if session_id:
            if session_id in self.sessions:
                return session_id
            for sid, info in self.sessions.items():
                if info.get("label", "").lower() == session_id.lower():
                    return sid
            for sid, info in self.sessions.items():
                if session_id.lower() in info.get("label", "").lower():
                    return sid
            return session_id
        return self._active_session_id

    def _read_meta(self, session_id: str) -> dict:
        meta_file = self._session_dir(session_id) / "meta.json"
        if meta_file.exists():
            try:
                return json.loads(meta_file.read_text())
            except Exception:
                pass
        return {}

    def _write_meta(self, session_id: str, meta: dict) -> None:
        meta_file = self._session_dir(session_id) / "meta.json"
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    def get_config_schema(self) -> dict:
        return {
            "model": "Model ID, e.g. custom:ZAI-GLM-5.1-0",
            "auto_level": "Autonomy level low/medium/high",
            "cwd": "Working directory",
            "reasoning_effort": "Reasoning depth",
        }

    def _parse_output(self, lines: list[str], last_line: int) -> dict:
        """Parse new lines from output.jsonl and return structured results.

        Returns:
            {
                "new_messages": [{"role": "user"|"assistant", "text": "..."}],
                "working_state": "working"|"idle"|"unknown",
                "total_lines": int,
            }
        """
        new_lines = lines[last_line:]
        total = len(lines)

        if not new_lines:
            return {"new_messages": [], "working_state": "unknown", "total_lines": total}

        new_messages = []
        assistant_parts: list[str] = []
        working_state = "unknown"

        for line in new_lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type", "")

            if msg_type == "response":
                result = obj.get("result", {})
                if "finalText" in result:
                    new_messages.append({"role": "assistant", "text": result["finalText"]})
                elif "error" in obj:
                    new_messages.append({"role": "error", "text": obj["error"].get("message", "unknown")})

            elif msg_type == "notification":
                params = obj.get("params", {})
                notif = params.get("notification", {})
                ntype = notif.get("type", "")

                if ntype in self.NOISE_TYPES:
                    continue

                if ntype == "assistant_text_delta":
                    assistant_parts.append(notif.get("textDelta", ""))

                elif ntype == "assistant_text_complete":
                    if assistant_parts:
                        new_messages.append({"role": "assistant_delta", "text": "".join(assistant_parts)})
                        assistant_parts = []

                elif ntype == "create_message":
                    msg = notif.get("message", {})
                    role = msg.get("role", "")
                    content = msg.get("content", [])
                    if role in ("user", "assistant") and isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                new_messages.append({"role": role, "text": block["text"]})

                elif ntype == "tool_use":
                    new_messages.append({"role": "tool_use", "text": notif.get("name", "unknown")})

                elif ntype == "droid_working_state_changed":
                    state = notif.get("newState", "")
                    if state == "idle":
                        working_state = "idle"
                    elif state in ("streaming_assistant_message", "tool_call"):
                        working_state = "working"

        return {"new_messages": new_messages, "working_state": working_state, "total_lines": total}

    def get_tools(self):
        return [
            (self._tool_start_session, "start_session",
             "Start a Droid session. Supports full toolchain (file read/write, terminal execution, search, etc.).",
             [("model", "Optional[str]", None, "Model ID, e.g. custom:ZAI-GLM-5.1-0"),
              ("auto_level", "str", "high", "Autonomy level low/medium/high"),
              ("cwd", "Optional[str]", None, "Working directory"),
              ("session_id", "Optional[str]", None, "Session ID to resume"),
              ("label", "Optional[str]", None, "Session label")]),
            (self.send_message, "send_message",
             "Send a message to a Droid session. Use poll_output to get the reply.",
             [("session_id", "Optional[str]", None, "Session ID or label; uses active session if omitted"),
              ("message", "str", "", "Message content")]),
            (self.poll_output, "poll_output",
             "Get the latest output from a Droid session. Returns full reply text and working state.",
             [("session_id", "Optional[str]", None, "Session ID or label"),
              ("last_line", "int", 0, "Previous total_lines value for incremental reading")]),
            (self.check_status, "check_status",
             "Check session status. Lists all sessions if session_id is not provided.",
             [("session_id", "Optional[str]", None, "Session ID or label")]),
            (self._tool_stop_session, "stop_session",
             "Stop the specified session.",
             [("session_id", "Optional[str]", None, "Session ID or label")]),
            (self._tool_exec_and_wait, "exec_and_wait",
             "One-shot execution: create session -> send message -> wait for completion -> return results.",
             [("message", "str", None, "Task description"),
              ("timeout", "int", 300, "Timeout in seconds"),
              ("cwd", "Optional[str]", None, "Working directory"),
              ("label", "Optional[str]", None, "Session label")]),
            (self.interrupt_session, "interrupt_session",
             "Interrupt the currently running task (sends SIGINT), preserving session context.",
             [("session_id", "Optional[str]", None, "Session ID or label")]),
            (self.get_history, "get_history",
             "View session conversation history.",
             [("session_id", "Optional[str]", None, "Session ID or label"),
              ("limit", "int", 50, "Return the last N entries")]),
        ]

    async def _tool_start_session(self, model=None, auto_level="high", cwd=None,
                                   session_id=None, label=None) -> dict:
        config = {
            "model": model, "auto_level": auto_level, "cwd": cwd,
            "workdir": cwd, "session_id": session_id, "label": label,
        }
        return await self.start_session(config)

    async def _tool_stop_session(self, session_id=None) -> dict:
        sid = self._resolve_session(session_id)
        if not sid:
            return {"error": "No active session"}
        return await self.stop_session(sid)

    async def _tool_exec_and_wait(self, message, timeout=300, cwd=None, label=None) -> dict:
        config = {"cwd": cwd, "workdir": cwd, "label": label}
        return await self.exec_and_wait(message, timeout, config)

    async def start_session(self, config: dict) -> dict:
        model = config.get("model") or self.default_config.get("model", "custom:ZAI-GLM-5.1-0")
        auto_level = config.get("auto_level") or self.default_config.get("auto_level", "high")
        cwd = config.get("cwd") or config.get("workdir") or self.default_config.get("cwd", str(self.workspace_dir))
        reasoning = config.get("reasoning_effort") or self.default_config.get("reasoning_effort", "")
        session_id = config.get("session_id")
        label = config.get("label", "")

        if session_id and session_id in self.sessions:
            proc = self.sessions[session_id]["proc"]
            if self._is_alive(proc):
                self._active_session_id = session_id
                return {"session_id": session_id, "status": "running", "pid": proc.pid}

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
            "label": label,
        }

        (sdir / "pid").write_text(str(proc.pid))
        if label:
            self._write_meta(sid, {"label": label})
        self._renew(sid)

        if not session_id:
            init_result = await self._wait_for_init(sid)
            if not init_result.get("success"):
                await self.stop_session(sid)
                return {"error": f"droid init failed: {init_result.get('error', 'unknown')}"}

        self._active_session_id = sid
        self._lease(sid, self._idle_timeout, lambda sid=sid: asyncio.ensure_future(self.stop_session(sid)))
        result = {"session_id": sid, "status": "started", "pid": proc.pid}
        if label:
            result["label"] = label
        return result

    async def send_message(self, session_id: Optional[str], message: str) -> dict:
        session_id = self._resolve_session(session_id)
        if not session_id:
            return {"error": "No active session. Call start_session first."}
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

        self._renew(session_id)
        msg_id = f"msg-{ts}"
        return {"status": "sent", "session_id": session_id, "msg_id": msg_id}

    async def poll_output(self, session_id: Optional[str] = None, last_line: int = 0) -> dict:
        """Get the latest output from a Droid session.

        Returns:
            {
                "messages": [{"role": "user"|"assistant"|"tool_use", "text": "..."}],
                "working_state": "working"|"idle"|"unknown",
                "total_lines": int,     // Pass this value as last_line in the next call
            }
        """
        session_id = self._resolve_session(session_id)
        if not session_id:
            return {"error": "No active session. Call start_session first."}
        self._renew(session_id)

        output_file = self._session_dir(session_id) / "output.jsonl"
        if not output_file.exists():
            return {"messages": [], "working_state": "unknown", "total_lines": 0}

        all_lines = output_file.read_text().splitlines()
        if not all_lines:
            return {"messages": [], "working_state": "unknown", "total_lines": 0}

        parsed = self._parse_output(all_lines, last_line)

        final_messages = []
        for m in parsed["new_messages"]:
            if m["role"] == "assistant_delta":
                final_messages.append(m)
            else:
                final_messages.append(m)

        seen_assistant = set()
        deduped = []
        for m in reversed(final_messages):
            if m["role"] == "assistant" and m.get("text"):
                key = m["text"][:80]
                if key not in seen_assistant:
                    seen_assistant.add(key)
                    deduped.insert(0, m)
            elif m["role"] == "assistant_delta":
                continue
            else:
                deduped.insert(0, m)

        return {
            "messages": deduped,
            "working_state": parsed["working_state"],
            "total_lines": parsed["total_lines"],
        }

    async def check_status(self, session_id: Optional[str] = None) -> dict:
        if session_id:
            session_id = self._resolve_session(session_id)
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

            result = {
                "session_id": session_id,
                "alive": self._is_alive(proc),
                "pid": proc.pid,
                "model": info["model"],
                "auto_level": info["auto_level"],
                "cwd": info["cwd"],
                "started_at": info["started_at"],
                "output_lines": msg_count,
                "tail_alive": tail is not None and self._is_alive(tail) if tail else False,
                "active": session_id == self._active_session_id,
            }
            if info.get("label"):
                result["label"] = info["label"]
            return result

        result = []
        for sid, info in self.sessions.items():
            proc = info["proc"]
            output_file = self._session_dir(sid) / "output.jsonl"
            msg_count = 0
            if output_file.exists():
                msg_count = len(output_file.read_text().splitlines())
            entry = {
                "session_id": sid,
                "alive": self._is_alive(proc),
                "model": info["model"],
                "started_at": info["started_at"],
                "output_lines": msg_count,
                "active": sid == self._active_session_id,
            }
            if info.get("label"):
                entry["label"] = info["label"]
            result.append(entry)
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
        self._release(session_id)
        if self._active_session_id == session_id:
            self._active_session_id = None
        return {"status": "stopped", "session_id": session_id}

    async def _wait_for_completion(self, session_id: str, timeout: int, msg_id: str) -> dict:
        import time
        start = time.time()
        all_text = []
        last_line = 0
        response_received = False

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

            proc_dead = not self._is_alive(info["proc"])

            output_file = self._session_dir(session_id) / "output.jsonl"
            if output_file.exists():
                lines = output_file.read_text().splitlines()
                new_lines = lines[last_line:]
                for line in new_lines:
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "response" and obj.get("id") == msg_id:
                            result = obj.get("result", {})
                            if "finalText" in result:
                                all_text.append(result["finalText"])
                            if "error" in obj:
                                return {"success": False, "error": obj["error"].get("message", "unknown"),
                                        "output": "\n".join(all_text), "session_id": session_id,
                                        "duration_seconds": int(time.time() - start)}
                            response_received = True
                        elif obj.get("type") == "response" and obj.get("id") == "init-1":
                            pass
                        elif obj.get("type") == "notification":
                            params = obj.get("params", {})
                            notif = params.get("notification", {})
                            ntype = notif.get("type", "")
                            if ntype == "create_message":
                                msg = notif.get("message", {})
                                role = msg.get("role", "")
                                content = msg.get("content", [])
                                if role == "assistant" and isinstance(content, list):
                                    for block in content:
                                        if isinstance(block, dict) and block.get("type") == "text":
                                            all_text.append(block["text"])
                    except json.JSONDecodeError:
                        pass
                last_line = len(lines)

            if response_received:
                await self.stop_session(session_id)
                elapsed = time.time() - start
                return {"success": True, "output": "\n".join(all_text),
                        "session_id": session_id, "duration_seconds": int(elapsed)}

            if proc_dead:
                await self.stop_session(session_id)
                elapsed = time.time() - start
                return {"success": True, "output": "\n".join(all_text),
                        "session_id": session_id, "duration_seconds": int(elapsed)}

            await asyncio.sleep(0.5)

    async def exec_and_wait(self, message: str, timeout: int, config: dict) -> dict:
        start_result = await self.start_session(config)
        if "error" in start_result:
            return start_result
        session_id = start_result["session_id"]

        send_result = await self.send_message(session_id, message)
        if "error" in send_result:
            await self.stop_session(session_id)
            return send_result

        msg_id = send_result.get("msg_id", "")
        return await self._wait_for_completion(session_id, timeout, msg_id)

    async def interrupt_session(self, session_id: Optional[str] = None) -> dict:
        session_id = self._resolve_session(session_id)
        if not session_id:
            return {"error": "No active session"}
        info = self.sessions.get(session_id)
        if not info:
            return {"error": f"Session {session_id} not found"}

        proc = info["proc"]
        if not self._is_alive(proc):
            return {"status": "process_exited", "session_id": session_id}

        try:
            proc.send_signal(signal.SIGINT)
        except (ProcessLookupError, PermissionError):
            return {"status": "process_exited", "session_id": session_id}

        await asyncio.sleep(1.0)
        alive = self._is_alive(proc)
        return {
            "status": "interrupt_sent" if alive else "process_exited",
            "alive": alive,
            "session_id": session_id,
        }

    async def get_history(self, session_id: Optional[str] = None, limit: int = 50) -> dict:
        session_id = self._resolve_session(session_id)
        if not session_id:
            return {"error": "No active session"}

        output_file = self._session_dir(session_id) / "output.jsonl"
        if not output_file.exists():
            return {"messages": [], "session_id": session_id}

        lines = output_file.read_text().splitlines()
        parsed = self._parse_output(lines, 0)

        messages = []
        for m in parsed["new_messages"]:
            if m["role"] in ("user", "assistant", "error"):
                messages.append({"role": m["role"], "text": m["text"]})

        if limit > 0:
            messages = messages[-limit:]

        return {"messages": messages, "count": len(messages), "session_id": session_id}
