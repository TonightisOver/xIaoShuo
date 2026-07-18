# 02 — 拆 novel_generator 上帝模块

**What to build:** `novel_generator.py`（原 1111 行，Step3 后已减到 ~980 行）装了短篇 LangGraph 编排 + 长篇编排 + 按卷 + 按范围 + 调度原语。把长篇 `generate_long_form_background` 迁入 `long_form_generation_helpers`（它的所有协作者已在那个模块），novel_generator 只留短篇 LangGraph 编排 + 任务调度原语。

**Blocked by:** 01（安全基线先稳）

**Status:** resolved — 长篇三入口迁入 helpers，novel_generator 996→640 行

- [ ] `generate_long_form_background` 从 novel_generator 迁入 long_form_generation_helpers
- [ ] 删除 novel_generator 里长篇相关的 import（progress_service/calculate_chapter_plan 等）
- [ ] novel_generator 只保留：短篇 13 阶段编排 + _emit_progress/pause/resume 调度原语 + _persist_to_novel
- [ ] novel_generator 行数从 ~980 降到 ~700
- [ ] 测试：长篇 API 集成测试（test_change044）全部通过，无回归