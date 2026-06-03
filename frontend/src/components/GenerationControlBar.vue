<template>
  <div class="fixed bottom-0 left-0 right-0 z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-lg border-t border-[#e5e5ea] dark:border-gray-700 shadow-[0_-2px_16px_rgba(0,0,0,0.06)]">
    <div class="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between gap-4 flex-wrap">
      <!-- Progress info -->
      <div class="flex items-center gap-3 text-sm text-[#1d1d1f] dark:text-gray-100">
        <span class="font-semibold">
          第{{ currentChapter }}章 / {{ totalChapters }}章
        </span>
        <span class="text-gray-400 dark:text-gray-500">|</span>
        <span class="font-mono text-xs text-gray-500 dark:text-gray-400">{{ wordCount.toLocaleString() }} 字</span>
      </div>

      <!-- Action buttons -->
      <div class="flex items-center gap-2">
        <button
          v-if="!isPaused"
          :disabled="!isStreaming"
          class="btn-control bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
          @click="$emit('pause')"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
          </svg>
          <span>暂停</span>
        </button>

        <button
          v-else
          class="btn-control bg-emerald-500 hover:bg-emerald-600 text-white"
          @click="$emit('resume')"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
          <span>继续</span>
        </button>

        <button
          :disabled="!isStreaming && !isPaused"
          class="btn-control bg-rose-500 hover:bg-rose-600 text-white disabled:opacity-40 disabled:cursor-not-allowed"
          @click="$emit('stop')"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
          <span>停止</span>
        </button>

        <button
          :disabled="!isPaused"
          class="btn-control bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-[#1d1d1f] dark:text-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
          @click="$emit('edit')"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
          </svg>
          <span>编辑当前章</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  taskId: { type: String, default: '' },
  isPaused: { type: Boolean, default: false },
  isStreaming: { type: Boolean, default: false },
  currentChapter: { type: Number, default: 0 },
  totalChapters: { type: Number, default: 0 },
  wordCount: { type: Number, default: 0 },
})

defineEmits(['pause', 'resume', 'stop', 'edit'])
</script>

<style scoped>
.btn-control {
  @apply flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all duration-200 shadow-sm;
}
</style>
