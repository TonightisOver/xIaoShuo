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
                <!-- Title Selection -->
                <template v-if="currentStep === 1 && suggestions.titles.length > 0">
                  <button
                    v-for="title in suggestions.titles"
                    :key="title"
                    type="button"
                    class="px-3.5 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl text-xs font-medium text-accent-200 transition-all duration-200 active:scale-[0.97]"
                    @click="selectOption(title)"
                  >
                    {{ title }}
                  </button>
                </template>

                <!-- Description Selection -->
                <template v-if="currentStep === 2 && suggestions.descriptions.length > 0">
                  <button
                    v-for="(desc, dIdx) in suggestions.descriptions"
                    :key="dIdx"
                    type="button"
                    class="block w-full text-left p-3 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl text-xs leading-relaxed text-neutral-300 transition-all duration-200 active:scale-[0.99]"
                    @click="selectOption(desc)"
                  >
                    {{ desc }}
                  </button>
                </template>

                <!-- Themes Multi-selection -->
                <template v-if="currentStep === 3">
                  <div class="w-full space-y-3">
                    <div class="flex flex-wrap gap-2">
                      <button
                        v-for="theme in themeOptions"
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

                <!-- Novel Type Selection -->
                <template v-if="currentStep === 4">
                  <button
                    v-for="type in novelTypes"
                    :key="type"
                    type="button"
                    class="px-3.5 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl text-xs font-medium text-indigo-300 transition-all duration-200 active:scale-[0.97]"
                    @click="selectOption(type)"
                  >
                    {{ type }}
                  </button>
                </template>

                <!-- Outline Preview / Editor Card -->
                <template v-if="currentStep === 5">
                  <div class="w-full bg-white/5 border border-white/10 rounded-2xl p-5 space-y-4 backdrop-blur-md">
                    <h3 class="text-sm font-semibold bg-clip-text text-transparent bg-gradient-to-r from-accent-400 to-indigo-400 flex items-center gap-1.5">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-accent-400">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                      <span>小说核心大纲预览</span>
                    </h3>

                    <!-- Premise -->
                    <div class="space-y-1">
                      <label class="block text-[11px] text-neutral-400 font-medium">基本设定 / Premise</label>
                      <textarea
                        v-model="outline.premise"
                        class="w-full bg-white/5 border border-white/10 rounded-lg p-2.5 text-xs text-neutral-200 focus:outline-none focus:border-accent-500 resize-none min-h-[60px]"
                      ></textarea>
                    </div>

                    <!-- Main Conflict -->
                    <div class="space-y-1">
                      <label class="block text-[11px] text-neutral-400 font-medium">核心冲突 / Main Conflict</label>
                      <textarea
                        v-model="outline.main_conflict"
                        class="w-full bg-white/5 border border-white/10 rounded-lg p-2.5 text-xs text-neutral-200 focus:outline-none focus:border-accent-500 resize-none min-h-[60px]"
                      ></textarea>
                    </div>

                    <!-- Themes -->
                    <div class="space-y-1">
                      <label class="block text-[11px] text-neutral-400 font-medium">大纲主题词 / Themes</label>
                      <div class="flex flex-wrap gap-1.5 p-2 bg-white/5 border border-white/10 rounded-lg text-xs min-h-[36px]">
                        <span v-for="t in outline.themes" :key="t" class="bg-indigo-900/40 text-indigo-200 border border-indigo-700/30 px-2 py-0.5 rounded-md text-[10px]">
                          {{ t }}
                        </span>
                      </div>
                    </div>

                    <!-- Ending -->
                    <div class="space-y-1">
                      <label class="block text-[11px] text-neutral-400 font-medium">大结局走向 / Ending</label>
                      <textarea
                        v-model="outline.ending"
                        class="w-full bg-white/5 border border-white/10 rounded-lg p-2.5 text-xs text-neutral-200 focus:outline-none focus:border-accent-500 resize-none min-h-[60px]"
                      ></textarea>
                    </div>

                    <!-- Plot Arcs -->
                    <div class="space-y-2">
                      <label class="block text-[11px] text-neutral-400 font-medium">情节分卷弧线 / Plot Arcs</label>
                      <div class="space-y-2">
                        <div v-for="(arc, aIdx) in outline.plot_arcs" :key="aIdx" class="p-2.5 bg-white/5 border border-white/10 rounded-lg space-y-1.5">
                          <input
                            v-model="arc.name"
                            type="text"
                            class="w-full bg-transparent border-b border-white/10 pb-1 text-xs text-accent-300 font-medium focus:outline-none focus:border-accent-500"
                          />
                          <textarea
                            v-model="arc.description"
                            class="w-full bg-transparent text-[11px] text-neutral-400 focus:outline-none focus:ring-0 resize-none min-h-[40px] pt-1"
                          ></textarea>
                        </div>
                      </div>
                    </div>

                    <!-- Submit action inside outline step -->
                    <div class="pt-2 flex gap-3">
                      <button
                        type="button"
                        class="btn-secondary flex-1 py-2 text-xs bg-white/5 hover:bg-white/10 text-white border-white/10"
                        @click="regenerateOutline"
                      >
                        重新生成大纲
                      </button>
                      <button
                        type="button"
                        class="btn-primary flex-1 py-2 text-xs bg-gradient-to-r from-accent-600 to-indigo-600 border-0 hover:from-accent-700 hover:to-indigo-700"
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
              <!-- Message Bubble -->
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
          <div class="bg-white/5 border border-white/10 rounded-2xl rounded-tl-none px-4 py-3.5 shadow-lg backdrop-blur-md flex items-center gap-2 max-w-[150px]">
            <!-- Spinner -->
            <div class="w-3.5 h-3.5 border-2 border-accent-400 border-t-transparent rounded-full animate-spin"></div>
            <span class="text-xs text-neutral-400">正在思考建议...</span>
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
        <p class="text-sm font-medium text-neutral-300">正在为您创建小说项目，生成大纲中...</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSuggestion, generateMasterOutlineTemplate } from './inspirationPresets.js'

const router = useRouter()

// UI state
const chatHistoryRef = ref(null)
const inputBoxRef = ref(null)
const aiLoading = ref(false)
const projectCreating = ref(false)

// Workflow State
const currentStep = ref(0)
const userInput = ref('')

const form = reactive({
  title: '',
  idea: '',
  novel_type: '科幻',
  target_words: 100000,
  writing_style: '现代白话',
})

const selectedThemes = ref([])
const customThemeInput = ref('')

const suggestions = reactive({
  category: 'general', // Matching category from analyzer
  titles: [],
  descriptions: [],
})

const outline = reactive({
  premise: '',
  main_conflict: '',
  themes: [],
  ending: '',
  plot_arcs: []
})

// Setup base dictionaries and templates
const themeOptions = [
  '爽文', '热血', '轻松', '硬核', '扮猪吃虎', '反抗财阀', '宇宙探险', '重生逆袭',
  '基建种田', '稳健发育', '基因进化', '系统流', '神秘复苏', '诡异规则', '快意恩仇'
]

const novelTypes = ['玄幻', '仙侠', '都市', '科幻', '历史', '武侠', '言情', '悬疑', '军事', '游戏', '竞技', '灵异', '同人']

// Initial conversation script
const chatHistory = ref([
  {
    sender: 'ai',
    text: '您好！我是您的小说创作助手。期待与您共同探索无限创意。\n\n请先告诉我您的小说“核心脑洞”或“创意火花”吧。例如：“我想写一个在赛博朋克都市修仙的故事，主角义体可以模拟经脉。”（请至少输入 10 个字）',
    step: 0,
    completed: false
  }
])

const canSend = computed(() => {
  if (currentStep.value === 0) return userInput.value.trim().length >= 10
  return userInput.value.trim().length > 0
})

const inputPlaceholder = computed(() => {
  switch (currentStep.value) {
    case 0: return '请输入核心想法（最少 10 个字）...'
    case 1: return '选择推荐标题，或在此输入自定义标题...'
    case 2: return '选择推荐简介，或在此输入自定义简介...'
    case 3: return '请在上面勾选主题标签...'
    case 4: return '选择推荐类型，或在此输入自定义类型...'
    default: return '向导已完成，请在下方确认...'
  }
})

// Scroll chat to bottom on updates
function scrollToBottom() {
  nextTick(() => {
    if (chatHistoryRef.value) {
      chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight
    }
  })
}

watch(() => chatHistory.value.length, scrollToBottom)
watch(aiLoading, scrollToBottom)

onMounted(() => {
  if (inputBoxRef.value) {
    inputBoxRef.value.focus()
  }
})

// NLP theme category analyzer inside front-end
function analyzeCategory(ideaText) {
  const idea = ideaText.toLowerCase()
  if (['赛博', '科幻', '机械', '机甲', '芯片', '科技', '宇宙', '星际', '霓虹', '飞船', '程序员'].some(k => idea.includes(k))) {
    return 'cyber'
  }
  if (['修仙', '仙侠', '修真', '飞升', '灵气', '道友', '渡劫', '仙门', '功法', '宗门'].some(k => idea.includes(k))) {
    return 'xianxia'
  }
  if (['末日', '末世', '生存', '求生', '丧尸', '废土', '变异', '避难所', '堡垒'].some(k => idea.includes(k))) {
    return 'apocalypse'
  }
  if (['悬疑', '灵异', '诡', '鬼', '恐怖', '怪谈', '惊悚', '推理', '破案', '凶手'].some(k => idea.includes(k))) {
    return 'mystery'
  }
  if (['都市', '系统', '神豪', '医生', '校花', '逆袭', '神医', '好感度', '聊天群'].some(k => idea.includes(k))) {
    return 'urban'
  }
  return 'general'
}

// Simulated response engine based on theme analyzed
function fetchSuggestions(category, userIdea) {
  const selection = getSuggestion(category)
  suggestions.category = category
  suggestions.titles = selection.titles
  suggestions.descriptions = selection.descriptions

  // Set default type matching the suggestion
  form.novel_type = selection.type
  selectedThemes.value = [...selection.defaultThemes]
}

// User clicked a suggested tag / option
function selectOption(val) {
  userInput.value = val
  submitInput()
}

// Toggle multi-select themes
function toggleTheme(theme) {
  const index = selectedThemes.value.indexOf(theme)
  if (index > -1) {
    selectedThemes.value.splice(index, 1)
  } else {
    selectedThemes.value.push(theme)
  }
}

// Add user custom theme
function addCustomTheme() {
  const t = customThemeInput.value.trim()
  if (t && !themeOptions.includes(t) && !selectedThemes.value.includes(t)) {
    selectedThemes.value.push(t)
    customThemeInput.value = ''
  }
}

// Multi-select theme confirmation step
function submitThemes() {
  if (selectedThemes.value.length === 0) return
  
  chatHistory.value.push({
    sender: 'user',
    text: `我选择的主题为: ${selectedThemes.value.join(', ')}`,
    step: 3
  })

  // Mark previous step as completed
  const prevMsg = chatHistory.value.find(m => m.step === 3 && m.sender === 'ai')
  if (prevMsg) prevMsg.completed = true

  aiLoading.value = true
  setTimeout(() => {
    aiLoading.value = false
    currentStep.value = 4
    chatHistory.value.push({
      sender: 'ai',
      text: `收到！主题定位十分精准。接下来是“小说类型”。我们根据上面的设定，默认为您匹配了「${form.novel_type}」大类。您觉得合适吗？您也可以选择其他的，或者在下方自己输入：`,
      step: 4,
      completed: false
    })
  }, 1000)
}

// Generate outline base data model

// Generate / Regenerate Outline
function rebuildOutline() {
  const generated = generateMasterOutlineTemplate(
    suggestions.category,
    form.title,
    form.idea,
    selectedThemes.value,
    form.novel_type
  )
  
  outline.premise = generated.premise
  outline.main_conflict = generated.main_conflict
  outline.themes = generated.themes
  outline.ending = generated.ending
  outline.plot_arcs = generated.plot_arcs
}

function regenerateOutline() {
  aiLoading.value = true
  setTimeout(() => {
    aiLoading.value = false
    rebuildOutline()
  }, 1000)
}

// Action submit from footer text box
function submitInput() {
  const text = userInput.value.trim()
  if (!text) return

  userInput.value = ''
  
  // 1. Record user response in history
  chatHistory.value.push({
    sender: 'user',
    text: text,
    step: currentStep.value
  })

  // Mark previous AI message completed
  const prevMsg = chatHistory.value.find(m => m.step === currentStep.value && m.sender === 'ai')
  if (prevMsg) prevMsg.completed = true

  // 2. Drive flow steps
  aiLoading.value = true

  if (currentStep.value === 0) {
    // Stage 0: Input Idea -> Trigger analyzers and return suggested Titles
    form.idea = text
    const category = analyzeCategory(text)
    fetchSuggestions(category, text)

    setTimeout(() => {
      aiLoading.value = false
      currentStep.value = 1
      chatHistory.value.push({
        sender: 'ai',
        text: `非常出色的创意想法！我为您分析的流派为「${form.novel_type || '其他'}」。\n\n为了给小说起个好名字，我构思了 3 个创意标题。您可以点击选择，或者自己输入喜欢的标题名：`,
        step: 1,
        completed: false
      })
    }, 1200)

  } else if (currentStep.value === 1) {
    // Stage 1: Title Selected -> Fetch Suggested Descriptions
    form.title = text.replace(/《|》/g, '') // strip title brackets if any

    setTimeout(() => {
      aiLoading.value = false
      currentStep.value = 2
      chatHistory.value.push({
        sender: 'ai',
        text: `「${form.title}」这名字很有代入感！\n\n接着，我针对标题和您的原始想法，写了 3 个不同视角的小说背景简介。请点击选择，或自行修饰：`,
        step: 2,
        completed: false
      })
    }, 1200)

  } else if (currentStep.value === 2) {
    // Stage 2: Description Selected -> Go to Multi-select Themes
    form.idea = text // Override idea to cleaner description selection

    setTimeout(() => {
      aiLoading.value = false
      currentStep.value = 3
      chatHistory.value.push({
        sender: 'ai',
        text: `简介描述已就绪。为了让 AI 在大纲中融入特定的元素，请给小说选择 2~4 个主题词标签。您也可以在下方自己添加新标签：`,
        step: 3,
        completed: false
      })
    }, 1000)

  } else if (currentStep.value === 4) {
    // Stage 4: Novel Type Chosen -> Build Outline drafts and present outline UI
    form.novel_type = text

    setTimeout(() => {
      aiLoading.value = false
      currentStep.value = 5
      rebuildOutline()
      
      chatHistory.value.push({
        sender: 'ai',
        text: `大功告成！我已经为您量身定制了一份核心小说大纲草稿。包含基本设定、冲突走向以及分卷情节大纲。您可以在下面进行任意编辑，确认无误后点击“确认并创建项目”：`,
        step: 5,
        completed: false
      })
    }, 1500)
  }
}

// Call backends to perform project setup
async function createProject() {
  projectCreating.value = true
  try {
    // Step 1: POST to /api/v1/projects to set up baseline Novel Metadata
    const novelPayload = {
      idea: form.idea,
      novel_type: form.novel_type,
      target_words: form.target_words,
      title: form.title,
      writing_style: form.writing_style,
      custom_style_description: '',
      writing_style_prompt: ''
    }

    const novelRes = await fetch('/api/v1/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(novelPayload),
    })

    if (!novelRes.ok) {
      const errData = await novelRes.json()
      throw new Error(errData.detail || '小说项目初始化失败')
    }

    const { novel_id } = await novelRes.json()

    // Step 2: PUT Outline data structure to backend /api/v1/projects/{novel_id}/outlines/master
    const outlinePayload = {
      premise: outline.premise,
      main_conflict: outline.main_conflict,
      plot_arcs: outline.plot_arcs.map(arc => ({
        volume_number: 1, // backend structure support
        title: arc.name,
        summary: arc.description
      })),
      ending: outline.ending,
      themes: outline.themes
    }

    const outlineRes = await fetch(`/api/v1/projects/${novel_id}/outlines/master`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(outlinePayload),
    })

    if (!outlineRes.ok) {
      // Log outline sync error but don't crash routing
      console.error('Failed to sync master outline:', await outlineRes.text())
    }

    // Step 3: Route user to the NovelDetail workspace view
    router.push(`/novels/${novel_id}`)

  } catch (e) {
    alert(e.message || '创建项目出错，请重试。')
  } finally {
    projectCreating.value = false
  }
}
</script>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
