import asyncio
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from toolkits.base import BaseToolkit


class OpencodeToolkit(BaseToolkit):
    """Opencode Toolkit - HTTP API multi-turn session mode"""

    name = "opencode"
    description = "OpenCode - HTTP API 多轮会话模式（opencode serve）"

    OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "/root/.opencode/bin/opencode")

    FREE_MODELS = [
        "opencode/big-pickle",
        "opencode/minimax-m2.5-free",
        "opencode/ling-2.6-flash-free",
        "opencode/gpt-5-nano",
        "opencode/hy3-preview-free",
        "opencode/nemotron-3-super-free",
    ]

    def __init__(self, ctx: dict = None):
        super().__init__()
        ctx = ctx or {}
        base = ctx.get("base_dir", "/tmp/jenny-droid")
        self.workspace_dir = Path(base) / "workspace"
        self.server_process: Optional[subprocess.Popen] = None
        self.server_url: str = ""
        self.server_port: int = 0
        self.sessions: dict[str, dict] = {}
        self.http_client: Optional[httpx.AsyncClient] = None
        self._idle_timeout = 1800
        self.default_model = {"providerID": "opencode", "modelID": "big-pickle"}

    def startup(self):
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        print(f"[opencode] startup: workspace={self.workspace_dir}")

    def _mark_active(self):
        if self.sessions and self.server_process and self.server_process.poll() is None:
            self._lease("serve", self._idle_timeout, self._auto_stop_serve_if_idle)

    async def _auto_stop_serve_if_idle(self):
        if not self.sessions:
            await self._stop_server()
            print(f"[opencode] serve idle {self._idle_timeout}s, stopped")

    def get_config_schema(self) -> dict:
        return {
            "port": "服务器端口，默认 4096",
            "workdir": "工作目录",
            "model": f"模型 ID，格式: provider/model。免费模型: {', '.join(self.FREE_MODELS[:3])} 等",
        }

    def get_tools(self):
        return [
            (self._tool_start_session, "start_session",
             "创建 OpenCode 会话。自动启动后台 serve 进程。",
             [("model", "str", "opencode/big-pickle", "模型 ID"),
              ("cwd", "Optional[str]", None, "工作目录"),
              ("port", "int", 4096, "服务器端口")]),
            (self.send_message, "send_message",
             "向 OpenCode 会话发送消息。异步模式，自动轮询等待结果。",
             [("session_id", "str", None, "会话 ID"),
              ("message", "str", None, "消息内容")]),
            (self.poll_output, "poll_output",
             "获取 OpenCode 会话的消息列表。",
             [("session_id", "str", None, "会话 ID"),
              ("last_line", "int", 0, "上次读取到的行号")]),
            (self.check_status, "check_status",
             "检查会话或服务器状态。",
             [("session_id", "Optional[str]", None, "会话 ID")]),
            (self.stop_session, "stop_session",
             "删除 Opencode 会话。",
             [("session_id", "str", None, "会话 ID")]),
            (self._tool_exec_and_wait, "exec_and_wait",
             "一站式执行：创建会话 → 发送消息 → 返回响应。",
             [("message", "str", None, "任务描述"),
              ("timeout", "int", 300, "超时秒数"),
              ("cwd", "Optional[str]", None, "工作目录")]),
            (self._tool_cleanup, "cleanup",
             "清理 Opencode 资源（停止服务器）。",
             []),
        ]

    async def _tool_start_session(self, model="opencode/big-pickle", cwd=None, port=4096) -> dict:
        config = {"model": model, "workdir": cwd, "cwd": cwd, "port": port}
        return await self.start_session(config)

    async def _tool_exec_and_wait(self, message, timeout=300, cwd=None) -> dict:
        config = {"workdir": cwd, "cwd": cwd}
        return await self.exec_and_wait(message, timeout, config)

    async def _tool_cleanup(self) -> dict:
        return await self.cleanup()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=300.0)
        return self.http_client

    async def _start_server(self, port: int, workdir: str) -> dict:
        if self.server_process and self.server_process.poll() is None:
            return {"status": "already_running", "url": self.server_url}

        cmd = [self.OPENCODE_BIN, "serve", "--port", str(port), "--hostname", "127.0.0.1"]
        self.server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workdir,
        )

        await asyncio.sleep(3)

        client = await self._ensure_client()
        try:
            resp = await client.get(f"http://127.0.0.1:{port}/global/health")
            if resp.status_code == 200:
                self.server_url = f"http://127.0.0.1:{port}"
                self.server_port = port
                return {"status": "started", "url": self.server_url, "pid": self.server_process.pid}
        except Exception as e:
            return {"error": f"Failed to start server: {e}"}

        return {"error": "Server not responding"}

    async def _stop_server(self) -> dict:
        self._release("serve")
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            self.server_process = None
            self.server_url = ""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        return {"status": "stopped"}

    async def start_session(self, config: dict) -> dict:
        self._mark_active()
        port = config.get("port", 4096)
        workdir = config.get("workdir") or config.get("cwd") or str(self.workspace_dir)
        model_str = config.get("model", "opencode/big-pickle")

        if model_str and "/" in model_str:
            parts = model_str.split("/")
            self.default_model = {"providerID": parts[0], "modelID": parts[1]}
        else:
            self.default_model = {"providerID": "opencode", "modelID": "big-pickle"}

        if not self.server_url or self.server_port != port:
            result = await self._start_server(port, workdir)
            if "error" in result:
                return result

        client = await self._ensure_client()

        try:
            resp = await client.post(
                f"{self.server_url}/session",
                json={"title": f"jenny-session-{datetime.now().strftime('%H%M%S')}"}
            )
            if resp.status_code != 200:
                return {"error": f"Failed to create session: {resp.status_code}", "body": resp.text[:200]}

            session_data = resp.json()
            sid = session_data.get("id")

            self.sessions[sid] = {
                "id": sid,
                "directory": workdir,
                "title": session_data.get("title", ""),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "server_url": self.server_url,
            }

            return {
                "session_id": sid,
                "status": "created",
                "url": self.server_url,
                "title": session_data.get("title", ""),
            }
        except Exception as e:
            return {"error": f"Failed to create session: {e}"}

    async def send_message(self, session_id: str, message: str, timeout: int = 120) -> dict:
        """Send a message to an Opencode session (async polling mode).

        After POSTing the message, if no immediate response is returned,
        polls the message list until the AI response is complete.
        """
        self._mark_active()
        if session_id not in self.sessions:
            return {"error": f"Session {session_id} not found"}

        if not self.server_url:
            return {"error": "Server not started"}

        client = await self._ensure_client()

        body = {
            "parts": [{"type": "text", "text": message}]
        }
        if self.default_model:
            body["model"] = self.default_model

        try:
            try:
                count_resp = await client.get(f"{self.server_url}/session/{session_id}/message")
                msg_count_before = len(count_resp.json()) if count_resp.status_code == 200 else 0
            except Exception:
                msg_count_before = 0

            try:
                resp = await client.post(
                    f"{self.server_url}/session/{session_id}/message",
                    json=body,
                    timeout=30.0
                )
                if resp.status_code == 200:
                    return self._parse_message_response(session_id, resp.json())
                if resp.status_code != 408:
                    return {"error": f"Failed to send message: {resp.status_code}", "body": resp.text[:200]}
            except httpx.TimeoutException:
                pass
            except httpx.ConnectError as e:
                return {"error": f"Connection error: {e}"}

            import time
            deadline = time.time() + timeout
            poll_interval = 2.0

            while time.time() < deadline:
                await asyncio.sleep(poll_interval)
                try:
                    poll_resp = await client.get(f"{self.server_url}/session/{session_id}/message")
                    if poll_resp.status_code != 200:
                        continue
                    messages = poll_resp.json()
                    if len(messages) > msg_count_before:
                        for msg in reversed(messages):
                            info = msg.get("info", {})
                            if info.get("role") == "assistant":
                                return self._parse_message_response(session_id, msg)
                except Exception:
                    pass
                poll_interval = min(poll_interval + 0.5, 5.0)

            return {"error": "timeout", "session_id": session_id, "detail": f"No response within {timeout}s, use poll_output to check"}

        except Exception as e:
            return {"error": f"Failed to send message: {e}"}

    def _parse_message_response(self, session_id: str, result: dict) -> dict:
        info = result.get("info", {})
        parts = result.get("parts", [])

        response_text = ""
        reasoning_text = ""
        tool_calls = []

        for part in parts:
            ptype = part.get("type", "")
            if ptype == "text":
                response_text += part.get("text", "")
            elif ptype == "reasoning":
                reasoning_text = part.get("text", "")
            elif ptype == "tool_use":
                tool_calls.append({
                    "name": part.get("name", "unknown"),
                    "input": part.get("input", {}),
                })
            elif ptype == "tool_result":
                tool_calls.append({
                    "name": part.get("name", "unknown"),
                    "result": part.get("result", ""),
                })

        return {
            "status": "sent",
            "session_id": session_id,
            "message_id": info.get("id"),
            "response": response_text.strip(),
            "reasoning": reasoning_text,
            "tool_calls": tool_calls,
            "tokens": info.get("tokens", {}),
            "model": f"{info.get('providerID', '')}/{info.get('modelID', '')}",
        }

    async def poll_output(self, session_id: str, last_line: int = 0) -> dict:
        """Get the message list for a session."""
        self._mark_active()
        if session_id not in self.sessions:
            return {"error": f"Session {session_id} not found"}

        if not self.server_url:
            return {"error": "Server not started"}

        client = await self._ensure_client()

        try:
            resp = await client.get(f"{self.server_url}/session/{session_id}/message")
            if resp.status_code != 200:
                return {"error": f"Failed to get messages: {resp.status_code}"}

            messages = resp.json()
            total = len(messages)

            if last_line >= total:
                return {"lines": [], "total_lines": total}

            new_messages = messages[last_line:]
            results = []

            for msg in new_messages:
                info = msg.get("info", {})
                parts = msg.get("parts", [])

                entry = {
                    "message_id": info.get("id"),
                    "role": info.get("role", "unknown"),
                }

                text_parts = []
                for part in parts:
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif part.get("type") == "tool_use":
                        text_parts.append(f"[tool: {part.get('name', 'unknown')}]")
                    elif part.get("type") == "tool_result":
                        text_parts.append(f"[tool_result]")

                entry["text"] = "\n".join(text_parts)
                results.append(entry)

            return {"lines": results, "total_lines": total}
        except Exception as e:
            return {"error": f"Failed to poll output: {e}"}

    async def check_status(self, session_id: Optional[str] = None) -> dict:
        """Check session status."""
        client = await self._ensure_client()

        if not self.server_url:
            return {"error": "Server not started"}

        try:
            resp = await client.get(f"{self.server_url}/global/health")
            health = resp.json()

            if session_id:
                if session_id not in self.sessions:
                    resp = await client.get(f"{self.server_url}/session/{session_id}")
                    if resp.status_code == 200:
                        session_data = resp.json()
                        return {
                            "session_id": session_id,
                            "title": session_data.get("title"),
                            "directory": session_data.get("directory"),
                            "server_url": self.server_url,
                            "server_health": health,
                        }
                    return {"error": f"Session {session_id} not found"}

                info = self.sessions[session_id]
                return {
                    "session_id": session_id,
                    "directory": info.get("directory"),
                    "started_at": info.get("started_at"),
                    "server_url": self.server_url,
                    "server_health": health,
                }

            resp = await client.get(f"{self.server_url}/session")
            remote_sessions = resp.json()

            return {
                "server_url": self.server_url,
                "server_health": health,
                "server_pid": self.server_process.pid if self.server_process else None,
                "local_sessions": list(self.sessions.keys()),
                "remote_sessions": [{"id": s.get("id"), "title": s.get("title")} for s in remote_sessions],
            }
        except Exception as e:
            return {"error": f"Failed to check status: {e}"}

    async def stop_session(self, session_id: str) -> dict:
        """Delete a session."""
        if session_id not in self.sessions:
            return {"error": f"Session {session_id} not found"}

        client = await self._ensure_client()

        try:
            resp = await client.delete(f"{self.server_url}/session/{session_id}")
            del self.sessions[session_id]
            return {"status": "stopped", "session_id": session_id, "deleted": resp.status_code == 200}
        except Exception as e:
            del self.sessions[session_id]
            return {"status": "stopped", "session_id": session_id, "error": str(e)}

    async def exec_and_wait(self, message: str, timeout: int, config: dict) -> dict:
        import time
        start = time.time()

        session_result = await self.start_session(config)
        if "error" in session_result:
            return session_result

        session_id = session_result["session_id"]

        send_result = await self.send_message(session_id, message)
        elapsed = time.time() - start

        if "error" in send_result:
            await self.stop_session(session_id)
            return {
                "success": False,
                "error": send_result.get("error"),
                "session_id": session_id,
                "duration_seconds": int(elapsed),
            }

        return {
            "success": True,
            "output": send_result.get("response", ""),
            "reasoning": send_result.get("reasoning", ""),
            "session_id": session_id,
            "message_id": send_result.get("message_id"),
            "duration_seconds": int(elapsed),
        }

    async def cleanup(self) -> dict:
        for sid in list(self.sessions.keys()):
            try:
                await self.stop_session(sid)
            except:
                pass

        await self._stop_server()
        return {"status": "cleaned"}
