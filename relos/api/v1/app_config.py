"""
relos/api/v1/app_config.py
---------------------------
只读配置与演示数据路径（非密钥）。供前端替代页面内硬编码常量。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


def _demo_data_dir() -> Path:
    """relos/demo_data（与 relos/api/v1 相对路径固定，打包后仍可用）。"""
    return Path(__file__).resolve().parent.parent.parent / "demo_data"


class ApiResponse(BaseModel):
    status: str
    data: dict[str, Any] = {}
    message: str = ""


@router.get("/quick-alarms", response_model=ApiResponse)
async def get_quick_alarms() -> ApiResponse:
    """告警分析页「快速选择」列表，来自 relos/demo_data/quick_alarms.json。"""
    path = _demo_data_dir() / "quick_alarms.json"
    if not path.is_file():
        return ApiResponse(status="success", data={"items": []}, message="")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else []
    except Exception:
        items = []
    return ApiResponse(status="success", data={"items": items}, message="")


@router.get("/text-samples", response_model=ApiResponse)
async def get_text_samples() -> ApiResponse:
    """公开知识页「示例」段落，来自 relos/demo_data/text_samples.json。"""
    path = _demo_data_dir() / "text_samples.json"
    if not path.is_file():
        return ApiResponse(status="success", data={"samples": {}}, message="")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        samples = raw if isinstance(raw, dict) else {}
    except Exception:
        samples = {}
    return ApiResponse(status="success", data={"samples": samples}, message="")
