<template>
  <div class="space-y-4">
    <div v-for="vol in volumes" :key="vol.id" class="card p-5 bg-slate-900/30 border-slate-800/80 hover:border-slate-800/50 transition-all duration-300">
      <div class="flex items-center justify-between pb-3 border-b border-slate-800/40 mb-3">
        <div class="flex items-center gap-3">
          <span class="text-xs font-bold px-2.5 py-1 bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded-lg shrink-0">
            卷 {{ vol.volume_number }}
          </span>
          <h3 class="font-extrabold text-slate-100 text-sm sm:text-base truncate">{{ vol.title || '未命名分卷' }}</h3>
          <span :class="'badge-' + statusClass(vol.status)">{{ statusLabel(vol.status) }}</span>
        </div>
        <button
          v-if="vol.status !== 'generating'"
          @click="$emit('generate-volume', vol.volume_number)"
          class="btn-primary text-xs py-1.5 px-4"
        >
          {{ vol.status === 'completed' ? '重新生成' : '生成本卷' }}
        </button>
      </div>
      
      <p v-if="vol.summary" class="text-xs sm:text-sm text-slate-400 leading-relaxed mb-4 pl-1 font-medium">{{ vol.summary }}</p>
      
      <div v-if="volumeChapters(vol)" class="grid grid-cols-1 md:grid-cols-2 gap-3 pl-1">
        <router-link
          v-for="ch in volumeChapters(vol)"
          :key="ch.id"
          :to="`/novels/${novelId}/chapters/${ch.chapter_number}`"
          class="px-4 py-3 bg-slate-950/40 hover:bg-slate-900/60 border border-slate-900 hover:border-purple-500/20 rounded-xl hover:shadow-md transition-all duration-300 flex justify-between items-center group"
        >
          <span class="text-xs sm:text-sm font-semibold text-slate-300 group-hover:text-purple-300 transition-colors truncate pr-2">
            第{{ chapterIndexInVolume(vol, ch) }}章：{{ ch.title }}
          </span>
          <span class="text-[10px] text-slate-500 font-mono bg-slate-900/60 px-2 py-0.5 rounded border border-slate-800/80 group-hover:border-purple-500/20 group-hover:text-purple-400 transition-all shrink-0">
            {{ ch.word_count || 0 }} 字
          </span>
        </router-link>
      </div>
      <p v-else class="text-xs text-slate-500 font-semibold italic pl-1">暂无章节</p>
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
  return chs.length ? chs.sort((a, b) => a.chapter_number - b.chapter_number) : null
}

function chapterIndexInVolume(vol, ch) {
  if (vol.chapter_start != null) {
    return ch.chapter_number - vol.chapter_start + 1
  }
  const chs = props.chapters
    .filter(c => c.volume_number === vol.volume_number)
    .sort((a, b) => a.chapter_number - b.chapter_number)
  const idx = chs.findIndex(c => c.id === ch.id)
  return idx >= 0 ? idx + 1 : ch.chapter_number
}

function statusClass(s) {
  return { draft: 'pending', generating: 'running', completed: 'completed', failed: 'failed' }[s] || 'pending'
}

function statusLabel(s) {
  return { draft: '待生成', generating: '生成中', completed: '已完成', failed: '失败' }[s] || s
}
</script>
