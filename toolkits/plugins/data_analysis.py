import io
import os
import json
from pathlib import Path
from typing import Optional

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from toolkits.base import BaseToolkit


class DataAnalysisToolkit(BaseToolkit):
    """DataAnalysis Toolkit - CSV/JSON data analysis."""

    name = "data_analysis"
    description = "Data analysis toolkit - CSV query/statistics/visualization, JSON query"

    CHART_DIR = "/tmp/data_analysis_charts"

    def __init__(self, ctx: dict = None):
        super().__init__()
        ctx = ctx or {}
        base = ctx.get("base_dir", ".")
        self.workspace_dir = Path(base) / "workspace"
        os.makedirs(self.CHART_DIR, exist_ok=True)

    def get_config_schema(self) -> dict:
        return {
            "workspace_dir": "Working directory, defaults to project workspace",
        }

    def get_tools(self):
        return [
            (self.csv_info, "csv_info",
             "获取 CSV 文件基本信息（行数、列名、类型、缺失值统计）。",
             [("file_path", "str", None, "CSV 文件路径"),
              ("encoding", "str", "utf-8", "文件编码")]),
            (self.csv_analyze, "csv_analyze",
             "对 CSV 指定列做统计分析（均值、中位数、分位数、分布等）。",
             [("file_path", "str", None, "CSV 文件路径"),
              ("columns", "Optional[str]", None, "要分析的列，逗号分隔"),
              ("group_by", "Optional[str]", None, "分组列名"),
              ("agg", "str", "mean", "聚合方式 mean/sum/count/min/max/std/median"),
              ("encoding", "str", "utf-8", "文件编码")]),
            (self.csv_query, "csv_query",
             "用 pandas 表达式筛选/过滤/排序 CSV 数据。支持 SQL 风格的查询。",
             [("file_path", "str", None, "CSV 文件路径"),
              ("select", "str", "*", "返回列，逗号分隔，如 'name,age,score'"),
              ("where", "Optional[str]", None, "过滤表达式，如 'age > 18 and score >= 60'"),
              ("order_by", "Optional[str]", None, "排序列，加前缀 desc 表示降序，如 'score desc'"),
              ("limit", "int", 100, "返回行数上限"),
              ("encoding", "str", "utf-8", "文件编码")]),
            (self.csv_chart, "csv_chart",
             "用 matplotlib 生成图表并保存为 PNG。支持折线/柱状/散点/饼/直方图。",
             [("file_path", "str", None, "CSV 文件路径"),
              ("chart_type", "str", None, "图表类型: line(折线)/bar(柱状)/scatter(散点)/pie(饼)/hist(直方)"),
              ("x", "str", None, "X 轴列名"),
              ("y", "Optional[str]", None, "Y 轴列名（pie/hist 可不传）"),
              ("title", "Optional[str]", None, "图表标题"),
              ("limit", "int", 500, "最大数据点数"),
              ("encoding", "str", "utf-8", "文件编码")]),
            (self.json_query, "json_query",
             "解析 JSON 文件，支持字典路径查询。",
             [("file_path", "str", None, "JSON 文件路径"),
              ("path", "str", ".", "查询路径"),
              ("pretty", "bool", True, "是否格式化输出"),
              ("encoding", "str", "utf-8", "文件编码")]),
        ]

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve file path, supports relative paths (based on workspace)."""
        p = Path(file_path)
        if not p.is_absolute():
            p = self.workspace_dir / p
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {p}")
        return p

    def _safe_df(self, df: pd.DataFrame, max_rows: int = 200) -> dict:
        """Safely serialize DataFrame to dict, truncating long data."""
        total = len(df)
        show = df.head(max_rows)
        return {
            "data": json.loads(show.to_json(orient="records", force_ascii=False)),
            "total_rows": total,
            "shown_rows": len(show),
            "columns": list(df.columns),
        }

    async def csv_info(self, file_path: str, encoding: str = "utf-8") -> dict:
        """Get basic CSV file information."""
        try:
            p = self._resolve_path(file_path)
            df = pd.read_csv(p, encoding=encoding)

            info = {
                "file": str(p),
                "file_size_bytes": p.stat().st_size,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
                "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
                "null_counts": {col: int(df[col].isnull().sum()) for col in df.columns},
                "sample": json.loads(df.head(5).to_json(orient="records", force_ascii=False)),
            }
            return info
        except Exception as e:
            return {"error": str(e)}

    async def csv_analyze(
        self,
        file_path: str,
        columns: Optional[str] = None,
        group_by: Optional[str] = None,
        agg: str = "mean",
        encoding: str = "utf-8",
    ) -> dict:
        """Perform statistical analysis on CSV data."""
        try:
            p = self._resolve_path(file_path)
            df = pd.read_csv(p, encoding=encoding)

            if columns:
                col_list = [c.strip() for c in columns.split(",")]
                missing = [c for c in col_list if c not in df.columns]
                if missing:
                    return {"error": f"列不存在: {missing}", "available_columns": list(df.columns)}
                df = df[col_list]

            if group_by:
                if group_by not in df.columns:
                    return {"error": f"分组列不存在: {group_by}", "available_columns": list(df.columns)}
                numeric_cols = df.select_dtypes(include="number").columns.tolist()
                if group_by in numeric_cols:
                    numeric_cols.remove(group_by)
                if not numeric_cols:
                    return {"error": "没有可聚合的数值列"}
                result = df.groupby(group_by)[numeric_cols].agg(agg)
                return self._safe_df(result.reset_index())
            else:
                numeric_df = df.select_dtypes(include="number")
                if numeric_df.empty:
                    return {"error": "没有数值列可分析"}
                desc = numeric_df.describe().round(4)
                return self._safe_df(desc.reset_index().rename(columns={"index": "stat"}))
        except Exception as e:
            return {"error": str(e)}

    async def csv_query(
        self,
        file_path: str,
        select: str = "*",
        where: Optional[str] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        encoding: str = "utf-8",
    ) -> dict:
        """Query CSV data in SQL style."""
        try:
            p = self._resolve_path(file_path)
            df = pd.read_csv(p, encoding=encoding)

            if where:
                df = df.query(where)

            if select.strip() != "*":
                col_list = [c.strip() for c in select.split(",")]
                missing = [c for c in col_list if c not in df.columns]
                if missing:
                    return {"error": f"列不存在: {missing}", "available_columns": list(df.columns)}
                df = df[col_list]

            if order_by:
                parts = order_by.strip().rsplit(maxsplit=1)
                if len(parts) == 2 and parts[1].lower() == "desc":
                    df = df.sort_values(parts[0], ascending=False)
                else:
                    df = df.sort_values(order_by.strip())

            df = df.head(limit)

            return self._safe_df(df)
        except Exception as e:
            return {"error": str(e)}

    async def csv_chart(
        self,
        file_path: str,
        chart_type: str,
        x: str,
        y: Optional[str] = None,
        title: Optional[str] = None,
        limit: int = 500,
        encoding: str = "utf-8",
    ) -> dict:
        """Generate charts from CSV data visualization."""
        try:
            p = self._resolve_path(file_path)
            df = pd.read_csv(p, encoding=encoding).head(limit)

            fig, ax = plt.subplots(figsize=(10, 6))

            chart_type = chart_type.lower()

            if chart_type == "line":
                ax.plot(df[x], df[y], marker="o", markersize=3)
                ax.set_xlabel(x)
                ax.set_ylabel(y)
            elif chart_type == "bar":
                ax.bar(df[x].astype(str), df[y])
                ax.set_xlabel(x)
                ax.set_ylabel(y)
                plt.xticks(rotation=45, ha="right")
            elif chart_type == "scatter":
                ax.scatter(df[x], df[y], alpha=0.6)
                ax.set_xlabel(x)
                ax.set_ylabel(y)
            elif chart_type == "pie":
                counts = df[x].value_counts()
                ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
            elif chart_type == "hist":
                col = y or x
                ax.hist(df[col], bins=30, edgecolor="black")
                ax.set_xlabel(col)
                ax.set_ylabel("Frequency")
            else:
                return {"error": f"不支持的图表类型: {chart_type}，可选: line/bar/scatter/pie/hist"}

            if title:
                ax.set_title(title)
            else:
                ax.set_title(f"{chart_type} chart - {x}" + (f" vs {y}" if y else ""))

            plt.tight_layout()

            out_name = f"chart_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
            out_path = os.path.join(self.CHART_DIR, out_name)
            fig.savefig(out_path, dpi=150)
            plt.close(fig)

            return {
                "status": "ok",
                "chart_type": chart_type,
                "chart_path": out_path,
                "data_points": len(df),
            }
        except Exception as e:
            plt.close("all")
            return {"error": str(e)}

    async def json_query(
        self,
        file_path: str,
        path: str = ".",
        pretty: bool = True,
        encoding: str = "utf-8",
    ) -> dict:
        """Query JSON files with dictionary path style."""
        try:
            p = self._resolve_path(file_path)
            with open(p, "r", encoding=encoding) as f:
                data = json.load(f)

            if path and path != ".":
                result = self._resolve_json_path(data, path)
            else:
                result = data

            text = json.dumps(result, ensure_ascii=False, indent=2 if pretty else None)
            max_len = 50000
            truncated = False
            if len(text) > max_len:
                text = text[:max_len]
                truncated = True

            return {
                "result": text,
                "path": path,
                "type": type(result).__name__,
                "truncated": truncated,
            }
        except Exception as e:
            return {"error": str(e)}

    def _resolve_json_path(self, data, path: str):
        """Resolve simple JSON path, e.g. users[0].name."""
        import re
        parts = re.split(r"\.(?![^\[]*\])", path)
        current = data
        for part in parts:
            if not part:
                continue
            match = re.match(r"^(\w+)\[(\d+)\]$", part)
            if match:
                key, idx = match.group(1), int(match.group(2))
                current = current[key][idx]
            elif "[" in part:
                idx = int(re.search(r"\[(\d+)\]", part).group(1))
                current = current[idx]
            else:
                if isinstance(current, dict):
                    current = current[part]
                else:
                    return {"error": f"路径 {part} 无法解析，当前类型: {type(current).__name__}"}
        return current
