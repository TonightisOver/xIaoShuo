# 项目历史资料整理报告

- 整理前受管文件数：833
- 整理后受管文件数：883
- 已归档 CHANGE 目录数：47
- 业务源码修改：无
- Git 暂存或提交：未执行

## 明确保留

- `frontend/node_modules/`
- `logs/`
- `data/`
- `.env*` 与 `poetry.lock`
- `.claude/worktrees/`
- 当前设计文档与实施计划

## 基线说明

- 前端测试基线：47 passed。
- 前端构建基线：PASS。
- 后端无数据库单元基线：762 passed、15 failed、1 skipped。
- 数据库测试受沙箱禁止连接 localhost:5432 影响，未取得真实结果。

## 完成后验证

- 归档工具测试：7 passed。
- 归档结构校验：PASS，47 个 CHANGE 目录均有归档记录。
- Manifest 校验：PASS，427 个移动文件均有新旧路径映射。
- Ruff：PASS。
- FastAPI 应用入口导入：PASS。
- 后端无数据库单元测试：768 passed、15 failed、1 skipped；15 个失败与整理前基线完全相同，新增归档测试全部通过。
- 前端测试：47 passed，与基线一致。
- 前端构建：PASS，与基线一致。
- 数据库集成测试仍受沙箱连接限制，未作为本次回归判定依据。

## 安全发现

- 自动生成的索引和归档记录已对 `sk-*` API Key 执行脱敏。
- 部分原始历史文件包含旧 API Key 明文；原文按归档要求未修改，也未在本报告中复述。
- 这些旧密钥应视为已泄露并轮换；Git 历史清理应作为独立安全任务执行。

## 路径映射

完整映射见 [`manifest.csv`](manifest.csv)。
