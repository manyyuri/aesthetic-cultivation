from __future__ import annotations

from ac_api.config import Config, DomainSpec, load_config


class DomainRegistry:
    """领域契约的唯一访问口。启动时校验，缺字段直接起不来。"""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config()

    @property
    def config(self) -> Config:
        return self._config

    def names(self) -> list[str]:
        return sorted(self._config.domains)

    def get(self, domain: str) -> DomainSpec:
        return self._config.domain(domain)

    def has(self, domain: str) -> bool:
        return domain in self._config.domains

    def all(self) -> list[DomainSpec]:
        return [self._config.domains[d] for d in self.names()]

    def display(self, domain: str) -> str:
        return self.get(domain).display_name


registry = DomainRegistry()
