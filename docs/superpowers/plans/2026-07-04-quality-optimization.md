# AI 质量优化 + 数据库备份 + 前端错误处理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement inline.

**Goal:** 解决 AI 生成小说的"AI味重"问题，补充数据库备份，统一前端错误处理三态

**Architecture:**
- **Prompt 优化**：在 `src/core/validation.py` WRITING_STYLES 中为每种文风追加"去 AI 味"指令，同时在 `src/core/llm/prompts.py` 的章节生成 prompt 中加入后处理要求
- **后处理清洗**：在 `src/core/llm/chapter_generator.py` 中新增 `post_process_chapter()` 函数，用正则替换 AI 标点习惯
- **数据库备份**：在服务器上创建备份脚本，利用 crontab 每日自动备份 PostgreSQL
- **前端错误处理**：给 WorldEdit、Characters、Conversation 页面补充 error state + retry 机制

**Tech Stack:** Python 3.11 · FastAPI · PostgreSQL · Vue 3 · Tailwind

---

### Task 1: Prompt 中去 AI 味指令

**Files:**
- Modify: `src/core/validation.py` (WRITING_STYLES dict, lines 140-149)
- Modify: `src/core/llm/prompts.py` (CHAPTER_GENERATION_PROMPT + CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT)

- [ ] **Step 1: 修改 WRITING_STYLES，追加去 AI 味指令**

```python
WRITING_STYLES = {
    "轻松幽默": "请使用轻松幽默的文风，多用吐槽、梗和诙谐对话，节奏轻快活泼。\n"
                "【去AI味要求】标点不要过于规范，不用或少用——和；使用口语化断句。对话带语气词、口头禅。段落长度不平均，穿插短句段营造节奏。避免每段以「他/她/主角」开头。不要出现AI式的「温馨提示」，减少「首先、其次、最后」等结构词。",
    "热血燃向": "请使用热血燃向的文风，短句有力，战斗场面爽快激烈，节奏紧凑。\n"
                "【去AI味要求】标点不要过于规范，多用短句和感叹。对话简短有力，避免长篇大论的心理描写。战斗场面多用动作和感官描写，少用「可以看出、毫无疑问」等抽象评价。段落要短，像网络小说一样有「断章」感。",
    "细腻文艺": "请使用细腻文艺的文风，注重环境描写和心理刻画，语言优美有意境。\n"
                "【去AI味要求】避免过于工整的排比句。描写要留白，不要每件事都「说明白」。适当使用不完整的句式制造氛围。少用「仿佛、好似、似乎」等模糊词。",
    "史诗厚重": "请使用史诗厚重的文风，宏大叙事，气势磅礴，用词正式庄重。\n"
                "【去AI味要求】避免AI式的四段式结构（背景-冲突-过程-结果）。对话要自然，不要变成「发表演讲」。打斗场面要有节奏变化，不要每场都一样详细。",
    "悬疑紧张": "请使用悬疑紧张的文风，善于营造氛围，短段落制造悬念，多设伏笔。\n"
                "【去AI味要求】不要过度解释悬念，留白让读者自己猜。避免「原来、没想到、竟然」等剧透词。段落更短，一句话一段也可以。",
    "古风典雅": "请使用古风典雅的文风，半文言半白话，多用四字词语和诗词典故。\n"
                "【去AI味要求】避免AI式的「诗云、古人云」模板。古文使用要自然，不要生硬堆砌。对话要根据人物身份区别措辞。",
    "现代白话": "请使用通俗易懂的现代白话文风，贴近生活，自然流畅。\n"
                "【去AI味要求】标点不要过于规范，像真人聊天一样自然。对话要用口语，带口头禅、语气词。段落长短不一。避免AI常见的「总的来说、换言之、值得注意的是」等过渡词。不要每段都解释动机。",
    "暗黑压抑": "请使用暗黑压抑的文风，注重内心独白和环境渲染，氛围阴暗沉重。\n"
                "【去AI味要求】避免过度使用「黑暗、阴冷、恐怖」等形容词堆砌。心理描写要精炼，不要变成内心独白演讲。留出让读者自己感受的空间。",
}
```

- [ ] **Step 2: 修改章节生成 prompt，追加网络小说质感要求**

在 `CHAPTER_GENERATION_PROMPT` 的 template 中追加：

```
【网络小说质感要求】
- 标点灵活：适当使用省略号、破折号，避免句句逗号句号
- 段落打碎：关键动作或对话可单独一段，不要写成工整议论文
- 对话要"像人说话"：带口头禅、吞吞吐吐、话说一半
- 避免AI病：不要出现「顾名思义、毋庸置疑、值得注意的是」等书面衔接词
- 少用"仿佛/似乎/好像"：直接描写，不要猜测式叙述
- 每段不要都以"主角名/他/她"开头，用动作、环境、对话做段首
```

同样修改 `CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT`。

- [ ] **Step 3: 提交代码**

```bash
git add src/core/validation.py src/core/llm/prompts.py
git commit -m "feat: add de-AI-ification instructions to writing style prompts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2: 章节正文后处理清洗函数

**Files:**
- Modify: `src/core/llm/chapter_generator.py`
- Create: `tests/unit/test_chapter_postprocess.py`

- [ ] **Step 1: 编写后处理函数 post_process_chapter**

在 `chapter_generator.py` 末尾添加：

```python
import re

# 需要后处理的 AI 标点/句式模式
_AI_PATTERNS = [
    # 连续多个破折号 → 统一
    (r"——{2,}", "——"),
    # 连续的省略号
    (r"…{4,}", "……"),
    # "首先、其次、最后"等AI结构词 → 替换
    (r"首先[，,]", ""),
    (r"其次[，,]", ""),
    (r"最后[，,]", ""),
    # "值得注意的是/毋庸置疑的是/很显然"等
    (r"值得注意的是[，,]", ""),
    (r"毋庸置疑[，,]", ""),
    (r"很显然[，,]", ""),
    (r"顾名思义[，,]", ""),
    # "总而言之/总的来说"等总结词
    (r"总而言之[，,]", ""),
    (r"总的来说[，,]", ""),
    # 过多的"仿佛/似乎/好像"（保留第一次，第二第三次删除）
    # 需要更复杂的逻辑
]

def post_process_chapter(content: str) -> str:
    """清洗 AI 生成文本中的 AI 味特征
    
    包括：标点规范化、删除AI结构词、优化句式
    """
    for pattern, replacement in _AI_PATTERNS:
        content = re.sub(pattern, replacement, content)
    
    # 去除多余空格和空行
    content = re.sub(r"\n{4,}", "\n\n\n", content)
    content = content.strip()
    
    return content
```

- [ ] **Step 2: 在 generate_single_chapter 返回结果前调用后处理**

在 `chapter_generator.py` 的 `generate_single_chapter()` 函数末尾，`return` 前加上：

```python
    # 后处理：去 AI 味
    if isinstance(result, dict) and result.get("content"):
        result["content"] = post_process_chapter(result["content"])
```

- [ ] **Step 3: 编写后处理测试**

```python
"""章节后处理函数测试"""

from src.core.llm.chapter_generator import post_process_chapter


def test_removes_excessive_dashes():
    result = post_process_chapter("他说——然后——")
    assert "——" in result
    assert "———" not in result  # 不应有3个以上连续


def test_removes_ai_buzzwords():
    text = "值得注意的是，这是一个测试。总的来说，结果不错。"
    result = post_process_chapter(text)
    assert "值得注意的是" not in result
    assert "总的来说" not in result
```

- [ ] **Step 4: 运行测试确认通过**

```bash
poetry run pytest tests/unit/test_chapter_postprocess.py -v
```

Expected: 2 passed

- [ ] **Step 5: 提交代码**

```bash
git add src/core/llm/chapter_generator.py tests/unit/test_chapter_postprocess.py
git commit -m "feat: add post-processing function to de-AI-ify chapter content

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 3: 数据库自动备份脚本

**Files:**
- Create: `scripts/backup-db.sh`
- Server: crontab entry

- [ ] **Step 1: 创建备份脚本**

```bash
#!/bin/bash
# xIaoShuo 数据库自动备份脚本
# 用法: ./scripts/backup-db.sh [backup_dir]

set -e

BACKUP_DIR="${1:-/opt/xiaoshuo/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/xiaoshuo_db_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

echo ">>> 开始数据库备份: $(date)"

# 从 Docker 容器导出 PostgreSQL 数据
docker exec xiaoshuo-db-1 pg_dump -U xiaoshuo xiaoshuo | gzip > "$BACKUP_FILE"

echo ">>> 备份完成: $BACKUP_FILE"
echo ">>> 备份大小: $(du -h "$BACKUP_FILE" | cut -f1)"

# 清理 7 天前的备份
find "$BACKUP_DIR" -name "xiaoshuo_db_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo ">>> 已清理 ${RETENTION_DAYS} 天前的旧备份"

echo ">>> 当前备份列表:"
ls -lh "$BACKUP_DIR"
```

- [ ] **Step 2: 上传脚本到服务器**

```bash
rsync -avz scripts/backup-db.sh root@115.190.142.169:/opt/xiaoshuo/scripts/backup-db.sh
```

- [ ] **Step 3: 服务器上设置 cron，每日凌晨 3:00 备份**

```bash
ssh root@115.190.142.169 "chmod +x /opt/xiaoshuo/scripts/backup-db.sh"
ssh root@115.190.142.169 'echo "0 3 * * * /opt/xiaoshuo/scripts/backup-db.sh >> /opt/xiaoshuo/backups/backup.log 2>&1" | crontab -'
```

- [ ] **Step 4: 测试备份脚本执行**

```bash
ssh root@115.190.142.169 "bash /opt/xiaoshuo/scripts/backup-db.sh"
```

Expected: 备份文件生成在 `/opt/xiaoshuo/backups/`

### Task 4: 前端错误状态覆盖

**Files:**
- Modify: `frontend/src/views/WorldEdit.vue`
- Modify: `frontend/src/views/Characters.vue`
- Modify: `frontend/src/views/Conversation.vue`
- Modify: `frontend/src/views/OutlineEditor.vue`

- [ ] **Step 1: WorldEdit.vue - 添加 error 状态**

添加 error ref，修改 load() 和 save() 加 try/catch：

```javascript
const error = ref('')
const loadError = ref(false)

async function load() {
  loadError.value = false
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/world`)
    if (!res.ok) {
      loadError.value = true
      error.value = '世界观加载失败'
      return
    }
    // ... existing logic
  } catch (e) {
    loadError.value = true
    error.value = '网络错误，无法连接到服务器'
  }
}

async function save() {
  saving.value = true
  saved.value = false
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/world`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
    })
    if (!res.ok) {
      error.value = '保存失败：' + (await res.json().catch(() => ({})).detail || '服务器错误')
      return
    }
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (e) {
    error.value = '网络错误，保存失败'
  } finally {
    saving.value = false
  }
}
```

在模板中 error 非空时显示错误提示：
```vue
<div v-if="error" class="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
  {{ error }}
  <button @click="error = ''; load()" class="ml-2 text-red-500 underline">重试</button>
</div>
```

- [ ] **Step 2: Characters.vue - 添加 error 状态**

同上模式，添加 error ref，load() 和 addCharacter() 加 try/catch。

- [ ] **Step 3: Conversation.vue - 添加 error 状态**

同上模式，确保 sendMessage / loadMessages 在 API 失败时有提示。

- [ ] **Step 4: OutlineEditor.vue - 添加 error 状态**

同上模式，load / save / generate 等操作加 try/catch。

- [ ] **Step 5: 提交代码**

```bash
git add frontend/src/views/WorldEdit.vue frontend/src/views/Characters.vue frontend/src/views/Conversation.vue frontend/src/views/OutlineEditor.vue
git commit -m "fix: add error state handling to WorldEdit, Characters, Conversation, OutlineEditor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 5: 部署到服务器并验证

- [ ] **Step 1: 同步所有改动到服务器** (backend code + frontend build + scripts)

```bash
rsync -avz src/ root@115.190.142.169:/opt/xiaoshuo/src/
rsync -avz scripts/ root@115.190.142.169:/opt/xiaoshuo/scripts/
cd frontend && npm run build && rsync -avz dist/ root@115.190.142.169:/opt/xiaoshuo/frontend/dist/
```

- [ ] **Step 2: 服务器上重启 API 容器**

```bash
ssh root@115.190.142.169 "docker cp src/ xiaoshuo-api-1:/app/src && docker restart xiaoshuo-api-1"
```

- [ ] **Step 3: 验证 API 健康 + 触发章节生成确认后处理生效**

### Task 6: 整体验证

- [ ] **Step 1: 运行全部测试**

```bash
docker exec xiaoshuo-api-1 python -m pytest tests/unit/test_chapter_service.py tests/unit/test_character_volume_world_service.py -q
```

Expected: 51 passed

- [ ] **Step 2: 提交最终代码到 git**

```bash
git add -A && git commit -m "refactor: de-AI-ify prompts, add post-processing, error handling

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
