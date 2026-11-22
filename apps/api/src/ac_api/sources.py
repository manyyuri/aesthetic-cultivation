"""开放数据源契约：从 config/sources.yaml 装载并校验，license 是硬闸门。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ac_api.config import API_ROOT, load_config
from ac_api.obs.logger import get_logger

log = get_logger("sources")
CONFIG = API_ROOT / "config" / "sources.yaml"

CC_RE = re.compile(r"cc[ -]by[ -](sa[ -])?(\d\.\d)", re.I)
PD_TOKENS = ("public domain", "public-domain", "publicdomain", "pdm", "pd mark")


class SourceConfigError(Exception):
    pass


class IaIdentifier(BaseModel):
    id: str
    license: str = "public-domain"
    work: str | None = None
    choreographer: str | None = None
    premiere_year: int | None = None
    acts: int | None = None
    version_note: str | None = None


class SourceSpec(BaseModel):
    name: str = ""
    domain: str
    kind: str = "api"
    fetcher: str
    license: str
    homepage: str = ""
    rate_limit_rps: float = 1.0
    user_agent: str = ""
    require_meta: list[str] = Field(default_factory=list)
    source_priority: str = "secondary_web"
    mapping: dict[str, str] = Field(default_factory=dict)
    media_hosts: list[str] = Field(default_factory=list)
    max_tracks: int = 12
    default_acts: int = 1
    max_chars: int = 6000
    identifiers: list[IaIdentifier] = Field(default_factory=list)


class AllowList(BaseModel):
    licenses: list[str]
    on_violation: str = "refuse"


class SourcesFile(BaseModel):
    allow: AllowList
    sources: dict[str, SourceSpec]


def normalize_license(raw: str | None) -> str | None:
    """把 'excerpt · CC BY-SA 4.0' / 'cc0' / 'Public Domain' 归一成白名单里的写法。"""
    if not raw:
        return None
    text = str(raw).split("·")[-1].split(",")[-1].strip()
    lowered = text.lower()
    if lowered.startswith("cc0") or lowered in ("cc-0", "cc zero"):
        return "CC0-1.0"
    match = CC_RE.search(text)
    if match:
        suffix = "-SA" if match.group(1) else ""
        return f"CC-BY{suffix}-{match.group(2)}"
    if any(token in lowered for token in PD_TOKENS):
        return "Public-Domain-Mark-1.0" if "mark" in lowered or "pdm" in lowered else "public-domain"
    return text


def load_from_dict(raw: dict[str, Any]) -> SourcesFile:
    """校验一份 sources 配置。拆出来是为了能在单测里验非法配置。"""
    data = SourcesFile.model_validate(raw)
    domain_config = load_config()
    allowed = set(data.allow.licenses)
    seen: set[str] = set()
    for name, spec in data.sources.items():
        if name != spec.name:
            spec.name = name
        if not re.fullmatch(r"[a-z_]+", spec.name):
            raise SourceConfigError(f"源名必须是 [a-z_]+：{spec.name}")
        if spec.domain not in domain_config.domains:
            raise SourceConfigError(f"{name} 的 domain 未注册：{spec.domain}")
        normalized = normalize_license(spec.license)
        if normalized not in allowed:
            raise SourceConfigError(f"{name} 的 license 不在白名单：{spec.license}")
        spec.license = normalized
        required = set(domain_config.domain(spec.domain).required_meta)
        missing = required - set(spec.require_meta)
        if missing:
            raise SourceConfigError(f"{name} 的 require_meta 缺领域必填字段：{sorted(missing)}")
        for item in spec.identifiers:
            if normalize_license(item.license) not in allowed:
                raise SourceConfigError(f"{name}/{item.id} 的 license 不在白名单：{item.license}")
        if spec.name in seen:
            raise SourceConfigError(f"重复的源名：{spec.name}")
        seen.add(spec.name)
    return data


def _read() -> SourcesFile:
    if not CONFIG.exists():
        raise SourceConfigError(f"缺少 {CONFIG}")
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    return load_from_dict(raw)


@lru_cache(maxsize=1)
def sources() -> SourcesFile:
    return _read()


def get_source(name: str) -> SourceSpec:
    data = sources()
    if name not in data.sources:
        raise SourceConfigError(f"未知数据源：{name}（可选：{', '.join(sorted(data.sources))}）")
    return data.sources[name]


def allowed_licenses() -> list[str]:
    return list(sources().allow.licenses)


def user_agent(spec: SourceSpec) -> str:
    import os

    contact = os.environ.get("SOURCES_UA_CONTACT", "").strip()
    return spec.user_agent.replace("${SOURCES_UA_CONTACT}", f"mailto:{contact}" if contact else "no-contact")


def allowed_media_hosts() -> set[str]:
    return {host for spec in sources().sources.values() for host in spec.media_hosts}


def doc_count(domain: str, source: str) -> int:
    from ac_api.rag.ingest.manifest import load_manifest

    manifest = load_manifest(domain)
    return sum(1 for info in manifest.values() if info.get("source") == source)


def as_public(spec: SourceSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "domain": spec.domain,
        "license": spec.license,
        "homepage": spec.homepage,
        "kind": spec.kind,
        "doc_count": doc_count(spec.domain, spec.name),
    }


__all__ = [
    "IaIdentifier",
    "SourceConfigError",
    "SourceSpec",
    "allowed_licenses",
    "allowed_media_hosts",
    "as_public",
    "get_source",
    "load_from_dict",
    "normalize_license",
    "sources",
    "user_agent",
]
