<template>
  <div class="space-y-6 animate-fade-up">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <h2 class="text-ink-700 font-semibold text-sm heading-serif">小说正文章节</h2>
      <div class="flex items-center gap-3">
        <button @click="$emit('cleanup')" class="btn-secondary text-xs py-2 px-4 flex items-center gap-1 text-red-500 hover:text-red-600 border-red-200">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
          </svg>
          <span>清理失败章节</span>
        </button>
        <button @click="$emit('open-range-dialog')" class="btn-secondary text-xs py-2 px-4 flex items-center gap-1">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-vermilion-500">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          <span>按范围重新生成章节</span>
        </button>
      </div>
    </div>

    <VolumeList v-if="volumes.length" :volumes="volumes" :chapters="chapters" :novel-id="novelId" @generate-volume="$emit('generate-volume', $event)" @delete-chapter="$emit('delete-chapter', $event)" />

    <div v-if="unassignedChapters.length" class="mt-6">
      <h3 v-if="volumes.length" class="text-sm font-medium text-ink-400 mb-3 pl-1">未分卷章节</h3>
      <div class="card divide-y divide-ink-100 overflow-hidden">
        <div v-for="(ch, idx) in unassignedChapters" :key="ch.id" class="card-hover shine-on-hover animate-fade-up-stagger flex items-center justify-between px-6 py-3.5 hover:bg-paper-50 transition-colors group" :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }">
          <router-link :to="`/novels/${novelId}/chapters/${ch.chapter_number}`" class="flex-1 flex items-center gap-3 min-w-0">
            <span class="text-sm text-ink-400 font-mono w-6 shrink-0">{{ ch.chapter_number }}</span>
            <span class="text-sm font-medium text-ink-600 truncate">{{ ch.title }}</span>
          </router-link>
          <div class="flex items-center gap-3 shrink-0">
            <span class="text-xs text-ink-400 font-mono">{{ ch.word_count || 0 }} 字</span>
            <button @click="$emit('confirm-delete', ch)" class="opacity-0 group-hover:opacity-100 text-ink-300 hover:text-red-500 transition-all p-1 rounded" title="删除章节">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
                <path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!volumes.length && !chapters.length" class="card p-12 text-center text-ink-400">
      尚未开始正文章节的生成。您可以点击右上角"一键全功能生成"或进行分步设定创建。
    </div>

    <ChapterRangeDialog :visible="showRangeDialog" @close="$emit('close-range-dialog')" @generate="$emit('generate-chapters', $event)" />
    <ExportDialog :visible="showExportDialog" :novel-id="novelId" :novel-title="novelTitle" :volumes="volumes" @close="$emit('close-export-dialog')" />

    <Teleport to="body">
      <div v-if="deleteTarget" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/20" @click="$emit('cancel-delete')"></div>
        <div class="relative bg-paper-50 rounded-xl shadow-xl p-6 w-80 mx-4 border border-ink-200 animate-fade-in">
          <h3 class="text-base font-semibold text-ink-700 mb-2">确认删除</h3>
          <p class="text-sm text-ink-500 mb-5">确定要删除「第{{ deleteTarget.chapter_number }}章：{{ deleteTarget.title }}」吗？此操作不可撤销。</p>
          <div class="flex gap-3 justify-end">
            <button @click="$emit('cancel-delete')" class="btn-secondary text-sm font-medium text-ink-600 hover:text-ink-700">取消</button>
            <button @click="$emit('do-delete')" class="btn-danger text-sm font-medium">删除</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import VolumeList from './VolumeList.vue'
import ChapterRangeDialog from './ChapterRangeDialog.vue'
import ExportDialog from './ExportDialog.vue'

defineProps({
  volumes: Array,
  chapters: Array,
  novelId: String,
  novelTitle: String,
  unassignedChapters: Array,
  showRangeDialog: Boolean,
  showExportDialog: Boolean,
  deleteTarget: Object,
})

defineEmits([
  'cleanup', 'open-range-dialog', 'close-range-dialog',
  'generate-volume', 'delete-chapter',
  'confirm-delete', 'cancel-delete', 'do-delete',
  'generate-chapters', 'close-export-dialog',
])
</script>
