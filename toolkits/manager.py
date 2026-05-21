import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Optional

from .base import BaseToolkit


def _discover_plugins(plugin_dir: Path) -> list[type[BaseToolkit]]:
    if not plugin_dir.is_dir():
        return []

    classes = []

    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            mod_name = f"toolkits.plugins.{py_file.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, py_file)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseToolkit)
                    and attr is not BaseToolkit
                    and hasattr(attr, "name")
                    and attr.name
                ):
                    classes.append(attr)
        except Exception as e:
            print(f"[plugin] load {py_file.name} failed: {e}")

    for subdir in sorted(plugin_dir.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("_") or subdir.name == "__pycache__":
            continue
        if not (subdir / "__init__.py").exists():
            continue
        mod_name = f"toolkits.plugins.{subdir.name}"
        try:
            mod = importlib.import_module(mod_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseToolkit)
                    and attr is not BaseToolkit
                    and hasattr(attr, "name")
                    and attr.name
                ):
                    classes.append(attr)
        except Exception as e:
            print(f"[plugin] load {subdir.name}/ failed: {e}")

    return classes


class ToolkitManager:

    def __init__(self, base_dir: str):
        self._toolkits: dict[str, BaseToolkit] = {}
        self._current: Optional[str] = None
        self._base_dir = Path(base_dir)

        ctx = {"base_dir": str(self._base_dir)}

        plugin_dir = Path(__file__).parent / "plugins"
        for cls in _discover_plugins(plugin_dir):
            try:
                instance = cls(ctx)
                self.register(instance)
                print(f"[plugin] loaded: {instance.name}")
            except TypeError:
                try:
                    instance = cls()
                    self.register(instance)
                    print(f"[plugin] loaded: {instance.name}")
                except Exception as e:
                    print(f"[plugin] instantiate {cls.__name__} failed: {e}")
            except Exception as e:
                print(f"[plugin] instantiate {cls.__name__} failed: {e}")

    def startup_all(self):
        for tk in self._toolkits.values():
            try:
                tk.startup()
            except Exception as e:
                print(f"[plugin] {tk.name} startup failed: {e}")

    def shutdown_all(self):
        for tk in self._toolkits.values():
            try:
                tk.shutdown()
            except Exception as e:
                print(f"[plugin] {tk.name} shutdown failed: {e}")

    def register(self, toolkit: BaseToolkit):
        self._toolkits[toolkit.name] = toolkit

    def list_toolkits(self) -> list[dict]:
        return [t.get_info() for t in self._toolkits.values()]

    def switch(self, name: str, config: dict) -> dict:
        if name not in self._toolkits:
            return {
                "error": f"Toolkit {name} not found",
                "available": list(self._toolkits.keys()),
            }

        old = self._current
        self._current = name
        toolkit = self._toolkits[name]

        result = {
            "status": "switched",
            "from": old,
            "to": name,
            "toolkit": toolkit.get_info(),
            "tools_schema": toolkit._build_tools_schema(),
        }

        if config:
            result["config_applied"] = config

        return result

    def current(self) -> dict:
        if self._current is None:
            return {
                "current": None,
                "toolkit": None,
                "hint": "Use toolkit_switch to switch to a target toolkit",
            }
        toolkit = self._toolkits[self._current]
        return {
            "current": self._current,
            "toolkit": toolkit.get_info(),
        }

    def get(self) -> Optional[BaseToolkit]:
        if self._current is None:
            return None
        return self._toolkits[self._current]
