<template>
  <div class="card p-5 mb-6">
    <button
      class="w-full flex items-center justify-between text-sm font-bold text-[#1d1d1f] dark:text-gray-100 mb-0 select-none"
      @click="collapsed = !collapsed"
    >
      <span class="flex items-center gap-2">
        <svg class="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
        <span>大纲/情节规划</span>
        <span v-if="isOutlineStreaming" class="inline-block w-2 h-2 rounded-full bg-purple-500 animate-pulse"></span>
      </span>
      <svg
        :class="['w-4 h-4 text-neutral-400 transition-transform duration-200', collapsed ? '' : 'rotate-180']"
        fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
      </svg>
    </button>

    <div v-show="!collapsed" class="mt-4">
      <StreamingText :text="outlineText" :is-streaming="isOutlineStreaming" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import StreamingText from './StreamingText.vue'

defineProps({
  outlineText: { type: String, default: '' },
  isOutlineStreaming: { type: Boolean, default: false },
})

const collapsed = ref(false)
</script>
