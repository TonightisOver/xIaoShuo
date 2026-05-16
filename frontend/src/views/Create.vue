<template>
  <div class="max-w-2xl mx-auto px-6 py-10">
    <h1 class="text-2xl font-bold text-ink-900 mb-2">开始创作</h1>
    <p class="text-ink-500 mb-8">输入你的小说创意，AI 将为你生成完整的中文小说</p>

    <form @submit.prevent="submit" class="space-y-6">
      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">小说标题</label>
        <input
          v-model="form.title"
          class="input"
          placeholder="给你的小说起个名字（可选，默认从创意生成）"
          maxlength="200"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">小说创意</label>
        <textarea
          v-model="form.idea"
          class="input min-h-[120px] resize-y"
          placeholder="描述你的小说创意，例如：一个现代程序员穿越到修仙世界，用编程思维修炼..."
          maxlength="1000"
        ></textarea>
        <p class="text-xs text-ink-400 mt-1">{{ form.idea.length }} / 1000 字符（最少 10 字）</p>
      </div>

      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">小说类型</label>
        <div class="grid grid-cols-4 gap-2">
          <button
            v-for="t in novelTypes"
            :key="t"
            type="button"
            :class="[
              'px-4 py-2 rounded-lg text-sm font-medium border transition-all',
              form.novel_type === t
                ? 'border-primary-500 bg-primary-50 text-primary-700'
                : 'border-ink-200 text-ink-600 hover:border-ink-400'
            ]"
            @click="form.novel_type = t"
          >{{ t }}</button>
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">文风风格</label>
        <div class="grid grid-cols-4 gap-2">
          <button
            v-for="s in writingStyles"
            :key="s"
            type="button"
            :class="[
              'px-4 py-2 rounded-lg text-sm font-medium border transition-all',
              form.writing_style === s
                ? 'border-primary-500 bg-primary-50 text-primary-700'
                : 'border-ink-200 text-ink-600 hover:border-ink-400'
            ]"
            @click="form.writing_style = s"
          >{{ s }}</button>
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-ink-700 mb-2">
          目标字数：<span class="text-primary-600">{{ (form.target_words / 10000).toFixed(0) }} 万字</span>
        </label>
        <input
          type="range"
          v-model.number="form.target_words"
          min="10000"
          max="500000"
          step="10000"
          class="w-full accent-primary-600"
        />
        <div class="flex justify-between text-xs text-ink-400 mt-1">
          <span>1 万</span>
          <span>50 万</span>
        </div>
      </div>

      <div class="pt-4 flex gap-3">
        <button type="submit" class="btn-primary flex-1" :disabled="!canSubmit || submitting">
          {{ submitting ? '提交中...' : '开始生成' }}
        </button>
        <router-link to="/" class="btn-secondary">取消</router-link>
      </div>

      <div v-if="error" class="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
        {{ error }}
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const novelTypes = ['玄幻', '仙侠', '都市', '科幻', '历史', '武侠', '言情', '悬疑']
const writingStyles = ['轻松幽默', '热血燃向', '细腻文艺', '史诗厚重', '悬疑紧张', '古风典雅', '现代白话', '暗黑压抑']

const form = ref({
  title: '',
  idea: '',
  novel_type: '玄幻',
  target_words: 100000,
  writing_style: '现代白话',
})

const submitting = ref(false)
const error = ref('')

const canSubmit = computed(() => form.value.idea.length >= 10 && form.value.novel_type)

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  error.value = ''

  try {
    const res = await fetch('/api/v1/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
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
</script>
