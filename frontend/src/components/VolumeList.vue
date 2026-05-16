<template>
  <div class="space-y-4">
    <div v-for="vol in volumes" :key="vol.id" class="card p-4">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <h3 class="font-medium text-ink-800">卷{{ vol.volume_number }}：{{ vol.title || '未命名' }}</h3>
          <span :class="'badge-' + statusClass(vol.status)">{{ statusLabel(vol.status) }}</span>
        </div>
        <button
          v-if="vol.status !== 'generating'"
          @click="$emit('generate-volume', vol.volume_number)"
          class="btn-primary text-xs"
        >
          {{ vol.status === 'completed' ? '重新生成' : '生成本卷' }}
        </button>
      </div>
      <p v-if="vol.summary" class="text-sm text-ink-600 mb-2">{{ vol.summary }}</p>
      <div v-if="volumeChapters(vol)" class="space-y-1 ml-4">
        <router-link
          v-for="ch in volumeChapters(vol)"
          :key="ch.id"
          :to="`/novels/${novelId}/chapters/${ch.chapter_number}`"
          class="block text-sm text-ink-600 hover:text-primary-600 transition-colors py-0.5"
        >
          第{{ ch.chapter_number }}章：{{ ch.title }}
          <span class="text-ink-400 text-xs ml-1">{{ ch.word_count }}字</span>
        </router-link>
      </div>
      <p v-else class="text-xs text-ink-400 ml-4">暂无章节</p>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  volumes: { type: Array, default: () => [] },
  chapters: { type: Array, default: () => [] },
  novelId: { type: String, required: true },
})

defineEmits(['generate-volume'])

function volumeChapters(vol) {
  const chs = props.chapters.filter(c => c.volume_number === vol.volume_number)
  return chs.length ? chs : null
}

function statusClass(s) {
  return { draft: 'pending', generating: 'running', completed: 'completed', failed: 'failed' }[s] || 'pending'
}

function statusLabel(s) {
  return { draft: '待生成', generating: '生成中', completed: '已完成', failed: '失败' }[s] || s
}
</script>
