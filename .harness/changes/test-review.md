# 测试评审报告 — CHANGE-053

**评审类型**: test_review（第 1 轮）  
**评审日期**: 2026-05-28  
**测试文件**:
- `tests/unit/test_novel_generator_auto_calc.py`
- `tests/unit/test_novel_generator_outline_persist.py`  
**评审人**: Reviewer Agent

---

## 评审结论

**结果**: APPROVED

---

## 评审发现

### MUST FIX（必须修复）

无。

---

### SHOULD FIX（建议修复）

**S1 — `test_persist_failure_does_not_interrupt_generation` 仅覆盖 `upsert_volume_outline` 失败，未覆盖 `upsert_chapter_outline` 失败路径**

文件: `tests/unit/test_novel_generator_outline_persist.py`，`test_persist_failure_does_not_interrupt_generation`

当前测试让 `upsert_volume_outline` 抛出异常，验证生成流程继续。由于 `upsert_volume_outline` 和 `upsert_chapter_outline` 在同一 `try` 块内，`upsert_volume_outline` 抛出后 `upsert_chapter_outline` 不会执行，因此该测试实际覆盖的是"整个持久化块失败"的场景。

建议补充一个 `upsert_volume_outline` 成功、`upsert_chapter_outline` 失败的测试，以验证章节级持久化失败同样不中断流程。不阻塞当前交付，但会提升边界覆盖完整性。

**S2 — `_expected_auto_calc` 辅助函数与生产代码逻辑重复，未引用生产代码**

文件: `tests/unit/test_novel_generator_auto_calc.py`，第 46-49 行

```python
def _expected_auto_calc(target_words, words_per_chapter, volumes):
    total = math.ceil(target_words / words_per_chapter)
    computed = math.ceil(total / volumes)
    return max(20, min(60, computed))
```

该函数手动复制了 `novel_generator.py` 中的计算逻辑。若生产代码的 clamp 范围（20/60）或计算公式变更，测试不会自动感知，可能出现"测试通过但逻辑已变"的假阳性。建议将该计算逻辑提取为生产代码中的独立纯函数，测试直接引用；或在注释中标注"与 novel_generator.py 第 865-867 行保持同步"。

---

### INFO（信息提示）

**I1 — 测试文件路径与 tasks.md 中的规划路径不一致**

tasks.md T5/T6 中指定路径为 `tests/test_novel_generator_auto_calc.py` 和 `tests/test_novel_generator_outline_persist.py`（根目录下 tests/），实际文件位于 `tests/unit/` 子目录。这是合理的工程决策（单元测试应在 unit/ 下），但 tasks.md 的路径描述需同步更新，避免后续混淆。

**I2 — `test_chapter_outlines_persisted_after_generation` 断言章节编号为 `[1, 2, 3, 1, 2, 3]`，依赖每卷内部章节编号从 1 重置的隐含假设**

文件: `tests/unit/test_novel_generator_outline_persist.py`，第 130-131 行

`_make_vol_outline` 中章节编号从 `i + 1` 生成（每卷内部从 1 开始），与实现代码中 `ch.get("chapter", idx + 1)` 的取值逻辑一致，断言正确。建议在测试注释中明确说明"每卷内部章节编号从 1 重置"这一假设，避免后续维护者误解为全局章节编号。

**I3 — 两个测试文件均在 `with` 块内部执行 `from ... import generate_long_form_background`**

这是为了确保 patch 在模块加载前生效的标准做法，逻辑正确。当前 438 个测试全部通过，说明实际运行中无模块缓存冲突问题，记录备查。

---

## 验收标准对照

| 验收项 | 测试方法 | 覆盖情况 |
|--------|---------|---------|
| T5-1: auto_calc=True 时 initialize_progress 收到自动计算值 | `test_auto_calc_chapters_before_initialize_progress` | 完整覆盖，断言 `kwargs["chapters_per_volume"] == 50` |
| T5-2: generate_master_outline 传入正确 chapters_per_vol | `test_auto_calc_chapters_master_outline_uses_correct_value` | 完整覆盖，断言 `kwargs["chapters_per_vol"] == 50` |
| T5-3: auto_calc=False 时 chapters_per_vol = request.chapters_per_volume | `test_auto_calc_false_uses_request_value` | 完整覆盖，断言 `kwargs["chapters_per_volume"] == 30` |
| T6-1: 每卷生成后 upsert_volume_outline 被调用一次 | `test_volume_outline_persisted_after_generation` | 完整覆盖，验证 `call_count==2` 且卷号正确 |
| T6-2: 每章大纲 upsert_chapter_outline 被调用 | `test_chapter_outlines_persisted_after_generation` | 完整覆盖，验证 `call_count==6` 且章节编号序列正确 |
| T6-3: 持久化失败不中断生成流程 | `test_persist_failure_does_not_interrupt_generation` | 完整覆盖，验证 `generate_volume_chapters` 仍被调用且 `complete_task` 正常执行 |

tasks.md 中 T5 要求 3 个测试，实际交付 5 个（额外覆盖了 `update_novel` 使用自动计算值，以及 `auto_calc=False` 对 `generate_master_outline` 的影响），超出验收要求。

---

## 总结

8 个测试用例全部覆盖了 tasks.md T5/T6 的验收标准，断言有实质意义（验证具体参数值和调用次数，而非仅检查是否被调用），测试之间相互独立，mock 策略合理（patch 路径指向定义处，与实现中的 inline import 一致）。主要改进建议（S1-S2）均为可选优化，不影响当前需求的正确性验证。

**结论：APPROVED**
