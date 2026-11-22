"""M0 门禁：核实 DeepSeek model id / 能力、embedding 与 rerank 实际 provider、依赖版本。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

import httpx  # noqa: E402

from ac_api.config import load_config, settings  # noqa: E402
from ac_api.rag.index.embedding import get_embedder, resolve_provider as embed_provider  # noqa: E402
from ac_api.rag.retrieve.rerank import get_reranker  # noqa: E402


def check_llm() -> None:
    s = settings()
    print("== LLM ==")
    print(f"  base_url = {s.deepseek_base_url}")
    if not s.deepseek_api_key:
        print("  api_key  = (空) → 走 stub provider，离线可跑通全链路")
        print("  model    = 未验证（需要 DEEPSEEK_API_KEY 才能打印真实 model 列表）")
        return
    headers = {"Authorization": f"Bearer {s.deepseek_api_key}"}
    try:
        resp = httpx.get(f"{s.deepseek_base_url.rstrip('/')}/models", headers=headers, timeout=20)
        resp.raise_for_status()
        models = [m.get("id") for m in resp.json().get("data", [])]
        print(f"  api_key  = {s.deepseek_api_key[:4]}***")
        print(f"  models   = {models}")
        print(f"  picked   = {s.deepseek_model or '(未设置 DEEPSEEK_MODEL)'}")
        if s.deepseek_model and s.deepseek_model not in models:
            print("  ⚠️ DEEPSEEK_MODEL 不在返回列表里，请核对")
    except Exception as exc:
        print(f"  ⚠️ /models 请求失败：{str(exc)[:200]}")


def check_models() -> None:
    config = load_config()
    print("== embedding / rerank ==")
    embedder = get_embedder()
    print(f"  embedding = {embedder.name} dim={embedder.dim} fp={embedder.fingerprint}")
    reranker = get_reranker()
    print(f"  rerank    = {reranker.name}  (min_score={config.min_score_for(reranker.name)})")
    print(f"  domains   = {', '.join(config.domains)}")
    print(f"  embedding.provider 配置 = {config.providers.get('embedding', {}).get('provider')}")
    print(f"  resolve 结果 = {embed_provider()}")
    print("  切到真模型：EMBED_PROVIDER=bge RERANK_PROVIDER=bge（首次会下载权重）")


def check_pkgs() -> None:
    print("== packages ==")
    import fastapi
    import jieba
    import numpy
    import pydantic
    import yaml

    for name, mod in [("fastapi", fastapi), ("pydantic", pydantic), ("numpy", numpy), ("pyyaml", yaml), ("jieba", jieba)]:
        print(f"  {name:10s} {getattr(mod, '__version__', 'n/a')}")
    try:
        import chromadb  # noqa: F401

        print("  chromadb   已安装（当前默认仍用 LocalVectorStore，见 DECISIONS）")
    except Exception:
        print("  chromadb   未安装（默认 LocalVectorStore，不影响运行）")
    try:
        import sentence_transformers as st

        print(f"  s-transformers {st.__version__}")
    except Exception:
        print("  s-transformers 未安装（embedding 走 hashed 兜底）")


if __name__ == "__main__":
    print(json.dumps({"env": "ok"}, ensure_ascii=False))
    check_llm()
    check_models()
    check_pkgs()
