# Map: post-funnel-cleanup

## Notes
- 首轮（2026-07-16 ~ 2026-07-18）：funnel-quality-gate 上线 + 低内聚高耦合重构三步（见 spec.md）。
- 第二轮（2026-07-18）：01-04 tickets 落地（BackgroundTasks 丢失保护 + 前端风格统一 + novel_generator 拆分 + ChapterGenContext 收窄 + 短篇 quality_check 收敛 gate）+ 遗留债务清理（helpers `i` NameError / supplement 孤儿测试 / 036 慢测试）。05-07 已在首轮/间期完成。

## Decisions so far
- Issue tracker = 本地 markdown（`.scratch/<feature>/`），不走 GitHub Issues
- 安全运维（DEV_AUTO_LOGIN/root 密码/登录守卫恢复）用户要求暂不处理（Ticket 01 状态为 partial）
- Ticket 优先级：02→03→04 是依赖链（已按序完成）；05/06/07 无 blocker（已完成）
- Ticket 04 行为口径变化（用户确认接受）：短篇 consistency block 从 KG verdict / StoryBible error 收敛为 gate 的 L2 评分 character_consistency/world_consistency < 0.4；StoryBible 冲突改为收集到 consistency_warnings 供展示，不再硬 block

## Frontier
- （无待办）01-07 全部 resolved/partial；01 的 partial 项（安全三项）按用户决策暂不处理

## Dependency chain
- ~~02（拆 novel_generator）→ 03（Context 对象）→ 04（gate 收敛短篇）~~ — 已按序完成（commit 2c56a9a / 9f83bf3 / 5653747）

## Fog
- ~~`generate_chapters_background`（按范围生成）的真实调用频率？~~ — 仍保留（helpers:992），未废弃
- ~~短篇 quality_check 节点（接 gate）改动面多大？~~ — 已完成（Ticket 04），保留 KG 抽取副作用
- ~~文件目录整理后 CI/docker-compose/deploy.sh 是否依赖旧路径~~ — Ticket 07 已处理
- 残留技术债（非 blocker）：
  - `test_change036::test_exhausts_retries_on_persistent_api_connection_error` 已 skip（降级路径 tenacity 退避 patch 未覆盖，待定位）
  - `test_change036` 预先存在的 RuntimeWarning（`_generate_single_chapter_inner` coroutine 未 await）