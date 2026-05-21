<template>
  <div class="space-y-6">
    <div v-for="vol in volumes" :key="vol.id" class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <!-- Volume Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-50">
        <div class="flex items-center gap-3">
          <span class="text-xs font-medium px-2.5 py-1 bg-indigo-50 text-indigo-600 rounded-lg">
            卷 {{ vol.volume_number }}
          </span>
          <h3 class="font-semibold text-gray-900 text-[15px]">{{ vol.title || '未命名分卷' }}</h3>
          <span :class="statusClasses(vol.status)" class="text-[11px] font-medium px-2 py-0.5 rounded-full">
            {{ statusLabel(vol.status) }}
          </span>
        </div>
        <button
          v-if="vol.status !== 'generating'"
          @click="$emit('generate-volume', vol.volume_number)"
          class="text-xs font-medium px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          {{ vol.status === 'completed' ? '重新生成' : '生成本卷' }}
        </button>
      </div>

      <!-- Volume Summary -->
      <p v-if="vol.summary" class="px-6 py-3 text-sm text-gray-500 leading-relaxed border-b border-gray-50">{{ vol.summary }}</p>

      <!-- Chapter List -->
      <div v-if="volumeChapters(vol)" class="divide-y divide-gray-50">
        <div
          v-for="ch in volumeChapters(vol)"
          :key="ch.id"
          class="flex items-center justify-between px-6 py-3.5 hover:bg-gray-50/50 transition-colors group"
        >
          <router-link
            :to="`/novels/${novelId}/chapters/${ch.chapter_number}`"
            class="flex-1 flex items-center gap-3 min-w-0"
          >
            <span class="text-sm text-gray-400 font-mono w-6 shrink-0">{{ chapterIndexInVolume(vol, ch) }}</span>
            <span class="text-sm font-medium text-gray-800 truncate">{{ ch.title }}</span>
          </router-link>
          <div class="flex items-center gap-3 shrink-0">
            <span class="text-xs text-gray-400 font-mono">{{ ch.word_count || 0 }} 字</span>
            <button
              @click.prevent="confirmDelete(ch)"
              class="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition-all p-1 rounded"
              title="删除章节"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                <path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
              </svg>
            </button>
          </div>
        </div>
      </div>
      <p v-else class="px-6 py-6 text-sm text-gray-400 text-center">暂无章节</p>
    </div>

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <div v-if="deleteTarget" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/20 backdrop-blur-sm" @click="deleteTarget = null"></div>
        <div class="relative bg-white rounded-2xl shadow-xl p-6 w-80 mx-4">
          <h3 class="text-base font-semibold text-gray-900 mb-2">确认删除</h3>
          <p class="text-sm text-gray-500 mb-5">
            确定要删除「第{{ deleteTarget.chapter_number }}章：{{ deleteTarget.title }}」吗？此操作不可撤销。
          </p>
          <div class="flex gap-3 justify-end">
            <button @click="deleteTarget = null" class="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 rounded-lg hover:bg-gray-100 transition-colors">
              取消
            </button>
            <button @click="doDelete" class="px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors">
              删除
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  volumes: { type: Array, default: () => [] },
  chapters: { type: Array, default: () => [] },
  novelId: { type: String, required: true },
})

const emit = defineEmits(['generate-volume', 'delete-chapter'])

const deleteTarget = ref(null)

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

function statusClasses(s) {
  const map = {
    draft: 'bg-gray-100 text-gray-500',
    generating: 'bg-amber-50 text-amber-600',
    completed: 'bg-emerald-50 text-emerald-600',
    failed: 'bg-red-50 text-red-500',
  }
  return map[s] || 'bg-gray-100 text-gray-500'
}

function statusLabel(s) {
  return { draft: '待生成', generating: '生成中', completed: '已完成', failed: '失败' }[s] || s
}

function confirmDelete(ch) {
  deleteTarget.value = ch
}

async function doDelete() {
  const ch = deleteTarget.value
  if (!ch) return
  try {
    const res = await fetch(`/api/v1/projects/${props.novelId}/chapters/${ch.chapter_number}`, { method: 'DELETE' })
    if (res.ok) {
      emit('delete-chapter', ch.chapter_number)
    }
  } finally {
    deleteTarget.value = null
  }
}
</script>
