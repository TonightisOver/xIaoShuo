<template>
  <div
    v-if="visible"
    class="w-72 border-l border-neutral-200 bg-white/80 backdrop-blur overflow-y-auto"
  >
    <div class="p-4 border-b border-neutral-100 flex items-center justify-between">
      <h3 class="text-sm font-semibold text-neutral-800">章节分析</h3>
      <button class="text-neutral-400 hover:text-neutral-600" @click="$emit('close')">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>
    <!-- Summary -->
    <div v-if="summary" class="p-4 grid grid-cols-2 gap-2">
      <div v-for="(count, type) in filteredSummary" :key="type"
        class="rounded-lg border px-3 py-2 text-center"
        :class="typeBorderClass(type)"
      >
        <div class="text-lg font-bold" :class="typeTextClass(type)">{{ count }}</div>
        <div class="text-xs text-neutral-500">{{ typeLabel(type) }}</div>
      </div>
    </div>
    <!-- Annotations list -->
    <div class="px-4 pb-4 space-y-2">
      <div
        v-for="(ann, i) in annotations"
        :key="i"
        class="rounded border px-3 py-2 text-xs cursor-pointer hover:shadow-sm transition"
        :class="typeBorderClass(ann.type)"
        @click="$emit('scroll-to', ann)"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="inline-block w-2 h-2 rounded-full" :class="typeBgClass(ann.type)"></span>
          <span class="font-semibold" :class="typeTextClass(ann.type)">{{ typeLabel(ann.type) }}</span>
          <span class="text-neutral-400 truncate">{{ ann.label }}</span>
        </div>
        <div class="text-neutral-600 line-clamp-2">{{ ann.description }}</div>
      </div>
      <div v-if="!annotations.length" class="text-center text-neutral-400 py-8">
        暂无标注数据
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  annotations: { type: Array, default: () => [] },
  summary: { type: Object, default: null },
})

defineEmits(['close', 'scroll-to'])

const filteredSummary = computed(() => {
  if (!props.summary) return {}
  const { total, ...rest } = props.summary
  return rest
})

const typeConfig = {
  foreshadow: { label: '伏笔', border: 'border-purple-200', text: 'text-purple-700', bg: 'bg-purple-500' },
  hook: { label: '钩子', border: 'border-orange-200', text: 'text-orange-700', bg: 'bg-orange-500' },
  plot_point: { label: '情节', border: 'border-blue-200', text: 'text-blue-700', bg: 'bg-blue-500' },
  character_event: { label: '角色', border: 'border-green-200', text: 'text-green-700', bg: 'bg-green-500' },
}

function typeLabel(t) { return typeConfig[t]?.label || t }
function typeBorderClass(t) { return typeConfig[t]?.border || 'border-neutral-200' }
function typeTextClass(t) { return typeConfig[t]?.text || 'text-neutral-700' }
function typeBgClass(t) { return typeConfig[t]?.bg || 'bg-neutral-400' }
</script>
