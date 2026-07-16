<template>
  <div class="fixed bottom-0 left-0 right-0 z-50 bg-paper-50/80 backdrop-blur-lg border-t border-ink-200 shadow-[0_-2px_16px_rgba(0,0,0,0.06)] animate-fade-up">
    <div class="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between gap-4 flex-wrap">
      <!-- Progress info -->
      <div class="flex items-center gap-3 text-sm text-ink-700 dark:text-gray-100">
        <span class="font-semibold">
          第{{ currentChapter }}章 / {{ totalChapters }}章
        </span>
        <span class="text-ink-400 dark:text-neutral-500">|</span>
        <span class="font-mono text-xs text-ink-500 dark:text-neutral-400">{{ wordCount.toLocaleString() }} 字</span>
      </div>

      <!-- Action buttons -->
      <div class="flex items-center gap-2">
        <button
          v-if="!isPaused"
          :disabled="!isStreaming"
          class="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed"
          @click="$emit('pause')"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
          </svg>
          <span>暂停</span>
        </button>

        <button
          v-else
          class="btn-primary"
          @click="$emit('resume')"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
          <span>继续</span>
        </button>

        <button
          :disabled="!isStreaming && !isPaused"
          title="Esc"
          class="btn-danger disabled:opacity-40 disabled:cursor-not-allowed"
          @click="requestStop"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
          <span>停止</span>
        </button>

        <button
          :disabled="!isPaused"
          class="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed"
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

  <Teleport to="body">
    <div
      v-if="showStopConfirm"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/35 backdrop-blur-sm px-4"
      @click.self="cancelStop"
    >
      <div class="card w-full max-w-sm animate-fade-up">
        <div class="px-6 py-5 space-y-4">
          <div class="space-y-2">
            <h3 class="text-base font-semibold text-ink-700 dark:text-gray-100">确定停止生成？</h3>
            <p class="text-sm leading-6 text-ink-500 dark:text-gray-300">未保存进度将丢失</p>
          </div>
          <div class="flex justify-end gap-3">
            <button
              class="btn-secondary"
              @click="cancelStop"
            >
              继续生成
            </button>
            <button
              class="btn-danger"
              @click="confirmStop"
            >
              确认停止
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'

defineProps({
  taskId: { type: String, default: '' },
  isPaused: { type: Boolean, default: false },
  isStreaming: { type: Boolean, default: false },
  currentChapter: { type: Number, default: 0 },
  totalChapters: { type: Number, default: 0 },
  wordCount: { type: Number, default: 0 },
})

const emit = defineEmits(['pause', 'resume', 'stop', 'edit'])

const showStopConfirm = ref(false)
let stopConfirmTimer = null

function clearStopTimer() {
  if (stopConfirmTimer) {
    clearTimeout(stopConfirmTimer)
    stopConfirmTimer = null
  }
}

function closeStopConfirm() {
  showStopConfirm.value = false
  clearStopTimer()
}

function requestStop() {
  if (showStopConfirm.value) {
    confirmStop()
    return
  }

  showStopConfirm.value = true
  clearStopTimer()
  stopConfirmTimer = setTimeout(() => {
    showStopConfirm.value = false
    stopConfirmTimer = null
  }, 2000)
}

function confirmStop() {
  closeStopConfirm()
  emit('stop')
}

function cancelStop() {
  closeStopConfirm()
}

function handleKeydown(event) {
  if (event.key === 'Escape' && showStopConfirm.value) {
    cancelStop()
  }
}

window.addEventListener('keydown', handleKeydown)

onBeforeUnmount(() => {
  clearStopTimer()
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.btn-secondary {
  @apply flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all duration-200 shadow-sm;
}
</style>
