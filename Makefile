# xIaoShuo 工程验证门禁
# 用法：make verify 跑全部检查；make <target> 跑单项。
#
# 说明：
# - tests/integration/test_langgraph/test_graph.py 真打 DeepSeek API（慢、依赖外网、不可重复），
#   默认从门禁排除，需手动验证时单独跑：poetry run pytest tests/integration/test_langgraph
# - tests/api 与 tests/integration 的 module 级 _db_setup 在混跑时会因 drop_all 互相破坏表
#   （既有隔离缺陷），故 test-integration 与 test-api 分为独立目标。

PY := poetry run
FE := cd frontend && npm

.PHONY: test-unit test-api test-integration test-backend test-frontend ruff ruff-fix build-frontend check-structure check-legacy-paths check-secrets verify

## 后端单元测试
test-unit:
	$(PY) pytest tests/unit -q

## 后端 API 测试（需可达的 PostgreSQL 测试库）
test-api:
	$(PY) pytest tests/api -q

## 后端集成测试（排除真 LLM 的 test_langgraph；需可达测试库）
test-integration:
	$(PY) pytest tests/integration --ignore=tests/integration/test_langgraph -q

## 后端全部测试（分目录跑以避开 module 级 _db_setup 混跑隔离缺陷）
test-backend: test-unit test-api test-integration
	@echo "==== backend tests done ===="

## 前端单元测试
test-frontend:
	$(FE) run test

## Ruff 静态检查
ruff:
	$(PY) ruff check .

## Ruff 自动修复（谨慎，会改文件）
ruff-fix:
	$(PY) ruff check . --fix

## 前端生产构建
build-frontend:
	$(FE) run build

## 服务目录结构约束测试
check-structure:
	$(PY) pytest tests/unit/test_project_structure.py -q

## 旧服务路径残留检查
check-legacy-paths:
	$(PY) python scripts/check_legacy_paths.py

## 仓库敏感凭据扫描
check-secrets:
	$(PY) python scripts/check_secrets.py

## 聚合门禁：跑全部验证（任一失败即整体失败）
verify: test-backend test-frontend ruff check-structure check-legacy-paths check-secrets build-frontend
	@echo "==== ALL CHECKS PASSED ===="
