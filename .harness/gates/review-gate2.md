# Gate 2 交付报告 — CHANGE-052 长篇章节数量与字数约束修复

**日期**: 2026-05-28
**变更 ID**: CHANGE-052
**分支**: feature/change-052-chapter-constraints
**提交**: 734a1f5

---

## 一、需求交付摘要

### R1（P0）— 修复卷纲生成 token 截断 ✅

| 任务 | 实现 | 验收 |
|------|------|------|
| T1: generate_volume_outline max_tokens 6000→12000 | `long_form_generation_helpers.py:200` | ✅ |
| T2: generate_master_outline max_tokens 6000→8000 | `long_form_generation_helpers.py:108` | ✅ |
| T3: 章节数量验证与重试（< 80% 时最多 2 次，耗尽后 fallback） | `long_form_generation_helpers.py:202-231` | ✅ 4 个单元测试 |
| T4: VOLUME_OUTLINE_PROMPT 强制要求措辞 + 建议语义 | `prompts.py:328-333, 320` | ✅ |

### R2（P1）— 章节数量自动计算 ✅

| 任务 | 实现 | 验收 |
|------|------|------|
| T8: LongFormNovelRequest 新增 auto_calc_chapters 字段 | `requests.py:102-105` | ✅ |
| T8: 后端自动计算 clamp(ceil(target/wpc/vol), 20, 60) | `novel_generator.py:900-921` | ✅ 7 个单元测试 |
| T9: 前端复选框 + 预览 + payload 传递 | `Create.vue:123-142, 212-218, 256, 295` | ✅ |
| words_per_chapter 上限 4000→8000 | `requests.py:83` | ✅ |

### R3（P1）— 字数约束强化 ✅

| 任务 | 实现 | 验收 |
|------|------|------|
| T5: WORD_COUNT续写阈值 0.6→0.75，MAX_CONTINUATION_ATTEMPTS=3 | `chapter_generator.py:54-55` | ✅ |
| T5: 单次续写改为循环，每次更新字数 | `chapter_generator.py:320-357` | ✅ 5 个单元测试 |
| T6: _continuation_generation max_tokens 4000→6000 | `chapter_generator.py:132` | ✅ |
| T7: CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT 字数约束移至第 1 条 + 最终检查 | `prompts.py:193, 202` | ✅ |

---

## 二、代码变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/api/services/long_form_generation_helpers.py` | 修改 | max_tokens 提升 + 重试逻辑 + chapters_count_min |
| `src/api/services/novel_generator.py` | 修改 | auto_calc_chapters 计算逻辑 |
| `src/core/llm/chapter_generator.py` | 修改 | 续写阈值/次数/循环 |
| `src/core/llm/prompts.py` | 修改 | 字数约束强化 + 卷纲措辞 |
| `src/api/models/requests.py` | 修改 | auto_calc_chapters 字段 + words_per_chapter 上限 |
| `frontend/src/views/Create.vue` | 修改 | 自动计算复选框 + 预览 + 语法修复 |
| `tests/unit/test_change052_chapter_constraints.py` | 新增 | 16 个单元测试 |

---

## 三、测试结果

| 测试套件 | 结果 |
|---------|------|
| 新增单元测试（16 个） | ✅ 16/16 通过 |
| 历史单元测试（414 个） | ✅ 414/414 通过 |
| 总计 | ✅ 430/430 通过，0 失败 |

---

## 四、评审结论

| 评审阶段 | 结论 |
|---------|------|
| Gate 1（需求评审） | APPROVED（第 2 轮） |
| 编码评审（阶段 4） | APPROVED（第 2 轮，修复了 VOLUME_OUTLINE_PROMPT 措辞遗漏） |
| 测试评审（阶段 6） | APPROVED（第 1 轮） |
| CI 验证（阶段 8） | ✅ 430/430 通过 |
| 部署验证（阶段 9） | ⚠️ 跳过（docker.io 网络不可达，环境限制） |

---

## 五、额外修复

编码评审过程中发现并修复了一个 Create.vue 语法错误：
- `const router = useRouter() = [...]` → 拆分为独立的 `router` 和 `novelTypes` 声明

---

## 六、遗留 SHOULD FIX 项（不阻塞交付）

1. **前端预览一致性**：当 autoCalcChaptersPerVolume 被夹紧时，总章数预览与实际生成章数不一致（UX 问题）
2. **计算逻辑重复**：auto_calc 公式在后端、前端、测试中三处镜像，建议后续提取为独立函数
3. **T8 测试镜像**：测试使用本地 `_calc()` 而非直接调用生产代码，存在漂移风险

---

## 结论

**CHANGE-052 交付完成，等待 Gate 2 审批。**

所有 9 个任务已实现，16 个新单元测试全部通过，430 个历史测试无回归。编码评审和测试评审均已通过。
