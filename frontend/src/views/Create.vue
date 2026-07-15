<template>
  <div class="max-w-2xl mx-auto px-6 py-8 animate-fade-up">
    <div class="mb-8">
      <h1 class="heading-serif text-2xl">开启新篇章</h1>
      <p class="text-ink-400 text-sm mt-1">输入你的小说创意与文风设定</p>
    </div>

    <form @submit.prevent="submit" class="card p-6 md:p-8 space-y-6">
      <div class="space-y-1.5">
        <label class="block text-sm font-medium text-ink-600">小说标题</label>
        <input
          v-model="form.title"
          class="input"
          placeholder="给你的小说起个名字（可选）"
          maxlength="200"
        />
      </div>

      <div class="space-y-1.5">
        <label class="block text-sm font-medium text-ink-600">小说核心创意</label>
        <textarea
          v-model="form.idea"
          class="input min-h-[120px] resize-y text-sm leading-relaxed"
          placeholder="描述你的核心梗或小说创意..."
          maxlength="1000"
        ></textarea>
        <div class="flex justify-between items-center text-xs text-ink-300">
          <span>最少 10 个字</span>
          <span>{{ form.idea.length }} / 1000</span>
        </div>
      </div>

      <div class="space-y-2">
        <label class="block text-sm font-medium text-ink-600">小说类型</label>
        <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
          <button
            v-for="(t, idx) in novelTypes"
            :key="t"
            type="button"
            :class="[
              'px-3 py-2 rounded-lg text-xs font-medium border transition-colors duration-150 animate-fade-up-stagger',
              form.novel_type === t
                ? 'border-vermilion-500 bg-vermilion-50 text-vermilion-600'
                : 'border-ink-200 bg-paper-50 text-ink-600 hover:border-ink-300'
            ]"
            :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }"
            @click="form.novel_type = t"
          >{{ t }}</button>
        </div>
      </div>

      <div class="space-y-2">
        <label class="block text-sm font-medium text-ink-600">文风与风格</label>
        <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
          <button
            v-for="(s, idx) in writingStyles"
            :key="s"
            type="button"
            :class="[
              'px-3 py-2 rounded-lg text-xs font-medium border transition-colors duration-150 animate-fade-up-stagger',
              form.writing_style === s
                ? 'border-vermilion-500 bg-vermilion-50 text-vermilion-600'
                : 'border-ink-200 bg-paper-50 text-ink-600 hover:border-ink-300'
            ]"
            :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }"
            @click="form.writing_style = s"
          >{{ s }}</button>
        </div>

        <div v-if="form.writing_style === '自定义'" class="mt-3 space-y-3 p-4 bg-paper-50 rounded-lg border border-ink-200">
          <textarea
            v-model="form.custom_style_description"
            class="input min-h-[60px] resize-y text-xs"
            placeholder="描述您追求的文体风格..."
          ></textarea>
          <button
            type="button"
            @click="generateStyle"
            class="btn-secondary text-xs"
            :disabled="generatingStyle || !form.custom_style_description"
          >
            {{ generatingStyle ? '生成中...' : 'AI 提炼风格指令' }}
          </button>
          <div v-if="form.writing_style_prompt" class="p-3 bg-paper-50 rounded-lg border border-ink-200">
            <p class="text-[10px] text-ink-300 font-medium uppercase tracking-wider mb-1.5">生成的风格指令：</p>
            <textarea
              v-model="form.writing_style_prompt"
              class="w-full bg-transparent border-0 text-xs resize-y min-h-[60px] focus:outline-none text-ink-600 leading-relaxed"
            ></textarea>
          </div>
        </div>
      </div>

      <div class="space-y-2">
        <div class="flex justify-between text-sm font-medium text-ink-600">
          <span>字数目标</span>
          <span class="text-vermilion-500 font-mono text-xs">{{ (form.target_words / 10000).toFixed(0) }} 万字</span>
        </div>
        <input
          type="range"
          v-model.number="form.target_words"
          min="10000"
          max="5000000"
          :step="form.target_words >= 500000 ? 100000 : 10000"
          class="w-full h-1.5 bg-ink-200 rounded-lg appearance-none cursor-pointer accent-vermilion-500"
        />
        <div class="flex justify-between text-[10px] text-ink-300">
          <span>1 万字</span>
          <span>500 万字</span>
        </div>
        <div v-if="isLongForm" class="mt-1 px-3 py-1.5 bg-vermilion-50 border border-vermilion-200 rounded-lg">
          <span class="text-[11px] text-vermilion-600 font-medium">长篇模式（>20万字自动启用卷章结构）</span>
        </div>
      </div>

      <div v-if="isLongForm" class="space-y-4 p-5 bg-paper-50 rounded-lg border border-ink-200">
        <h3 class="text-sm font-medium text-ink-600">长篇结构设定</h3>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div class="space-y-1">
            <label class="block text-xs text-ink-400">卷数</label>
            <input type="number" v-model.number="form.volumes" min="3" max="20" class="input text-sm text-center" />
            <span class="text-[10px] text-ink-300">3 ~ 20 卷</span>
          </div>
          <div class="space-y-1">
            <label class="flex items-center gap-2 cursor-pointer mb-1">
              <input type="checkbox" v-model="form.auto_calc_chapters" class="accent-vermilion-500 w-3.5 h-3.5 rounded" />
              <span class="text-xs text-ink-600">自动计算章节数（根据目标字数÷每章字数）</span>
            </label>
            <div v-if="form.auto_calc_chapters" class="text-xs text-vermilion-600 bg-vermilion-50 px-3 py-2 rounded">
              预计约 {{ autoCalcTotalChapters }} 章，每卷约 {{ autoCalcChaptersPerVolume }} 章
            </div>
            <template v-else>
              <label class="block text-xs text-ink-400">每卷章数</label>
              <input type="number" v-model.number="form.chapters_per_volume" min="20" max="60" class="input text-sm text-center" />
              <span class="text-[10px] text-ink-300">20 ~ 60 章</span>
            </template>
          </div>
          <div class="space-y-1">
            <label class="block text-xs text-ink-400">每章字数</label>
            <input type="number" v-model.number="form.words_per_chapter" min="2000" max="8000" step="100" class="input text-sm text-center" />
            <span class="text-[10px] text-ink-300">2000 ~ 8000 字</span>
          </div>
        </div>
        <div class="flex flex-wrap gap-4 pt-1">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="form.auto_quality_check" class="accent-vermilion-500 w-3.5 h-3.5 rounded" />
            <span class="text-xs text-ink-600">自动质量检查</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="form.auto_filler_detection" class="accent-vermilion-500 w-3.5 h-3.5 rounded" />
            <span class="text-xs text-ink-600">自动注水检测</span>
          </label>
        </div>
      </div>

      <div class="pt-4 flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          class="btn-secondary sm:flex-1 py-2.5"
          :disabled="!canSubmit || submitting || fullGenerating"
          @click="submit"
        >
          {{ submitting ? '创建中...' : '生成小说设定' }}
        </button>
        <button
          type="button"
          class="btn-primary sm:flex-1 py-2.5 flex items-center justify-center gap-1.5"
          :disabled="!canSubmit || submitting || fullGenerating"
          @click="fullGenerate"
        >
          <span>{{ fullGenerating ? '启动中...' : '一键全自动生成' }}</span>
        </button>
        <router-link to="/" class="btn-secondary text-center py-2.5">取消</router-link>
      </div>

      <div v-if="error" class="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
        {{ error }}
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const novelTypes = ['玄幻', '仙侠', '都市', '科幻', '历史', '武侠', '言情', '悬疑', '军事', '游戏', '竞技', '灵异', '同人']
const writingStyles = ['轻松幽默', '热血燃向', '细腻文艺', '史诗厚重', '悬疑紧张', '古风典雅', '现代白话', '暗黑压抑', '自定义']

const form = ref({
  title: '',
  idea: '',
  novel_type: '玄幻',
  target_words: 100000,
  writing_style: '现代白话',
  custom_style_description: '',
  writing_style_prompt: '',
  volumes: 10,
  chapters_per_volume: 40,
  words_per_chapter: 3000,
  auto_quality_check: true,
  auto_filler_detection: true,
  auto_calc_chapters: false,
})

const submitting = ref(false)
const fullGenerating = ref(false)
const error = ref('')
const generatingStyle = ref(false)

const canSubmit = computed(() => form.value.idea.length >= 10 && form.value.novel_type)
const isLongForm = computed(() => form.value.target_words > 200000)

const autoCalcTotalChapters = computed(() =>
  Math.ceil(form.value.target_words / form.value.words_per_chapter)
)
const autoCalcChaptersPerVolume = computed(() => {
  const raw = Math.ceil(autoCalcTotalChapters.value / form.value.volumes)
  return Math.max(20, Math.min(60, raw))
})

async function generateStyle() {
  if (!form.value.custom_style_description) return
  generatingStyle.value = true
  try {
    const res = await fetch('/api/v1/style/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: form.value.custom_style_description }),
    })
    if (res.ok) {
      const data = await res.json()
      form.value.writing_style_prompt = data.style_prompt
    }
  } finally {
    generatingStyle.value = false
  }
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  error.value = ''
  try {
    const endpoint = isLongForm.value ? '/api/v1/novels/long-form' : '/api/v1/projects'
    const payload = isLongForm.value
      ? {
          idea: form.value.idea,
          novel_type: form.value.novel_type,
          target_words: form.value.target_words,
          volumes: form.value.volumes,
          chapters_per_volume: form.value.chapters_per_volume,
          words_per_chapter: form.value.words_per_chapter,
          writing_style: form.value.writing_style,
          writing_style_prompt: form.value.writing_style_prompt,
          auto_quality_check: form.value.auto_quality_check,
          auto_filler_detection: form.value.auto_filler_detection,
          auto_calc_chapters: form.value.auto_calc_chapters,
        }
      : form.value
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || `请求失败 (${res.status})`)
    }
    const data = await res.json()
    router.push(`/novels/${data.novel_id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}

async function fullGenerate() {
  if (!canSubmit.value) return
  fullGenerating.value = true
  error.value = ''
  try {
    const endpoint = isLongForm.value ? '/api/v1/novels/long-form' : '/api/v1/projects/full-generate'
    const payload = isLongForm.value
      ? {
          idea: form.value.idea,
          novel_type: form.value.novel_type,
          target_words: form.value.target_words,
          volumes: form.value.volumes,
          chapters_per_volume: form.value.chapters_per_volume,
          words_per_chapter: form.value.words_per_chapter,
          writing_style: form.value.writing_style,
          writing_style_prompt: form.value.writing_style_prompt,
          auto_quality_check: form.value.auto_quality_check,
          auto_filler_detection: form.value.auto_filler_detection,
          auto_calc_chapters: form.value.auto_calc_chapters,
        }
      : form.value
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || `请求失败 (${res.status})`)
    }
    const data = await res.json()
    router.push(isLongForm.value ? `/novels/${data.novel_id}` : `/task/${data.task_id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    fullGenerating.value = false
  }
}
</script>
