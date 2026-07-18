# 07 — 项目目录管理规范化

**What to build:** 根目录散落的 md 文件和部署文件归类到统一位置，项目结构更干净、新开发者更容易定位文件。

**Blocked by:** None — 可立即开始

**Status:** ready-for-agent

- [ ] 非入口 md（AGENTS.md/CHANGELOG.md/DATABASE_SETUP.md）移入 `docs/`
- [ ] 部署文件归类：Dockerfile/nginx.conf → 保留根（标准位置），deploy.sh/verify_deployment.py → `scripts/`
- [ ] `docs/` 目录整理：已有机密文档 + 图片 + agent 配置 → 分 `docs/guides/` `docs/images/` `docs/agents/`
- [ ] README.md 保留根（入口）
- [ ] 确认 `src/`(`backend/`) + `frontend/` 不动（之前讨论过 src→backend rename 高风险，这次不做）
- [ ] 更新 deploy.sh 中可能的路径引用
- [ ] 确认 Dockerfile/docker-compose 不依赖被移动的文件路径
