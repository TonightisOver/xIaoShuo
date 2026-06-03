<template>
  <div>
    <transition name="toc-fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-30 bg-black/20 backdrop-blur-sm"
        @click="emit('close')"
      ></div>
    </transition>

    <transition name="toc-slide">
      <aside
        v-if="visible"
        class="fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r border-white/20 bg-white/85 shadow-2xl backdrop-blur-xl dark:border-neutral-800/70 dark:bg-neutral-950/85"
      >
        <header class="border-b border-neutral-200/70 px-4 py-4 dark:border-neutral-800/70">
          <div class="mb-3 flex items-center justify-between gap-3">
            <h2 class="text-sm font-bold text-neutral-900 dark:text-neutral-100">目录</h2>
            <button
              type="button"
              class="flex h-8 w-8 items-center justify-center rounded-full text-lg leading-none text-neutral-500 transition hover:bg-neutral-900/5 hover:text-neutral-900 active:scale-95 dark:text-neutral-400 dark:hover:bg-white/10 dark:hover:text-neutral-100"
              aria-label="关闭目录"
              @click="emit('close')"
            >
              x
            </button>
          </div>

          <div class="space-y-2">
            <div class="flex items-center justify-between text-xs font-medium text-neutral-500 dark:text-neutral-400">
              <span>阅读进度</span>
              <span class="font-mono font-bold text-accent-600 dark:text-accent-400">{{ progressPercent }}%</span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-neutral-200/80 dark:bg-neutral-800">
              <div
                class="h-full rounded-full bg-accent-600 transition-all duration-300 dark:bg-accent-500"
                :style="{ width: `${progressPercent}%` }"
              ></div>
            </div>
          </div>
        </header>

        <nav class="custom-scrollbar flex-1 overflow-y-auto px-2 py-3">
          <div
            v-for="group in groupedChapters"
            :key="group.volumeNumber"
            class="mb-4 last:mb-0"
          >
            <div class="px-2 pb-1 text-[11px] font-bold uppercase tracking-wide text-neutral-400 dark:text-neutral-500">
              {{ group.label }}
            </div>

            <button
              v-for="chapter in group.chapters"
              :key="chapter.chapter_number"
              type="button"
              class="mb-0.5 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs transition"
              :class="chapterClass(chapter)"
              @click="emit('go-to-chapter', chapter.chapter_number)"
            >
              <span class="shrink-0 font-mono text-[11px] opacity-60">{{ chapter.chapter_number }}</span>
              <span class="min-w-0 flex-1 truncate">{{ chapter.title || `第 ${chapter.chapter_number} 章` }}</span>
              <span
                v-if="isCurrentChapter(chapter)"
                class="shrink-0 rounded bg-accent-100 px-1.5 py-0.5 text-[10px] font-bold text-accent-700 dark:bg-accent-950 dark:text-accent-300"
              >
                当前
              </span>
            </button>
          </div>
        </nav>
      </aside>
    </transition>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  chapters: {
    type: Array,
    default: () => [],
  },
  currentChapter: {
    type: Number,
    default: null,
  },
  visible: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['go-to-chapter', 'close'])

const sortedChapters = computed(() =>
  [...props.chapters].sort((a, b) => Number(a.chapter_number) - Number(b.chapter_number))
)

const groupedChapters = computed(() => {
  const groups = new Map()

  for (const chapter of sortedChapters.value) {
    const volumeNumber = chapter.volume_number == null ? 0 : Number(chapter.volume_number)
    if (!groups.has(volumeNumber)) {
      groups.set(volumeNumber, {
        volumeNumber,
        label: volumeNumber > 0 ? `第 ${volumeNumber} 卷` : '正文',
        chapters: [],
      })
    }
    groups.get(volumeNumber).chapters.push(chapter)
  }

  return [...groups.values()].sort((a, b) => a.volumeNumber - b.volumeNumber)
})

const progressPercent = computed(() => {
  const total = sortedChapters.value.length
  if (!total) return 0

  const currentIndex = sortedChapters.value.findIndex(isCurrentChapter)
  const currentPosition = currentIndex >= 0 ? currentIndex + 1 : Number(props.currentChapter)

  return Math.min(100, Math.max(0, Math.round((currentPosition / total) * 100)))
})

function isCurrentChapter(chapter) {
  return Number(chapter.chapter_number) === Number(props.currentChapter)
}

function chapterClass(chapter) {
  if (isCurrentChapter(chapter)) {
    return 'bg-accent-50 text-accent-700 font-semibold shadow-sm dark:bg-accent-950/50 dark:text-accent-300'
  }

  return 'text-neutral-700 hover:bg-neutral-900/5 hover:text-neutral-950 dark:text-neutral-300 dark:hover:bg-white/10 dark:hover:text-white'
}
</script>

<style scoped>
.toc-slide-enter-from,
.toc-slide-leave-to {
  transform: translateX(-100%);
}

.toc-slide-enter-active,
.toc-slide-leave-active {
  transition: transform 0.25s ease;
}

.toc-fade-enter-from,
.toc-fade-leave-to {
  opacity: 0;
}

.toc-fade-enter-active,
.toc-fade-leave-active {
  transition: opacity 0.2s ease;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(115, 115, 115, 0.24);
  border-radius: 9999px;
}
</style>
