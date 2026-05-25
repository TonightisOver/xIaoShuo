<template>
  <div class="max-w-3xl mx-auto px-6 py-10">
    <div class="mb-10 text-center">
      <h1 class="text-3xl font-extrabold tracking-tight text-slate-100 flex items-center justify-center gap-2 mb-2.5">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-8 h-8 text-purple-400">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
        </svg>
        <span class="bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-indigo-400">开启新篇章</span>
      </h1>
      <p class="text-slate-400 text-sm font-medium">输入你的小说创意与文风设定，让 AI 为你雕琢专属大作</p>
    </div>

    <form @submit.prevent="submit" class="space-y-8 glass-panel rounded-3xl p-6 md:p-8 border border-slate-900 shadow-2xl relative overflow-hidden">
      <!-- Background Ambient Glow -->
      <div class="absolute -top-24 -left-24 w-48 h-48 rounded-full bg-purple-500/5 blur-3xl"></div>
      <div class="absolute -bottom-24 -right-24 w-48 h-48 rounded-full bg-indigo-500/5 blur-3xl"></div>

      <div class="space-y-2 relative z-10">
        <label class="block text-sm font-bold text-slate-300">小说标题</label>
        <input
          v-model="form.title"
          class="input bg-slate-950/40 border-slate-800"
          placeholder="给你的小说起个震撼的名字（可选，默认从创意生成）"
          maxlength="200"
        />
      </div>

      <div class="space-y-2 relative z-10">
        <label class="block text-sm font-bold text-slate-300">小说核心创意</label>
        <textarea
          v-model="form.idea"
          class="input min-h-[140px] resize-y bg-slate-950/40 border-slate-800 text-sm leading-relaxed"
          placeholder="尽情描述你的核心梗或小说创意。例如：一个现代游戏程序员意外穿越到诸神修仙世界，发现可以通过编写灵力算法和自动化仙法修炼程序来逆天改命..."
          maxlength="1000"
        ></textarea>
        <div class="flex justify-between items-center text-xs text-slate-500 font-medium">
          <span>最少 10 个字</span>
          <span>{{ form.idea.length }} / 1000 字符</span>
        </div>
      </div>

      <div class="space-y-3 relative z-10">
        <label class="block text-sm font-bold text-slate-300">小说类型</label>
        <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
          <button
            v-for="t in novelTypes"
            :key="t"
            type="button"
            :class="[
              'px-3 py-2.5 rounded-xl text-xs font-semibold border transition-all duration-200',
              form.novel_type === t
                ? 'border-purple-500 bg-purple-500/10 text-purple-300 shadow-inner'
                : 'border-slate-800 bg-slate-900/20 text-slate-400 hover:border-slate-700 hover:text-slate-200'
            ]"
            @click="form.novel_type = t"
          >{{ t }}</button>
        </div>
      </div>

      <div class="space-y-3 relative z-10">
        <label class="block text-sm font-bold text-slate-300">文风与风格特征</label>
        <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
          <button
            v-for="s in writingStyles"
            :key="s"
            type="button"
            :class="[
              'px-3 py-2.5 rounded-xl text-xs font-semibold border transition-all duration-200',
              form.writing_style === s
                ? 'border-purple-500 bg-purple-500/10 text-purple-300 shadow-inner'
                : 'border-slate-800 bg-slate-900/20 text-slate-400 hover:border-slate-700 hover:text-slate-200'
            ]"
            @click="form.writing_style = s"
          >{{ s }}</button>
        </div>

        <div v-if="form.writing_style === '自定义'" class="mt-4 space-y-3 p-4 bg-slate-950/30 rounded-2xl border border-slate-900">
          <textarea
            v-model="form.custom_style_description"
            class="input min-h-[70px] resize-y text-xs bg-slate-950/40 border-slate-800"
            placeholder="请细化描述您所追求的文体，例如：类似于猫腻的半文言文风，注重角色对白，偏向灰色幽默与宿命感..."
          ></textarea>
          <div class="flex gap-2">
            <button 
              type="button" 
              @click="generateStyle" 
              class="btn-secondary text-xs px-4 py-2 flex items-center gap-1" 
              :disabled="generatingStyle || !form.custom_style_description"
            >
              <svg v-if="generatingStyle" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3.5 h-3.5 animate-spin">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              <span>{{ generatingStyle ? '生成中...' : 'AI 提炼风格指令' }}</span>
            </button>
          </div>
          <div v-if="form.writing_style_prompt" class="p-4 bg-slate-950/60 rounded-xl border border-slate-800/60 text-xs text-slate-300">
            <p class="text-slate-500 font-bold mb-1.5 text-[10px] tracking-wider uppercase">生成的风格指令（您可以自由编辑微调）：</p>
            <textarea 
              v-model="form.writing_style_prompt" 
              class="w-full bg-transparent border-0 text-xs resize-y min-h-[80px] focus:outline-none focus:ring-0 text-slate-300 leading-relaxed font-mono"
            ></textarea>
          </div>
        </div>
      </div>

      <div class="space-y-3 relative z-10">
        <div class="flex justify-between text-sm font-bold text-slate-300">
          <span>长篇字数目标</span>
          <span class="text-purple-400 font-mono">{{ (form.target_words / 10000).toFixed(0) }} 万字</span>
        </div>
        <input
          type="range"
          v-model.number="form.target_words"
          min="10000"
          max="5000000"
          :step="form.target_words >= 500000 ? 100000 : 10000"
          class="w-full h-2 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-purple-500"
        />
        <div class="flex justify-between text-[10px] text-slate-500 font-bold font-mono">
          <span>1 万字</span>
          <span>500 万字</span>
        </div>
        <div v-if="isLongForm" class="mt-1 px-3 py-1.5 bg-purple-500/10 border border-purple-500/20 rounded-lg">
          <span class="text-[11px] text-purple-300 font-semibold">长篇模式已激活（>20万字自动启用卷章结构）</span>
        </div>
      </div>

      <div v-if="isLongForm" class="space-y-4 relative z-10 p-5 bg-slate-950/30 rounded-2xl border border-purple-500/20">
        <h3 class="text-sm font-bold text-purple-300 flex items-center gap-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
          </svg>
          长篇结构设定
        </h3>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-400">卷数</label>
            <input
              type="number"
              v-model.number="form.volumes"
              min="3"
              max="20"
              class="input text-sm bg-slate-950/40 border-slate-800 text-center"
            />
            <span class="text-[10px] text-slate-500">3 ~ 20 卷</span>
          </div>
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-400">每卷章数</label>
            <input
              type="number"
              v-model.number="form.chapters_per_volume"
              min="20"
              max="60"
              class="input text-sm bg-slate-950/40 border-slate-800 text-center"
            />
            <span class="text-[10px] text-slate-500">20 ~ 60 章</span>
          </div>
          <div class="space-y-1.5">
            <label class="block text-xs font-semibold text-slate-400">每章字数</label>
            <input
              type="number"
              v-model.number="form.words_per_chapter"
              min="2000"
              max="4000"
              step="100"
              class="input text-sm bg-slate-950/40 border-slate-800 text-center"
            />
            <span class="text-[10px] text-slate-500">2000 ~ 4000 字</span>
          </div>
        </div>

        <div class="flex flex-wrap gap-4 pt-2">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="form.auto_quality_check" class="accent-purple-500 w-4 h-4 rounded" />
            <span class="text-xs text-slate-300 font-medium">自动质量检查</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" v-model="form.auto_filler_detection" class="accent-purple-500 w-4 h-4 rounded" />
            <span class="text-xs text-slate-300 font-medium">自动注水检测</span>
          </label>
        </div>
      </div>

      <div class="pt-4 flex flex-col sm:flex-row gap-3 relative z-10">
        <button 
          type="button" 
          class="btn-secondary sm:flex-1 py-3" 
          :disabled="!canSubmit || submitting || fullGenerating" 
          @click="submit"
        >
          {{ submitting ? '创建中...' : '生成小说设定 (分步)' }}
        </button>
        
        <button 
          type="button" 
          class="btn-primary sm:flex-1 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 py-3 shadow-lg shadow-emerald-500/10 flex items-center justify-center gap-1.5" 
          :disabled="!canSubmit || submitting || fullGenerating" 
          @click="fullGenerate"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
          </svg>
          <span>{{ fullGenerating ? '启动流水线...' : '一键全自动生成' }}</span>
        </button>

        <router-link to="/" class="btn-secondary text-center py-3">取消</router-link>
      </div>

      <div v-if="error" class="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-xs text-rose-400 font-medium relative z-10 leading-relaxed">
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
})

const submitting = ref(false)
const fullGenerating = ref(false)
const error = ref('')
const generatingStyle = ref(false)

const canSubmit = computed(() => form.value.idea.length >= 10 && form.value.novel_type)
const isLongForm = computed(() => form.value.target_words > 200000)

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
