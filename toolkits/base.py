from abc import ABC, abstractmethod
from typing import Callable, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

ToolDef = tuple[Callable, str, str] | tuple[Callable, str, str, list]


class _Lease:
    __slots__ = ("key", "ttl", "cleanup", "task", "owner")

    def __init__(self, key: str, ttl: int, cleanup: Callable, owner: str):
        self.key = key
        self.ttl = ttl
        self.cleanup = cleanup
        self.owner = owner
        self.task: Optional[asyncio.Task] = None

    def start(self):
        self.cancel()
        self.task = asyncio.ensure_future(self._countdown())

    def cancel(self):
        if self.task and not self.task.done():
            self.task.cancel()

    async def _countdown(self):
        try:
            await asyncio.sleep(self.ttl)
            logger.info(f"[lease] {self.owner}/{self.key} expired (ttl={self.ttl}s), cleaning up")
            try:
                result = self.cleanup()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"[lease] {self.owner}/{self.key} cleanup error: {e}")
        except asyncio.CancelledError:
            pass


class BaseToolkit(ABC):
    name: str = ""
    description: str = ""

    def __init__(self):
        self._leases: dict[str, _Lease] = {}

    def _lease(self, key: str, ttl: int, cleanup: Callable):
        lease = _Lease(key, ttl, cleanup, self.name)
        self._leases[key] = lease
        lease.start()

    def _renew(self, key: str):
        lease = self._leases.get(key)
        if lease:
            lease.start()

    def _release(self, key: str):
        lease = self._leases.pop(key, None)
        if lease:
            lease.cancel()

    def shutdown(self):
        for key, lease in list(self._leases.items()):
            lease.cancel()
            try:
                result = lease.cleanup()
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(result)
                        else:
                            loop.run_until_complete(result)
                    except RuntimeError:
                        asyncio.ensure_future(result)
            except Exception as e:
                logger.warning(f"[shutdown] {self.name}/{key} cleanup error: {e}")
        self._leases.clear()
        logger.info(f"[shutdown] {self.name}: all leases released")

    def get_tools(self) -> list[ToolDef]:
        return []

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "config_schema": self.get_config_schema(),
            "tools": [t[1] for t in self.get_tools()],
            "tools_schema": self._build_tools_schema(),
        }

    def _build_tools_schema(self) -> list[dict]:
        import inspect as _insp

        schemas = []
        for entry in self.get_tools():
            fn, name, desc = entry[0], entry[1], entry[2]
            params = entry[3] if len(entry) > 3 else None

            if params is None:
                params = self._extract_params(fn)

            schemas.append({
                "name": name,
                "description": desc,
                "parameters": [
                    {"name": p[0], "type": p[1], "description": p[3]}
                    for p in params
                ],
            })
        return schemas

    @staticmethod
    def _extract_params(fn) -> list[tuple]:
        import inspect as _insp

        params = []
        sig = _insp.signature(fn)
        for pname, param in sig.parameters.items():
            if pname in ("self", "cls", "**_"):
                continue
            ann = param.annotation
            if ann is _insp.Parameter.empty:
                ptype = "str"
            elif hasattr(ann, "__origin__"):
                ptype = str(ann)
            else:
                ptype = getattr(ann, "__name__", str(ann))

            default = param.default
            if default is _insp.Parameter.empty:
                default = None

            params.append((pname, ptype, default, ""))
        return params

    @abstractmethod
    def get_config_schema(self) -> dict:
        pass

    def startup(self):
        pass
