# 唯一入口。后端 = apps/api/.venv（python3.12），前端 = pnpm workspace。
PY      := apps/api/.venv/bin/python
PIP     := apps/api/.venv/bin/pip
API_DIR := apps/api
PORT    ?= 8710
WEB_PORT?= 5173

.PHONY: help install api-install web-install dev serve preflight contracts check lint test cost \
        ingest index rollback ask issue-build issue-deliver eval eval-ci eval-dry eval-check \
        eval-feedback web-build seed clean

help:
	@grep -E '^[a-zA-Z:_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: api-install web-install ## 安装后端与前端依赖

api-install: ## 建 venv 并装后端依赖
	@test -d $(API_DIR)/.venv || /opt/homebrew/bin/python3.12 -m venv $(API_DIR)/.venv
	@$(PIP) install -q --upgrade pip
	@$(PIP) install -q -r $(API_DIR)/requirements.txt
	@echo "api deps ok"

web-install: ## 安装前端依赖
	@pnpm install --silent

dev: ## 并行起 api(8710) 与 web(5173)
	@sh scripts/dev.sh

serve: ## 只起后端
	@$(PY) -m uvicorn ac_api.app:app --app-dir $(API_DIR)/src --port $(PORT)

preflight: ## 验证 key / model / embedding / 依赖版本
	@PYTHONPATH=$(API_DIR)/src $(PY) scripts/preflight.py

contracts: ## 导出 openapi.json 并生成 TS 类型
	@PYTHONPATH=$(API_DIR)/src $(PY) scripts/export_openapi.py
	@pnpm --filter @ac/contracts gen

seed: ## 把 fixtures 灌进 data/raw（可重复执行）
	@PYTHONPATH=$(API_DIR)/src $(PY) scripts/seed_fixtures.py

ingest: ## 入库 DOMAIN=ballet [FORCE=1]
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.cli ingest --domain $(DOMAIN) $(if $(FORCE),--force,)

index: ## 建索引 DOMAIN=ballet
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.cli index --domain $(DOMAIN)

rollback: ## 回滚 DOMAIN=ballet VERSION=...
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.cli rollback --domain $(DOMAIN) --version $(VERSION)

ask: ## 检索 Q="..." DOMAIN=ballet [TOPK=4]
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.cli ask --domain $(DOMAIN) --query "$(Q)" --top-k $(or $(TOPK),4)

issue-build: ## 生成一期 DATE=2026-11-22 [KIND=daily|weekly]
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.cli issue-build --date $(or $(DATE),$$(date +%F)) --kind $(or $(KIND),daily)

issue-deliver: ## 推送一期 DATE=... [CHANNEL=inapp|email]
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.cli issue-deliver --date $(or $(DATE),$$(date +%F)) --channel $(or $(CHANNEL),inapp)

eval: ## 检索 + 期级指标（DOMAIN=ballet；LLM 判分需 key）
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.eval.cli --domain $(or $(DOMAIN),ballet) --k 5

eval-ci: ## 只跑免 LLM 三项
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.eval.cli --domain $(or $(DOMAIN),ballet) --k 5 --ci

eval-check: ## 校验 golden 的 doc_id 真实存在
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.eval.cli --check --domain $(or $(DOMAIN),ballet)

cost: ## 当日 token 与成本
	@PYTHONPATH=$(API_DIR)/src $(PY) scripts/cost_report.py

eval-feedback: ## 汇总 feedback 出三类清单
	@PYTHONPATH=$(API_DIR)/src $(PY) -m ac_api.eval.cli --feedback

lint: ## ruff（未装则跳过）
	@$(API_DIR)/.venv/bin/ruff check $(API_DIR)/src 2>/dev/null || echo "ruff 未安装，跳过"

test: ## 后端单测
	@cd $(API_DIR) && PYTHONPATH=src .venv/bin/pytest -q

check: lint test web-build contracts-verify ## 全量门禁
	@echo "check ok"

contracts-verify: ## 校验契约生成物无漂移
	@$(PY) scripts/check_contracts_drift.py

web-build: ## 前端类型检查 + 构建
	@pnpm --filter @ac/web exec tsc --noEmit && pnpm --filter @ac/web build

clean: ## 清掉生成物
	@rm -rf apps/api/data/chunks apps/api/data/index apps/web/dist
