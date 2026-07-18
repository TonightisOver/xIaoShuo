# Map: post-funnel-cleanup

## Notes
本轮（2026-07-16 ~ 2026-07-18）已完成 funnel-quality-gate 上线 + 低内聚高耦合重构三步。以下是剩余的工程化 debt 和架构深化。

## Decisions so far
- Issue tracker = 本地 markdown（`.scratch/<feature>/`），不走 GitHub Issues
- 安全运维（DEV_AUTO_LOGIN/root 密码/登录守卫恢复）用户要求暂不处理
- Ticket 优先级：无 blocker 的先做 → 05/06/07 可并行；02→03→04 是依赖链

## Frontier（无 blocker，可立即开工）
- 05：长篇进度详情页完善
- 06：短篇流程页体验优化
- 07：项目目录管理规范化

## Dependency chain
02（拆 novel_generator）→ 03（Context 对象）→ 04（gate 收敛短篇）

## Fog
- `generate_chapters_background`（按范围生成）的真实调用频率？如果很少用，是否值得保留？还是直接废弃？
- 短篇 LangGraph 流水线的 quality_check 节点（接 gate）改动面多大？需先探索
- 文件目录整理后，CI/docker-compose/deploy.sh 是否依赖旧路径