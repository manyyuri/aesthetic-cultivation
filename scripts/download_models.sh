#!/bin/sh
# 下模型权重到 apps/api/models/（不进 git，「.gitignore」已排除）
# bge-m3：多语言 embedding，跨语言检索靠它；bge-reranker-v2-m3：cross-encoder 重排
set -e
DEST="${1:-apps/api/models}"
HF="${HF_ENDPOINT:-https://huggingface.co}"

fetch() { # $1=repo $2=destdir $3...=files
  repo="$1"; dir="$DEST/$2"; shift 2
  mkdir -p "$dir"
  for f in "$@"; do
    mkdir -p "$dir/$(dirname "$f")"
    [ -s "$dir/$f" ] && continue
    echo "  $repo/$f"
    curl -sSL -o "$dir/$f" "$HF/$repo/resolve/main/$f"
  done
}

echo "→ bge-m3"
fetch BAAI/bge-m3 bge-m3 \
  config.json modules.json sentence_bert_config.json special_tokens_map.json \
  tokenizer_config.json tokenizer.json sentencepiece.bpe.model\
  1_Pooling/config.json pytorch_model.bin

echo "→ bge-reranker-v2-m3"
fetch BAAI/bge-reranker-v2-m3 bge-reranker-v2-m3 \
  config.json modules.json sentence_bert_config.json special_tokens_map.json \
  tokenizer_config.json tokenizer.json sentencepiece.bpe.model model.safetensors

echo "done. 使用："
echo "  EMBED_PROVIDER=bge EMBED_MODEL=\$PWD/$DEST/bge-m3 \\"
echo "  RERANK_PROVIDER=bge RERANK_MODEL=\$PWD/$DEST/bge-reranker-v2-m3 make index DOMAIN=art"
