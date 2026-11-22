"""配置装载：env（密钥/密钥来源）+ config.yaml（行为）+ config/domains/*.yaml（领域契约）。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]
CONFIG_DIR = API_ROOT / "config"


class Settings(BaseSettings):
    """密钥与运行环境。缺 key 时各 provider 自动降级，保证全链路可离线跑通。"""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", API_ROOT / ".env"), extra="ignore", case_sensitive=False
    )

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = ""

    embed_provider: str = "auto"
    embed_base_url: str = ""
    embed_api_key: str = ""
    embed_model: str = ""

    rerank_provider: str = "auto"

    api_keys: str = "dev-local-key"
    session_secret: str = "dev-session-secret"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    push_email_to: str = ""

    data_dir: str = ""

    @property
    def keys(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def data_root(self) -> Path:
        p = Path(self.data_dir) if self.data_dir else API_ROOT / "data"
        p.mkdir(parents=True, exist_ok=True)
        return p


class FilterRule(BaseModel):
    type: Literal["int", "str"]
    min: int | None = None
    max: int | None = None
    max_len: int | None = None


class DomainSpec(BaseModel):
    domain: str
    display_name: str
    chunker: str
    required_meta: list[str]
    optional_meta: list[str] = []
    filter_allowlist: dict[str, FilterRule] = {}
    retrieval: dict[str, Any] = {}
    source_priority: list[str]
    citation_style: str = "《{doc_title}》{locator}"

    def priority_rank(self, name: str) -> int:
        return self.source_priority.index(name) if name in self.source_priority else len(
            self.source_priority
        )


class ServerCfg(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8710
    request_timeout_s: int = 20


class AuthCfg(BaseModel):
    admin_localhost_only: bool = True


class RetrievalCfg(BaseModel):
    top_k_default: int = 4
    top_k_max: int = 10
    recall_pool: int = 50
    rrf_k: int = 60
    rerank_pool: int = 30
    expand_parent: bool = True
    max_chunks_per_doc: int = 2
    budget_tokens: int = 3000
    min_score: dict[str, float] = {}


class CacheCfg(BaseModel):
    enabled: bool = True
    ttl_s: int = 600
    max_entries: int = 512
    task_scope_ttl_s: int = 900


class Config(BaseModel):
    server: ServerCfg = ServerCfg()
    auth: AuthCfg = AuthCfg()
    providers: dict[str, Any] = {}
    retrieval: RetrievalCfg = RetrievalCfg()
    cache: CacheCfg = CacheCfg()
    curation: dict[str, Any] = {}
    domains: dict[str, DomainSpec] = {}

    def domain(self, name: str) -> DomainSpec:
        if name not in self.domains:
            raise UnknownDomain(name)
        return self.domains[name]

    def min_score_for(self, rerank_signature: str) -> float:
        """阈值按"具体 rerank 模型"取；不同模型的分数量纲完全不同，不能共用。"""
        table = self.retrieval.min_score
        if rerank_signature in table:
            return float(table[rerank_signature])
        provider = rerank_signature.split(":", 1)[0]
        return float(table.get(provider, 0.12))


class UnknownDomain(Exception):
    def __init__(self, domain: str):
        super().__init__(f"未注册的领域：{domain}")
        self.domain = domain


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_config() -> Config:
    raw = _read_yaml(API_ROOT / "config.yaml")
    domains: dict[str, DomainSpec] = {}
    for path in sorted((CONFIG_DIR / "domains").glob("*.yaml")):
        spec = DomainSpec.model_validate(_read_yaml(path))
        if not spec.required_meta:
            raise ValueError(f"{path} 缺 required_meta：宁可起不来，也不要带病运行")
        domains[spec.domain] = spec
    curation_path = CONFIG_DIR / "curation.yaml"
    raw["curation"] = _read_yaml(curation_path) if curation_path.exists() else {}
    raw["domains"] = domains
    return Config.model_validate(raw)


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()


# ---- 路径 ----

def data_dir() -> Path:
    return settings().data_root


def raw_dir(domain: str) -> Path:
    p = data_dir() / "raw" / domain
    p.mkdir(parents=True, exist_ok=True)
    return p


def chunks_dir(domain: str) -> Path:
    p = data_dir() / "chunks" / domain
    p.mkdir(parents=True, exist_ok=True)
    return p


def index_root(domain: str) -> Path:
    p = data_dir() / "index" / domain
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    p = data_dir().parent / "var"
    p.mkdir(parents=True, exist_ok=True)
    return p / "app.db"


def eval_dir() -> Path:
    p = REPO_ROOT / "eval"
    p.mkdir(parents=True, exist_ok=True)
    return p
