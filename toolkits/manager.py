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
        # NOTE: per-session state removed — toolkit switching is now handled
        # by FastMCP Context (get_state/set_state/enable_components/disable_components)
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

    # ── Legacy per-session methods (removed) ──────────────────
    # switch(), current(), get() — now handled by FastMCP Context
    # in server.py: toolkit_switch / toolkit_current tools
