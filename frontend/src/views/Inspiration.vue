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
  const dict = {
    cyber: {
      titles: [
        '《赛博仙途：我用义肢代替灵根》',
        '《深空修真：核聚变飞升计划》',
        '《霓虹之下，皆为蝼蚁：机械飞升的都市剑仙》'
      ],
      descriptions: [
        `在霓虹闪烁的赛博朋克废土都市中，传统灵气早已消亡。主角作为一名底层的赛博黑客，意外发现通过高精度的纳米机械臂与义体芯片，可以模拟出远古传说中的“周天经脉”。为了打破财阀的绝对统治，他用义肢重开仙路，剑斩机甲。`,
        `当天道被编译为一行行冰冷的底层逻辑，修仙沦为财阀高层的专利。主角偶然下载了远古野火修真编译器，以恒星核心作炉鼎，以主板走经络，在太空中拉开了一场属于全人类的“物理飞升”狂潮。`,
        `赛博义体是魔障，还是通向大道的通天桥？主角身患经脉破损恶疾，通过给身体改装开源修仙义体完美解决了修行缺陷。在基因工程与超凡权柄的博弈中，主角打断财阀神像，开创机械剑仙流派。`
      ],
      defaultThemes: ['硬核科幻', '反抗财阀', '科技与修仙'],
      type: '科幻'
    },
    xianxia: {
      titles: [
        '《万劫仙主：从长生开始无敌》',
        '《逆反天命：我的功法能自动顿悟》',
        '《大荒纪元：我有一座诸天神殿》'
      ],
      descriptions: [
        `仙路漫漫，万骨皆枯。资质平平的杂役主角，觉醒了功法挂机顿悟系统。当其他修士为了一粒丹药抢破头时，主角的功法每天都在识海中自我迭代变强。在稳健中发育，直到手握天地寰宇。`,
        `顺天为凡，逆天为仙。世间仙门大宗皆为利益奴仆，天道降灾蚕食世间凡尘。主角在逆境中得到古神石碑，从此手握灭世魔兵，斩碎不公宿命，杀上九重云霄。`,
        `灵气复苏的荒蛮大荒，远古妖神苏醒。主角携神秘诸天神殿碎片，收纳天下失落的古老遗迹与至宝，重新构建正道天理，荡平邪魔外道。`
      ],
      defaultThemes: ['稳健发育', '逆天改命', '快意恩仇'],
      type: '仙侠'
    },
    apocalypse: {
      titles: [
        '《末世求生：我的避难所能无限升级》',
        '《废土狂潮：开局一辆基地车》',
        '《基因禁区：无限吞噬进化》'
      ],
      descriptions: [
        `丧尸狂潮降临，极寒笼罩全球。人类社会文明分崩离析。主角继承了一座带有神秘科技内核的地下避难所。从最初漏雨的防空洞，一步步升级到配备生态农场、聚变电站和近防机炮的终极末日壁垒。`,
        `废土辐射区，巨兽盘踞，狂暴掠夺者出没。主角获得一辆可全自动装配、机动的重装基地车。搜集铁矿与反应源，源源不断地产出无惧生死的机械兵团，在焦黑大地建立秩序帝邦。`,
        `天外陨石带来了古怪的灾变尘埃，动植物急速进化，人类沦为底层。主角垂死之际，觉醒了基因吞噬特质，可夺取其他变异生物的核心能力，踩在物种演变阶梯上不断向上狂奔。`
      ],
      defaultThemes: ['末日求生', '基建种田', '基因进化'],
      type: '科幻'
    },
    mystery: {
      titles: [
        '《怪谈游戏：我有诡异修改器》',
        '《神秘复苏：我能看见死者遗言》',
        '《深夜书屋：诡异请闭眼》'
      ],
      descriptions: [
        `怪谈世界降临，人命如草芥，遵守规则是唯一的生存法则。被拉入怪谈空间的普通人主角，意外加载了诡异编辑器外挂，能够修改、伪造诡异空间的底层规则，令惊悚世界的厉鬼陷入逻辑死循环。`,
        `百鬼夜行，秩序崩溃。面对重重杀机，主角的一双鬼眼却能够穿透时间，洞悉亡者临时前的绝望回忆。依靠着死人留下的情报漏洞，他在步步死局的凶地里，与恶诡做博弈。`,
        `街角有一间深夜才开张的书屋，接待的从来不是活人。每一本书都记录着一段执念鬼魂的不平之事。主角化渡亡魂，平定人间阴阳纷乱，在此过程中超脱彼岸。`
      ],
      defaultThemes: ['诡异规则', '惊悚悬疑', '神秘复苏'],
      type: '悬疑'
    },
    urban: {
      titles: [
        '《都市逍遥神医》',
        '《我有万界交换群》',
        '《隐世宗门：我的弟子全是玩家》'
      ],
      descriptions: [
        `落魄实习医生主角偶得旷世玄医武道传承。在危机四伏的都市洪流中，他游刃于各大豪门巨擘之间，施针救人，铁拳除恶，登临红尘逍遥王座。`,
        `一只神秘的新手机突然加入了一个跨越诸天万界的群聊。主角拿红薯换金丹，拿充电宝换钢铁侠战衣。用万界特产横扫都市，成就首富与最强神话。`,
        `在灵力断代的世界，主角为拯救自家道观，设计出了“超高保真沉浸式游戏”，召唤了一群无畏又爱整活的地球玩家降临。这群第四天灾在现实与修仙的交界里，直接降维打击一切强敌。`
      ],
      defaultThemes: ['扮猪吃虎', '都市爽文', '系统流'],
      type: '都市'
    },
    general: {
      titles: [
        '《独步万界：从破败小镇开始》',
        '《逆袭之路：开局先扣满好感度》',
        '《星河主宰：我的灵力无上限》'
      ],
      descriptions: [
        `一个波澜壮阔的玄奇世界，万族林立。从边境小镇走出的平凡少年，在历经无数艰难险阻与偶得的至宝机缘下，踏遍万界，逆天改命，最终登临至尊。`,
        `主角意外穿越危险重重的异界，开局竟是天谴孤星，全服好感度为负。主角依靠极高智商，借力打力，疯狂调戏并击退反派，走出一条奇葩搞怪的逆袭之路。`,
        `星河浩渺，宇宙灵能如织。所有修行者都因气海极限而停滞，唯独主角丹田宛如太虚黑洞，容纳星河灵力。一拳之下，星骸粉碎，主宰虚空。`
      ],
      defaultThemes: ['热血逆袭', '稳健发育', '轻松'],
      type: '玄幻'
    }
  }

  const selection = dict[category] || dict.general
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
function generateMasterOutlineTemplate(category, title, idea, selectedThemes, novelType) {
  switch (category) {
    case 'cyber':
      return {
        premise: `在赛博朋克都市的高科技阴影下，${idea}。主角利用义体编译功法，以凡人之躯对抗垄断财阀的压迫。`,
        main_conflict: "垄断巨头对基因与义体的垄断控制，与主角所代表的开源、自由修真力量之间的阶级对立与信仰冲突。",
        themes: [...selectedThemes, "科技与修仙", "反抗财阀", "硬核科幻"],
        ending: "主角带领底层义体修士攻陷财阀的太空总部，上传“全民修真编译协议”，开启了星际时代的量子修仙时代。",
        plot_arcs: [
          { name: "第一卷：贫民窟的芯片微光", description: "主角在垃圾场重组开源义体，破译第一层算法功法，解决当地帮派冲突。" },
          { name: "第二卷：义体财阀的猎杀令", description: "因为推广开源修仙程序，遭到财阀武装的围剿。主角深入义体黑市，开发出机甲御剑术对抗财阀机甲。" },
          { name: "第三卷：攻陷天顶之城", description: "联合地下反抗军，主角杀上太空轨道站，击败财阀掌控的“机械天道”，解放整座城市。" }
        ]
      }
    case 'xianxia':
      return {
        premise: `远古洪荒，灵气飘零。${idea}。这是一个逆天改命、顿悟求索的传统神话修仙旅程。`,
        main_conflict: "天道棋局视众生为棋子，主角为了打破命运的枷锁，不得不与满天仙神以及腐朽的宗门制度为敌。",
        themes: [...selectedThemes, "逆天改命", "法宝探秘", "快意恩仇"],
        ending: "斩断天道傀儡锁链，以自身法相重塑世界规则，建立人神平等的万世太平。",
        plot_arcs: [
          { name: "第一卷：仙门微澜", description: "宗门大比，主角展露挂机顿悟功法，击败冷酷对手，获得古神遗物。" },
          { name: "第二卷：横渡十万荒山", description: "古神遗物引来仙门追杀。主角转战荒野，深入禁区，收服异兽，实力大增。" },
          { name: "第三卷：逆战九天", description: "主角杀回仙门，揭露天道吸食人间气运的阴谋，粉碎天道祭坛，傲立群山之巅。" }
        ]
      }
    case 'apocalypse':
      return {
        premise: `冰封丧尸，废土求生。${idea}。依靠强悍的避难所/基地系统，主角在文明覆灭的荒芜世界中，播撒希望之光。`,
        main_conflict: "极端灾难环境下，稀缺资源匮乏引发的人性沦丧、变异兽狂潮，以及主角的绿洲基地生存发展之间的尖锐对立。",
        themes: [...selectedThemes, "基建爆兵", "末日求生", "基因进化"],
        ending: "彻底研制出抗体，或者让基地净化整片大陆，带领幸存人类走出地下，重建文明。",
        plot_arcs: [
          { name: "第一卷：寒冬微澜", description: "天灾降临，丧尸暴动。主角利用避难所系统建立第一条自动化防御防线，拯救周边幸存者。" },
          { name: "第二卷：废土远征", description: "资源耗尽，主角开动重装基地车横穿废土，搜集核能核心，沿途收编其他避难所。" },
          { name: "第三卷：纪元之光", description: "变异尸王围攻总部。主角带领爆兵军团迎战，击溃尸潮，并启动超级净化塔，恢复地表生态。" }
        ]
      }
    case 'mystery':
      return {
        premise: `神秘复苏，厉鬼夜行。${idea}。游走在光明与黑暗之间，主角通过洞悉诡异漏洞，守护最后的防线。`,
        main_conflict: "诡异规则的不可直视与不可抗力，同主角仅有的凡人之躯、以及被污染的灵异力量之间的殊死抗争。",
        themes: [...selectedThemes, "规则怪谈", "神秘复苏", "惊悚悬疑"],
        ending: "主角牺牲一部分人性，将自己编译进诡异规则中，成为了约束众鬼的“规则判官”，换来人间宁静。",
        plot_arcs: [
          { name: "第一卷：死亡回音", description: "遭遇首个灵异副本（如古怪公寓），主角破解隐藏遗言，利用规则反杀诡异。" },
          { name: "第二卷：调查局的钟声", description: "加入神秘案件调查局，处理城市中多起诡异复苏事件，追寻幕后邪教的踪迹。" },
          { name: "第三卷：终焉怪谈", description: "进入源头裂隙。主角在众神魔视线中，依靠怪谈编辑器改写终极怪谈规则，封印源头。" }
        ]
      }
    case 'urban':
      return {
        premise: `繁华都市，卧虎藏龙。${idea}。主角通过系统或者奇遇在红尘之中行侠仗义，书写传奇。`,
        main_conflict: "隐藏在都市背后的神秘武道家族、异能组织与主角在普通人秩序、商业帝国的扩张中爆发的明争暗斗。",
        themes: [...selectedThemes, "都市爽文", "扮猪吃虎", "系统流"],
        ending: "击败境外异能寡头，登临华夏武道巅峰，建立涵盖商业与超凡秩序的庞大财团。",
        plot_arcs: [
          { name: "第一卷：红尘初露", description: "主角获得传承重回都市，通过绝世医术与武力解决家族危机，结识各路贵人。" },
          { name: "第二卷：暗流激荡", description: "主角遭遇古老武道世家的联合打压。他在商战与超凡对决中双重反击，反吞对手产业。" },
          { name: "第三卷：名动华夏", description: "打破境外武道联盟的封锁，斩杀幕后大宗师，确立都市至高无上的盟主地位。" }
        ]
      }
    default:
      return {
        premise: `波澜壮阔的世界中，${idea}。这是一位平凡少年的非凡逆袭与世界探索之旅。`,
        main_conflict: "世界的层层禁锢与主角对自由、力量的不懈追求之间的矛盾。",
        themes: [...selectedThemes, "热血逆袭", "稳健发育"],
        ending: "主角游历万界，解开世界起源的真相，最终掌握至高力量，破虚空而去。",
        plot_arcs: [
          { name: "第一卷：起于微末", description: "主角在小镇崛起，通过坚毅性格和突发奇遇，战胜欺压者，走向更大的舞台。" },
          { name: "第二卷：风起四海", description: "游历大荒，解决多方势力纷争，结交知己，实力达到当世顶峰。" },
          { name: "第三卷：万界称尊", description: "面对灭世危机，主角挺身而出，联合百族对抗域外天魔，踏碎星河，终得长生。" }
        ]
      }
  }
}

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
