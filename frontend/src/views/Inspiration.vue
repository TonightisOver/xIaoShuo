<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-neutral-900 to-indigo-950 text-white relative overflow-hidden flex flex-col">
    <!-- Background light circles for Glassmorphism glow effect -->
    <div class="absolute w-72 h-72 rounded-full bg-accent-500/10 blur-[100px] top-10 left-10 animate-pulse pointer-events-none"></div>
    <div class="absolute w-80 h-80 rounded-full bg-indigo-500/10 blur-[120px] bottom-20 right-20 animate-pulse pointer-events-none" style="animation-duration: 6s;"></div>
    <div class="absolute w-60 h-60 rounded-full bg-pink-500/5 blur-[90px] top-1/3 right-1/4 pointer-events-none"></div>

    <!-- Header -->
    <header class="h-16 flex items-center justify-between px-6 border-b border-white/10 backdrop-blur-md sticky top-0 z-40 bg-slate-900/40 select-none">
      <div class="flex items-center gap-2">
        <router-link to="/" class="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <span class="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-accent-400 to-indigo-400">xIaoShuo</span>
          <span class="text-[9px] bg-white/10 text-accent-300 border border-white/10 px-1.5 py-0.5 rounded-full font-medium">灵感向导</span>
        </router-link>
      </div>
      <div class="flex items-center gap-3">
        <router-link to="/" class="text-xs text-neutral-400 hover:text-white transition-colors bg-white/5 border border-white/10 px-3 py-1.5 rounded-lg">
          退出向导
        </router-link>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="flex-1 max-w-4xl w-full mx-auto px-4 py-6 flex flex-col justify-between overflow-hidden relative z-10">
      <!-- Chat history area -->
      <div
        ref="chatHistoryRef"
        class="flex-1 overflow-y-auto space-y-6 pr-2 mb-4 scroll-smooth"
        style="max-height: calc(100vh - 12rem);"
      >
        <div v-for="(msg, idx) in chatHistory" :key="idx" class="space-y-3">
          <!-- AI Message -->
          <div v-if="msg.sender === 'ai'" class="flex items-start gap-3">
            <div class="shrink-0 w-8 h-8 rounded-xl bg-gradient-to-tr from-accent-500 to-indigo-500 flex items-center justify-center shadow-md shadow-accent-500/20 text-xs font-bold text-white select-none">
              AI
            </div>
            <div class="flex-1 space-y-3">
              <!-- Message Bubble -->
              <div class="bg-white/5 border border-white/10 rounded-2xl rounded-tl-none px-4 py-3 shadow-lg backdrop-blur-md text-sm leading-relaxed max-w-[90%] text-neutral-100">
                <p class="whitespace-pre-line">{{ msg.text }}</p>
              </div>

              <!-- Action Area (Tags, selections) -->
              <div v-if="msg.step === currentStep && !msg.completed" class="flex flex-wrap gap-2 max-w-[90%] pt-1 animate-[fadeIn_0.3s_ease-out]">
                <!-- 通用候选（LLM 实时生成）：idea 示例 / 标题 / 简介 / 类型 -->
                <template v-if="[0, 1, 2, 4].includes(currentStep) && currentOptions.length > 0">
                  <button
                    v-for="(opt, oIdx) in currentOptions"
                    :key="oIdx"
                    type="button"
                    :class="currentStep === 2
                      ? 'block w-full text-left p-3 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl text-xs leading-relaxed text-neutral-300 transition-all duration-200 active:scale-[0.99]'
                      : 'px-3.5 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl text-xs font-medium text-accent-200 transition-all duration-200 active:scale-[0.97]'"
                    @click="selectOption(opt)"
                  >
                    {{ opt }}
                  </button>
                </template>

                <!-- Themes Multi-selection（LLM 建议 + 基础标签合并） -->
                <template v-if="currentStep === 3">
                  <div class="w-full space-y-3">
                    <div class="flex flex-wrap gap-2">
                      <button
                        v-for="theme in mergedThemeOptions"
                        :key="theme"
                        type="button"
                        :class="[
                          'px-3 py-1.5 rounded-lg text-xs font-medium border transition-all duration-150',
                          selectedThemes.includes(theme)
                            ? 'bg-accent-600 border-accent-500 text-white'
                            : 'bg-white/5 border-white/10 text-neutral-300 hover:bg-white/10'
                        ]"
                        @click="toggleTheme(theme)"
                      >
                        {{ theme }}
                      </button>
                    </div>
                    <div class="flex gap-2">
                      <input
                        v-model="customThemeInput"
                        type="text"
                        class="bg-white/5 border border-white/10 rounded-lg text-xs px-3 py-1.5 text-white placeholder-neutral-500 focus:outline-none focus:border-accent-500 flex-1"
                        placeholder="自定义主题标签..."
                        @keyup.enter="addCustomTheme"
                      />
                      <button
                        type="button"
                        class="btn-secondary py-1 px-3 text-xs bg-white/10 text-white border-white/10 hover:bg-white/20"
                        @click="addCustomTheme"
                      >
                        添加
                      </button>
                    </div>
                    <button
                      type="button"
                      class="btn-primary w-full py-2 text-xs"
                      :disabled="selectedThemes.length === 0"
                      @click="submitThemes"
                    >
                      确认选择主题 (已选 {{ selectedThemes.length }} 个)
                    </button>
                  </div>
                </template>

                <!-- Confirm / Outline 阶段 -->
                <template v-if="currentStep === 5">
                  <div class="w-full bg-white/5 border border-white/10 rounded-2xl p-5 space-y-4 backdrop-blur-md">
                    <h3 class="text-sm font-semibold bg-clip-text text-transparent bg-gradient-to-r from-accent-400 to-indigo-400 flex items-center gap-1.5">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-accent-400">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                      <span>小说方案大纲</span>
                    </h3>

                    <!-- 收集信息回显 -->
                    <div class="grid grid-cols-2 gap-2 text-[11px]">
                      <div class="bg-white/5 border border-white/10 rounded-lg px-3 py-2">
                        <span class="text-neutral-500">标题</span>
                        <p class="text-accent-200 font-medium mt-0.5">{{ collected.title || '—' }}</p>
                      </div>
                      <div class="bg-white/5 border border-white/10 rounded-lg px-3 py-2">
                        <span class="text-neutral-500">类型</span>
                        <p class="text-indigo-300 font-medium mt-0.5">{{ collected.genre || '—' }}</p>
                      </div>
                    </div>

                    <!-- LLM 生成的大纲（文本） -->
                    <div v-if="outlineText" class="space-y-1">
                      <label class="block text-[11px] text-neutral-400 font-medium">AI 生成大纲（可在创建后于大纲编辑器中细化）</label>
                      <div class="w-full bg-white/5 border border-white/10 rounded-lg p-3 text-xs text-neutral-200 leading-relaxed whitespace-pre-wrap max-h-72 overflow-y-auto">{{ outlineText }}</div>
                    </div>
                    <div v-else class="text-xs text-neutral-400 bg-white/5 border border-white/10 rounded-lg p-3">
                      尚未生成大纲。点击下方「生成大纲预览」，AI 将基于全部对话内容产出完整方案（含前 10 章章节大纲）。
                    </div>

                    <!-- Actions -->
                    <div class="pt-2 flex gap-3">
                      <button
                        type="button"
                        class="btn-secondary flex-1 py-2 text-xs bg-white/5 hover:bg-white/10 text-white border-white/10"
                        :disabled="outlineGenerating"
                        @click="generateOutline"
                      >
                        {{ outlineGenerating ? '大纲生成中...' : (outlineText ? '重新生成大纲' : '生成大纲预览') }}
                      </button>
                      <button
                        type="button"
                        class="btn-primary flex-1 py-2 text-xs bg-gradient-to-r from-accent-600 to-indigo-600 border-0 hover:from-accent-700 hover:to-indigo-700"
                        :disabled="projectCreating"
                        @click="createProject"
                      >
                        确认并创建项目
                      </button>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>

          <!-- User Message -->
          <div v-if="msg.sender === 'user'" class="flex items-start justify-end gap-3">
            <div class="flex-grow flex justify-end">
              <div class="bg-accent-600 border border-accent-500 text-white rounded-2xl rounded-tr-none px-4 py-3 shadow-lg text-sm max-w-[85%] leading-relaxed">
                <p>{{ msg.text }}</p>
              </div>
            </div>
            <div class="shrink-0 w-8 h-8 rounded-xl bg-slate-700 flex items-center justify-center text-xs font-bold text-white select-none">
              我
            </div>
          </div>
        </div>

        <!-- AI Loading / Thinking bubble -->
        <div v-if="aiLoading" class="flex items-start gap-3 animate-pulse">
          <div class="shrink-0 w-8 h-8 rounded-xl bg-gradient-to-tr from-accent-500 to-indigo-500 flex items-center justify-center shadow-md text-xs font-bold text-white select-none">
            AI
          </div>
          <div class="bg-white/5 border border-white/10 rounded-2xl rounded-tl-none px-4 py-3.5 shadow-lg backdrop-blur-md flex items-center gap-2 max-w-[170px]">
            <div class="w-3.5 h-3.5 border-2 border-accent-400 border-t-transparent rounded-full animate-spin"></div>
            <span class="text-xs text-neutral-400">AI 正在构思...</span>
          </div>
        </div>
      </div>

      <!-- User input and settings panel (fixed at bottom) -->
      <div v-if="currentStep < 5" class="bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-4 space-y-4 shadow-xl">
        <!-- Settings (Only shows at appropriate steps) -->
        <div v-if="currentStep === 0" class="flex flex-wrap gap-4 text-xs text-neutral-400 border-b border-white/5 pb-3">
          <div class="flex items-center gap-2">
            <span>字数目标:</span>
            <select v-model="form.target_words" class="bg-white/10 border border-white/10 rounded px-2 py-1 text-white focus:outline-none focus:border-accent-500">
              <option :value="50000" class="bg-slate-900">5万字 (短篇)</option>
              <option :value="100000" class="bg-slate-900">10万字 (中篇)</option>
              <option :value="300000" class="bg-slate-900">30万字 (长篇)</option>
              <option :value="1000000" class="bg-slate-900">100万字 (长篇巨著)</option>
            </select>
          </div>
          <div class="flex items-center gap-2">
            <span>文风倾向:</span>
            <select v-model="form.writing_style" class="bg-white/10 border border-white/10 rounded px-2 py-1 text-white focus:outline-none focus:border-accent-500">
              <option value="轻松幽默" class="bg-slate-900">轻松幽默</option>
              <option value="热血燃向" class="bg-slate-900">热血燃向</option>
              <option value="细腻文艺" class="bg-slate-900">细腻文艺</option>
              <option value="史诗厚重" class="bg-slate-900">史诗厚重</option>
              <option value="悬疑紧张" class="bg-slate-900">悬疑紧张</option>
              <option value="古风典雅" class="bg-slate-900">古风典雅</option>
              <option value="现代白话" class="bg-slate-900">现代白话</option>
            </select>
          </div>
        </div>

        <!-- Progress Indicator -->
        <div class="flex justify-between items-center text-[10px] text-neutral-500 px-1 select-none">
          <span>创意对话进度</span>
          <span>已完成 {{ Math.min(100, Math.round((currentStep / 5) * 100)) }}%</span>
        </div>
        <div class="w-full h-1 bg-white/5 rounded-full overflow-hidden">
          <div
            class="h-full bg-gradient-to-r from-accent-500 to-indigo-500 rounded-full transition-all duration-300"
            :style="{ width: `${(currentStep / 5) * 100}%` }"
          ></div>
        </div>

        <!-- Form submission input -->
        <form @submit.prevent="submitInput" class="flex gap-2">
          <input
            ref="inputBoxRef"
            v-model="userInput"
            type="text"
            class="w-full px-4 py-2.5 bg-white/10 text-white placeholder-neutral-500 border border-white/10 rounded-xl focus:outline-none focus:ring-2 focus:ring-accent-500/20 focus:border-accent-500 focus:bg-white/15 transition-all text-sm animate-none"
            :placeholder="inputPlaceholder"
            :disabled="aiLoading"
            maxlength="1000"
          />
          <button
            type="submit"
            class="btn-primary px-5 py-2.5 flex items-center justify-center shrink-0 rounded-xl bg-gradient-to-r from-accent-600 to-indigo-600 border-0 hover:from-accent-700 hover:to-indigo-700 shadow-md shadow-accent-600/10"
            :disabled="!canSend || aiLoading"
          >
            <span>发送</span>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </form>
      </div>

      <!-- Creation overlay spinner loader -->
      <div v-if="projectCreating" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex flex-col items-center justify-center gap-4">
        <div class="w-10 h-10 border-4 border-accent-500 border-t-transparent rounded-full animate-spin"></div>
        <p class="text-sm font-medium text-neutral-300">正在为您创建小说项目...</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authHeaders } from '../composables/useApi.js'

const router = useRouter()

// ── UI state ─────────────────────────────────────────────
const chatHistoryRef = ref(null)
const inputBoxRef = ref(null)
const aiLoading = ref(false)
const projectCreating = ref(false)
const outlineGenerating = ref(false)

// ── Wizard state（由后端 LLM API 驱动）─────────────────────
// 后端步骤: idea → title → description → theme → genre → confirm
// 前端 UI 步: 0=idea 1=title 2=description 3=theme(多选) 4=genre 5=confirm/大纲
const BACKEND_STEPS = ['idea', 'title', 'description', 'theme', 'genre']
const sessionId = ref('')
const currentStep = ref(0)
const userInput = ref('')
const currentOptions = ref([])   // 每步 LLM 实时生成的候选
const collected = ref({})        // 后端已收集的上下文
const outlineText = ref('')      // LLM 生成的大纲文本

const form = reactive({
  target_words: 100000,
  writing_style: '现代白话',
})

const selectedThemes = ref([])
const customThemeInput = ref('')

// 主题多选的基础标签（LLM 建议会合并进来）
const themeOptions = [
  '爽文', '热血', '轻松', '硬核', '扮猪吃虎', '反抗财阀', '宇宙探险', '重生逆袭',
  '基建种田', '稳健发育', '基因进化', '系统流', '神秘复苏', '诡异规则', '快意恩仇'
]

const mergedThemeOptions = computed(() => {
  // LLM 生成的主题建议排前面，基础标签排后面，去重
  const llm = currentOptions.value.filter(t => t && t.length <= 12)
  return [...new Set([...llm, ...themeOptions])]
})

const chatHistory = ref([])

const canSend = computed(() => {
  if (currentStep.value === 0) return userInput.value.trim().length >= 10
  return userInput.value.trim().length > 0
})

const inputPlaceholder = computed(() => {
  switch (currentStep.value) {
    case 0: return '请输入核心想法（最少 10 个字）...'
    case 1: return '点击 AI 推荐标题，或在此输入自定义标题...'
    case 2: return '点击 AI 推荐简介，或在此输入自定义简介...'
    case 3: return '请在上面勾选主题标签...'
    case 4: return '选择推荐类型，或在此输入自定义类型...'
    default: return '向导已完成，请在上方确认...'
  }
})

// ── helpers ─────────────────────────────────────────────
function scrollToBottom() {
  nextTick(() => {
    if (chatHistoryRef.value) {
      chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight
    }
  })
}

watch(() => chatHistory.value.length, scrollToBottom)
watch(aiLoading, scrollToBottom)

function pushAi(text, step) {
  chatHistory.value.push({ sender: 'ai', text, step, completed: false })
}

function pushUser(text, step) {
  chatHistory.value.push({ sender: 'user', text, step })
}

function completeCurrentAiMsg() {
  const prevMsg = chatHistory.value.find(
    m => m.step === currentStep.value && m.sender === 'ai' && !m.completed
  )
  if (prevMsg) prevMsg.completed = true
}

// ── 后端 API 调用 ────────────────────────────────────────
async function startSession() {
  aiLoading.value = true
  try {
    const res = await fetch('/api/v1/inspiration/start', { method: 'POST' })
    if (!res.ok) throw new Error('启动灵感会话失败')
    const data = await res.json()
    sessionId.value = data.session_id
    currentOptions.value = data.options || []
    pushAi(
      data.ai_reply +
        '\n\n下面是几个方向示例，点击可直接采用，也可以自由输入你的想法（最少 10 个字）。',
      0,
    )
  } catch (e) {
    pushAi('灵感服务暂时不可用，请稍后刷新重试。' + (e.message ? `（${e.message}）` : ''), 0)
  } finally {
    aiLoading.value = false
  }
}

async function callStep(backendStep, text) {
  const res = await fetch(`/api/v1/inspiration/${sessionId.value}/step`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ step: backendStep, user_input: text }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '处理失败')
  }
  return res.json()
}

// ── 交互处理 ─────────────────────────────────────────────
function selectOption(val) {
  userInput.value = val
  submitInput()
}

function toggleTheme(theme) {
  const index = selectedThemes.value.indexOf(theme)
  if (index > -1) {
    selectedThemes.value.splice(index, 1)
  } else {
    selectedThemes.value.push(theme)
  }
}

function addCustomTheme() {
  const t = customThemeInput.value.trim()
  if (t && !selectedThemes.value.includes(t)) {
    selectedThemes.value.push(t)
    customThemeInput.value = ''
  }
}

async function submitThemes() {
  if (selectedThemes.value.length === 0) return
  const text = selectedThemes.value.join('、')
  await advanceStep(text)
}

async function submitInput() {
  const text = userInput.value.trim()
  if (!text) return
  userInput.value = ''
  await advanceStep(text)
}

async function advanceStep(text) {
  if (aiLoading.value || currentStep.value >= BACKEND_STEPS.length) return

  const backendStep = BACKEND_STEPS[currentStep.value]
  pushUser(text, currentStep.value)
  completeCurrentAiMsg()
  aiLoading.value = true

  try {
    const data = await callStep(backendStep, text)
    collected.value = data.collected || {}
    currentStep.value += 1
    currentOptions.value = data.options || []

    if (data.next_step === null || currentStep.value >= 5) {
      // 全部收集完成 → confirm/大纲阶段
      currentStep.value = 5
      pushAi(data.ai_reply, 5)
    } else {
      pushAi(data.ai_reply, currentStep.value)
    }
  } catch (e) {
    // 失败不推进步骤：提示重试，用户输入不丢（重新填入输入框）
    userInput.value = text
    pushAi(`处理出错：${e.message}。请稍后重新发送。`, currentStep.value)
  } finally {
    aiLoading.value = false
  }
}

async function generateOutline() {
  if (outlineGenerating.value) return
  outlineGenerating.value = true
  try {
    const res = await fetch(`/api/v1/inspiration/${sessionId.value}/generate`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error('大纲生成失败')
    const data = await res.json()
    outlineText.value = data.outline || ''
  } catch (e) {
    alert(e.message || '大纲生成失败，请重试。')
  } finally {
    outlineGenerating.value = false
  }
}

async function createProject() {
  projectCreating.value = true
  try {
    const res = await fetch(`/api/v1/inspiration/${sessionId.value}/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ target_words: form.target_words }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '创建项目失败')
    }
    const { novel_id } = await res.json()

    // 补写文风偏好（后端 create 不含 writing_style；失败静默不阻断）
    try {
      await fetch(`/api/v1/projects/${novel_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ writing_style: form.writing_style }),
      })
    } catch { /* 非关键，静默 */ }

    router.push(`/novels/${novel_id}`)
  } catch (e) {
    alert(e.message || '创建项目出错，请重试。')
  } finally {
    projectCreating.value = false
  }
}

onMounted(() => {
  startSession()
  if (inputBoxRef.value) {
    inputBoxRef.value.focus()
  }
})
</script>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
