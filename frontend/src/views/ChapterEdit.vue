<template>
  <div class="max-w-4xl mx-auto px-6 py-10">
    <div v-if="!chapter" class="text-center py-20 text-ink-400">章节不存在</div>

    <template v-else>
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-xl font-bold text-ink-900">第{{ chapter.chapter_number }}章：{{ chapter.title }}</h1>
          <p class="text-xs text-ink-400 mt-1">{{ contentLength }} 字</p>
        </div>
        <div class="flex gap-2">
          <button @click="regenerate" class="btn-secondary text-sm" :disabled="regenerating">
            {{ regenerating ? '生成中...' : '重新生成' }}
          </button>
          <button @click="deleteChapter" class="text-red-500 hover:text-red-700 text-sm px-3 py-2">删除</button>
          <button @click="save" class="btn-primary text-sm" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
          <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
        </div>
      </div>

      <div class="card p-1">
        <textarea
          v-model="content"
          class="w-full min-h-[500px] p-5 text-sm leading-relaxed font-serif resize-y border-0 focus:outline-none"
          placeholder="章节内容..."
        ></textarea>
      </div>

      <p v-if="saved" class="text-sm text-emerald-600 mt-3">已保存（{{ contentLength }} 字）</p>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const novelId = route.params.id
const chapterNum = route.params.num

const chapter = ref(null)
const content = ref('')
const saving = ref(false)
const saved = ref(false)
const regenerating = ref(false)

const contentLength = computed(() => content.value.length)

async function load() {
  const res = await fetch(`/api/v1/projects/${novelId}/chapters/${chapterNum}`)
  if (res.ok) {
    chapter.value = await res.json()
    content.value = chapter.value.content || ''
  }
}

async function save() {
  saving.value = true
  saved.value = false
  await fetch(`/api/v1/projects/${novelId}/chapters/${chapterNum}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: content.value, title: chapter.value.title }),
  })
  saving.value = false
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}

async function regenerate() {
  if (!confirm('重新生成将覆盖当前内容，确定吗？')) return
  regenerating.value = true
  const res = await fetch(`/api/v1/projects/${novelId}/generate-chapters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chapter_start: parseInt(chapterNum), chapter_end: parseInt(chapterNum) }),
  })
  if (res.ok) {
    const data = await res.json()
    router.push(`/task/${data.task_id}`)
  }
  regenerating.value = false
}

async function deleteChapter() {
  if (!confirm('确定删除本章？此操作不可恢复。')) return
  await fetch(`/api/v1/projects/${novelId}/chapters/${chapterNum}`, { method: 'DELETE' })
  router.push(`/novels/${novelId}`)
}

onMounted(load)
</script>
