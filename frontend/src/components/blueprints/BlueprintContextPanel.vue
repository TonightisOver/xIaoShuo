<template>
  <div class="flex flex-col h-full overflow-auto p-4 space-y-4 text-sm">
    <!-- 章节大纲 -->
    <section>
      <h4 class="text-xs font-semibold text-ink-500 mb-1">章节大纲</h4>
      <div v-if="workspace?.outline" class="text-ink-700 text-xs whitespace-pre-wrap">
        {{ JSON.stringify(workspace.outline.content, null, 2) }}
      </div>
      <p v-else class="text-ink-400 text-xs">无大纲</p>
    </section>

    <!-- 上章 state_delta -->
    <section>
      <h4 class="text-xs font-semibold text-ink-500 mb-1">上一章连续性</h4>
      <div v-if="workspace?.previous_state_delta" class="text-ink-700 text-xs">
        {{ JSON.stringify(workspace.previous_state_delta) }}
      </div>
      <p v-else class="text-ink-400 text-xs">无</p>
    </section>

    <!-- 正文摘要 + 质量 -->
    <section>
      <h4 class="text-xs font-semibold text-ink-500 mb-1">正文状态</h4>
      <div v-if="workspace?.chapter_summary" class="text-xs text-ink-700">
        <span>{{ workspace.chapter_summary.status }}</span>
        <span class="text-ink-400 mx-1">·</span>
        <span>{{ workspace.chapter_summary.word_count }} 字</span>
        <span v-if="workspace.quality_status" class="text-ink-400 mx-1">·</span>
        <span v-if="workspace.quality_status" data-quality-status>{{ workspace.quality_status }}</span>
      </div>
      <p v-else class="text-ink-400 text-xs">无正文</p>
    </section>

    <!-- 影响预览 -->
    <section>
      <h4 class="text-xs font-semibold text-ink-500 mb-1">影响范围</h4>
      <button @click="$emit('load-impact')" class="btn-secondary text-xs">预览影响</button>
      <div v-if="impact" class="mt-1 text-xs text-ink-600">
        <ImpactPreviewPanel :impact="impact" @choice="onChoice" />
      </div>
    </section>

    <!-- 控制 -->
    <section class="space-y-2">
      <button @click="$emit('confirm')" :disabled="!canControl"
              class="btn-secondary text-xs w-full">确认</button>
      <button @click="$emit('lock')" :disabled="!canLock"
              class="btn-secondary text-xs w-full">锁定</button>
      <button @click="$emit('unlock')" :disabled="!locked"
              class="btn-secondary text-xs w-full">解锁</button>
      <button @click="$emit('regenerate')" class="btn-primary text-xs w-full">重新生成</button>
      <button @click="$emit('view-versions')" class="btn-secondary text-xs w-full">版本历史</button>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ImpactPreviewPanel from '../ImpactPreviewPanel.vue'

const props = defineProps({
  workspace: { type: Object, default: null },
  impact: { type: Object, default: null },
  operations: { type: Array, default: () => [] },
})
const emit = defineEmits(['confirm', 'lock', 'unlock', 'regenerate', 'view-versions', 'load-impact', 'choice'])

const locked = computed(() => props.workspace?.control?.locked)
const canControl = computed(() => props.workspace?.control && !locked.value)
const canLock = computed(() => {
  const s = props.workspace?.control?.control_status
  return s === 'confirmed' || s === 'approved'
})

function onChoice(c) { emit('choice', c) }
</script>
