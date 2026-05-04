"""
Opencode 工具包 - HTTP API 多轮会话模式

使用官方 API (https://opencode.ai/docs/server/)：
- POST /session - 创建会话
- POST /session/:id/message - 发送消息（同步返回响应）
- GET /session/:id/message - 获取消息列表
- DELETE /session/:id - 删除会话
"""

import asyncio
import subprocess
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from .base import BaseToolkit


class OpencodeToolkit(BaseToolkit):
    """Opencode 工具包 - HTTP API 多轮会话模式"""

    name = "opencode"
    description = "OpenCode - HTTP API 多轮会话模式（opencode serve）"

    # Opencode 二进制路径
    OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "opencode")

    # Opencode 免费模型列表
    FREE_MODELS = [
        "opencode/big-pickle",
        "opencode/minimax-m2.5-free",
        "opencode/ling-2.6-flash-free",
        "opencode/gpt-5-nano",
        "opencode/hy3-preview-free",
        "opencode/nemotron-3-super-free",
    ]

    def __init__(self, workspace_dir: Path, default_model: str = "opencode/big-pickle"):
        self.workspace_dir = workspace_dir
        self.server_process: Optional[subprocess.Popen] = None
        self.server_url: str = ""
        self.server_port: int = 0
        self.sessions: dict[str, dict] = {}
        self.http_client: Optional[httpx.AsyncClient] = None
        self._last_activity: float = 0
        self._idle_timeout = 1800  # 30 分钟无活动自动停止 serve
        self._gc_task: Optional[asyncio.Task] = None
        
        # 解析默认模型
        if default_model and "/" in default_model:
            parts = default_model.split("/")
            self.default_model = {"providerID": parts[0], "modelID": parts[1]}
        else:
            self.default_model = {"providerID": "opencode", "modelID": "big-pickle"}

    def start_gc(self):
        """启动后台回收任务"""
        if self._gc_task is None or self._gc_task.done():
            self._gc_task = asyncio.ensure_future(self._gc_loop())

    async def _gc_loop(self):
        """每 60 秒检查：无活动且无会话则停止 serve 进程"""
        import time
        while True:
            await asyncio.sleep(60)
            if not self.server_process or self.server_process.poll() is not None:
                continue
            now = time.time()
            # 有会话时不回收（会话可能在用）
            if self.sessions:
                continue
            # 无会话且空闲超时，停掉 serve
            if self._last_activity > 0 and now - self._last_activity > self._idle_timeout:
                await self._stop_server()
                print(f"[opencode-gc] Idle {int(now - self._last_activity)}s, stopped server")

    def _touch(self):
        """记录活动时间"""
        import time
        self._last_activity = time.time()

    def get_config_schema(self) -> dict:
        return {
            "port": "服务器端口，默认 4096",
            "workdir": "工作目录",
            "model": f"模型 ID，格式: provider/model。免费模型: {', '.join(self.FREE_MODELS[:3])} 等",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=300.0)  # 5分钟超时
        return self.http_client

    async def _start_server(self, port: int, workdir: str) -> dict:
        """启动 opencode serve 后台服务器"""
        if self.server_process and self.server_process.poll() is None:
            return {"status": "already_running", "url": self.server_url}

        cmd = [self.OPENCODE_BIN, "serve", "--port", str(port), "--hostname", "127.0.0.1"]
        self.server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workdir,
        )

        await asyncio.sleep(3)  # 等待服务器启动

        # 检查健康
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
        """停止服务器"""
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
        """创建 Opencode 会话"""
        self._touch()
        port = config.get("port", 4096)
        workdir = config.get("workdir") or config.get("cwd") or str(self.workspace_dir)
        model_str = config.get("model", "opencode/big-pickle")

        # 解析模型
        if model_str and "/" in model_str:
            parts = model_str.split("/")
            self.default_model = {"providerID": parts[0], "modelID": parts[1]}
        else:
            self.default_model = {"providerID": "opencode", "modelID": "big-pickle"}

        # 确保服务器运行
        if not self.server_url or self.server_port != port:
            result = await self._start_server(port, workdir)
            if "error" in result:
                return result

        client = await self._ensure_client()

        # 创建新 session
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
        """发送消息到 Opencode 会话（异步轮询模式）

        POST 消息后如果未立即返回，则轮询消息列表等待 AI 响应完成。
        """
        self._touch()
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
            # 记录发送前的消息数量
            try:
                count_resp = await client.get(f"{self.server_url}/session/{session_id}/message")
                msg_count_before = len(count_resp.json()) if count_resp.status_code == 200 else 0
            except Exception:
                msg_count_before = 0

            # POST 消息，短超时：如果 API 同步返回就直接拿结果
            try:
                resp = await client.post(
                    f"{self.server_url}/session/{session_id}/message",
                    json=body,
                    timeout=30.0
                )
                if resp.status_code == 200:
                    return self._parse_message_response(session_id, resp.json())
                # 非 200 但不是超时，直接报错
                if resp.status_code != 408:
                    return {"error": f"Failed to send message: {resp.status_code}", "body": resp.text[:200]}
            except httpx.TimeoutException:
                pass  # 超时了，走轮询
            except httpx.ConnectError as e:
                return {"error": f"Connection error: {e}"}

            # 轮询等待响应：消息数量增加且最后一条是 assistant 回复
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
                        # 取最后一条 assistant 消息
                        for msg in reversed(messages):
                            info = msg.get("info", {})
                            if info.get("role") == "assistant":
                                return self._parse_message_response(session_id, msg)
                        # 有新消息但还没 assistant 回复，继续等
                except Exception:
                    pass
                # 逐步增加轮询间隔，最大 5 秒
                poll_interval = min(poll_interval + 0.5, 5.0)

            return {"error": "timeout", "session_id": session_id, "detail": f"No response within {timeout}s, use poll_output to check"}

        except Exception as e:
            return {"error": f"Failed to send message: {e}"}

    def _parse_message_response(self, session_id: str, result: dict) -> dict:
        """解析 opencode 消息响应"""
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
        """获取会话消息列表"""
        self._touch()
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

                # 提取文本
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
        """检查会话状态"""
        client = await self._ensure_client()

        if not self.server_url:
            return {"error": "Server not started"}

        try:
            # 检查服务器健康
            resp = await client.get(f"{self.server_url}/global/health")
            health = resp.json()

            if session_id:
                if session_id not in self.sessions:
                    # 尝试从服务器获取
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

            # 列出所有 session
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
        """删除会话"""
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
        """一站式执行：创建会话 → 发送消息 → 返回响应"""
        import time
        start = time.time()

        # 1. 创建会话
        session_result = await self.start_session(config)
        if "error" in session_result:
            return session_result

        session_id = session_result["session_id"]

        # 2. 发送消息（同步 API 自动等待响应）
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

        # 3. 返回结果
        return {
            "success": True,
            "output": send_result.get("response", ""),
            "reasoning": send_result.get("reasoning", ""),
            "session_id": session_id,
            "message_id": send_result.get("message_id"),
            "duration_seconds": int(elapsed),
        }

    async def cleanup(self) -> dict:
        """清理所有资源"""
        # 删除所有本地会话
        for sid in list(self.sessions.keys()):
            try:
                await self.stop_session(sid)
            except:
                pass

        await self._stop_server()
        return {"status": "cleaned"}
