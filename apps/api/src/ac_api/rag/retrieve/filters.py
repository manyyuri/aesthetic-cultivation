"""meta_filter 白名单校验 + Chroma 风格 where 转换。越权 key 一律 400。"""

from __future__ import annotations

from typing import Any

from ac_api.config import DomainSpec


class FilterError(Exception):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def validate_filter(spec: DomainSpec, meta_filter: dict[str, Any] | None) -> dict[str, Any] | None:
    if not meta_filter:
        return None
    allowed = set(spec.filter_allowlist)
    unknown = sorted(set(meta_filter) - allowed)
    if unknown:
        raise FilterError(
            f"meta_filter 含未授权字段：{','.join(unknown)}",
            {"allowed": sorted(allowed), "unknown": unknown},
        )
    normalized: dict[str, Any] = {}
    for key, rule in spec.filter_allowlist.items():
        if key not in meta_filter:
            continue
        value = meta_filter[key]
        if rule.type == "int":
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                value = int(value)
            if not isinstance(value, int):
                raise FilterError(f"{key} 必须是整数", {"field": key, "got": type(value).__name__})
            if rule.min is not None and value < rule.min:
                raise FilterError(f"{key} 不能小于 {rule.min}", {"field": key, "min": rule.min})
            if rule.max is not None and value > rule.max:
                raise FilterError(f"{key} 不能大于 {rule.max}", {"field": key, "max": rule.max})
            normalized[key] = {"$eq": value}
        else:
            if not isinstance(value, str):
                raise FilterError(f"{key} 必须是字符串", {"field": key})
            if rule.max_len and len(value) > rule.max_len:
                raise FilterError(f"{key} 超长（>{rule.max_len}）", {"field": key, "max_len": rule.max_len})
            normalized[key] = {"$eq": value}
    return normalized or None


def relaxations(spec: DomainSpec, meta_filter: dict[str, Any] | None) -> list[str]:
    if not meta_filter:
        return []
    return [f"去掉筛选条件 {key}" for key in meta_filter][:2]
