<template>
  <div class="annotated-text relative leading-relaxed">
    <button
      v-if="annotations.length"
      class="mb-2 text-xs px-2 py-1 rounded border border-ink-200 bg-paper-50/60 text-ink-500 hover:bg-paper-100 transition"
      @click="showAnnotations = !showAnnotations"
    >
      {{ showAnnotations ? '隐藏标注' : '显示标注' }} ({{ annotations.length }})
    </button>
    <div class="whitespace-pre-wrap break-words text-sm leading-7">
      <template v-for="(seg, i) in segments" :key="i">
        <span
          v-if="seg.annotation"
          class="cursor-pointer rounded-sm px-0.5 transition-colors"
          :class="typeClasses(seg.annotation.type)"
          @mouseenter="hovered = seg.annotation"
          @mouseleave="hovered = null"
        >{{ seg.text }}</span>
        <span v-else>{{ seg.text }}</span>
      </template>
    </div>
    <!-- Tooltip -->
    <div
      v-if="hovered"
      class="fixed z-50 max-w-xs rounded-lg border border-ink-200 bg-paper-50/95 shadow-lg backdrop-blur px-3 py-2 text-xs animate-fade-in"
      :style="tooltipStyle"
    >
      <div class="font-semibold mb-1" :class="typeTextClass(hovered.type)">
        {{ typeLabel(hovered.type) }}：{{ hovered.label }}
      </div>
      <div class="text-ink-600">{{ hovered.description }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  content: { type: String, default: '' },
  annotations: { type: Array, default: () => [] },
})

const showAnnotations = ref(true)
const hovered = ref(null)

const segments = computed(() => {
  if (!showAnnotations.value || !props.annotations.length) {
    return [{ text: props.content, annotation: null }]
  }
  const sorted = [...props.annotations]
    .filter(a => a.start != null && a.end != null)
    .sort((a, b) => a.start - b.start)
  const result = []
  let cursor = 0
  for (const ann of sorted) {
    const start = Math.max(cursor, ann.start)
    if (start > cursor) {
      result.push({ text: props.content.slice(cursor, start), annotation: null })
    }
    const end = Math.min(ann.end, props.content.length)
    if (end > start) {
      result.push({ text: props.content.slice(start, end), annotation: ann })
      cursor = end
    }
  }
  if (cursor < props.content.length) {
    result.push({ text: props.content.slice(cursor), annotation: null })
  }
  return result
})

const tooltipStyle = computed(() => ({
  top: '20px',
  right: '20px',
}))

const typeMap = {
  foreshadow: { classes: 'bg-purple-100 text-purple-800 border-purple-200', label: '伏笔' },
  hook: { classes: 'bg-orange-100 text-orange-800 border-orange-200', label: '钩子' },
  plot_point: { classes: 'bg-blue-100 text-blue-800 border-blue-200', label: '情节' },
  character_event: { classes: 'bg-green-100 text-green-800 border-green-200', label: '角色' },
}

function typeClasses(type) {
  return typeMap[type]?.classes || 'bg-paper-100'
}
function typeTextClass(type) {
  const map = {
    foreshadow: 'text-purple-700',
    hook: 'text-orange-700',
    plot_point: 'text-blue-700',
    character_event: 'text-green-700',
  }
  return map[type] || 'text-ink-600'
}
function typeLabel(type) {
  return typeMap[type]?.label || type
}
</script>
