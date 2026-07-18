# 01 — 安全 & 运维债务清理

**What to build:** 线上已暴露且阻塞正式上线的安全/运维问题，每一个都是独立可验证的修正。

**Blocked by:** None — 可立即开始

**Status:** partial — BackgroundTasks 丢失保护 + 前端风格统一已落地；安全三项（DEV_AUTO_LOGIN/root 密码/登录守卫）按 map.md 决策暂不处理

- [ ] **关 DEV_AUTO_LOGIN**：线上当前 DEV_AUTO_LOGIN=1，任何人可免登录获 admin 调全部 API（含 LLM 配置）。恢复前端路由守卫 + 去掉 compose 注入，仅本地 dev 保留
- [ ] **改 root 密码**：服务器 root 密码 `qT27RUgyLRGJ` 已在对话记录中暴露，部署完立即改
- [ ] **恢复前端登录守卫**：`router/index.js` 的 beforeEach 改回"未带 token 且非 landing/login → 跳 login"
- [ ] **BackgroundTasks 丢失保护**：FastAPI BackgroundTasks 在容器重启时丢任务，task 卡 pending 永远。短期：启动时把所有 pending task 标记 failed；长期：迁移到 Celery
- [ ] **前端风格残留 4 处**：ForeshadowTracker/ChapterEdit 的 indigo/amber、KnowledgeGraph 的 neutral、Careers/Home 的 neutral 标签 → 统一纸墨
