"""
DataAnalysis 工具包 - CSV/JSON 数据分析

提供五个工具：
- csv_info: CSV 文件基本信息（行数、列名、类型、缺失值统计）
- csv_analyze: CSV 数据统计分析（describe、分组聚合）
- csv_query: SQL 风格查询 CSV 数据
- csv_chart: CSV 数据可视化（折线图、柱状图、散点图、饼图）
- json_query: JSON 文件查询（JMESPath / JSONPath 风格）
"""

import io
import os
import json
from pathlib import Path
from typing import Optional

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 无头模式
import matplotlib.pyplot as plt

from .base import BaseToolkit


class DataAnalysisToolkit(BaseToolkit):
    """DataAnalysis 工具包 - CSV/JSON 数据分析"""

    name = "data_analysis"
    description = "数据分析工具包 - CSV 查询/统计/可视化，JSON 查询"

    # 输出图表保存目录
    CHART_DIR = "/tmp/data_analysis_charts"

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = Path(workspace_dir)
        os.makedirs(self.CHART_DIR, exist_ok=True)

    def get_config_schema(self) -> dict:
        return {
            "workspace_dir": "工作目录，默认为项目 workspace",
        }

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _resolve_path(self, file_path: str) -> Path:
        """解析文件路径，支持相对路径（基于 workspace）"""
        p = Path(file_path)
        if not p.is_absolute():
            p = self.workspace_dir / p
        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {p}")
        return p

    def _safe_df(self, df: pd.DataFrame, max_rows: int = 200) -> dict:
        """将 DataFrame 安全序列化为 dict，截断过长的数据"""
        total = len(df)
        show = df.head(max_rows)
        return {
            "data": json.loads(show.to_json(orient="records", force_ascii=False)),
            "total_rows": total,
            "shown_rows": len(show),
            "columns": list(df.columns),
        }

    # ------------------------------------------------------------------
    # 工具实现
    # ------------------------------------------------------------------

    async def csv_info(self, file_path: str, encoding: str = "utf-8") -> dict:
        """获取 CSV 文件基本信息"""
        try:
            p = self._resolve_path(file_path)
            df = pd.read_csv(p, encoding=encoding)

            # 基本信息
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
        """CSV 数据统计分析

        Args:
            file_path: CSV 文件路径
            columns: 要分析的列，逗号分隔，默认全部数值列
            group_by: 分组列名
            agg: 聚合函数 mean/sum/count/min/max/std/median
            encoding: 文件编码
        """
        try:
            p = self._resolve_path(file_path)
            df = pd.read_csv(p, encoding=encoding)

            # 筛选列
            if columns:
                col_list = [c.strip() for c in columns.split(",")]
                missing = [c for c in col_list if c not in df.columns]
                if missing:
                    return {"error": f"列不存在: {missing}", "available_columns": list(df.columns)}
                df = df[col_list]

            # 分组聚合
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
                # 整体统计
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
        """SQL 风格查询 CSV 数据

        Args:
            file_path: CSV 文件路径
            select: 要查询的列，逗号分隔，默认 *（全部）
            where: 筛选条件表达式，如 "age > 30 and city == '北京'"
            order_by: 排序列，支持 "col" 或 "col desc"
            limit: 返回行数上限
            encoding: 文件编码
        """
        try:
            p = self._resolve_path(file_path)
            df = pd.read_csv(p, encoding=encoding)

            # WHERE
            if where:
                df = df.query(where)

            # SELECT
            if select.strip() != "*":
                col_list = [c.strip() for c in select.split(",")]
                missing = [c for c in col_list if c not in df.columns]
                if missing:
                    return {"error": f"列不存在: {missing}", "available_columns": list(df.columns)}
                df = df[col_list]

            # ORDER BY
            if order_by:
                parts = order_by.strip().rsplit(maxsplit=1)
                if len(parts) == 2 and parts[1].lower() == "desc":
                    df = df.sort_values(parts[0], ascending=False)
                else:
                    df = df.sort_values(order_by.strip())

            # LIMIT
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
        """CSV 数据可视化生成图表

        Args:
            file_path: CSV 文件路径
            chart_type: 图表类型 line/bar/scatter/pie/hist
            x: X 轴列名
            y: Y 轴列名（pie/hist 模式可省略）
            title: 图表标题
            limit: 最大数据点数
            encoding: 文件编码
        """
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

            # 保存
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
        """JSON 文件查询

        支持 Python 字典路径风格查询，例如：
        - "." : 返回根对象
        - "users" : 返回 users 字段
        - "users[0].name" : 返回第一个用户的 name
        - "data.items" : 嵌套路径

        Args:
            file_path: JSON 文件路径
            path: 查询路径，默认 "."（根）
            pretty: 是否格式化输出
            encoding: 文件编码
        """
        try:
            p = self._resolve_path(file_path)
            with open(p, "r", encoding=encoding) as f:
                data = json.load(f)

            # 路径解析
            if path and path != ".":
                result = self._resolve_json_path(data, path)
            else:
                result = data

            # 截断控制
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
        """解析简单的 JSON 路径，如 users[0].name"""
        import re
        parts = re.split(r"\.(?![^\[]*\])", path)
        current = data
        for part in parts:
            if not part:
                continue
            # 处理 array index: items[0]
            match = re.match(r"^(\w+)\[(\d+)\]$", part)
            if match:
                key, idx = match.group(1), int(match.group(2))
                current = current[key][idx]
            elif "[" in part:
                # 纯索引 [0]
                idx = int(re.search(r"\[(\d+)\]", part).group(1))
                current = current[idx]
            else:
                if isinstance(current, dict):
                    current = current[part]
                else:
                    return {"error": f"路径 {part} 无法解析，当前类型: {type(current).__name__}"}
        return current
