<template>
  <div class="p-3 border-b border-ink-200 bg-paper-50 flex flex-wrap items-center gap-2">
    <span class="text-xs text-ink-500">已选 {{ selectedCount }} 章</span>
    <button @click="onPreview('generate')" :disabled="!selectedCount" data-batch-generate class="btn-primary text-xs disabled:opacity-40">批量生成</button>
    <button @click="$emit('batch-confirm')" :disabled="!selectedCount" data-batch-confirm class="btn-secondary text-xs disabled:opacity-40">批量确认</button>
    <button @click="$emit('batch-lock')" :disabled="!selectedCount" data-batch-lock class="btn-secondary text-xs disabled:opacity-40">批量锁定</button>
    <button @click="$emit('batch-unlock')" :disabled="!selectedCount" data-batch-unlock class="btn-secondary text-xs disabled:opacity-40">批量解锁</button>

    <!-- 预览 -->
    <div v-if="batchPreview" class="w-full mt-2 p-2 rounded bg-ink-50 text-xs text-ink-600" data-batch-preview>
      将处理 {{ batchPreview.target_chapters?.length || 0 }} 章 ·
      跳过锁定 {{ batchPreview.skipped_locked?.length || 0 }} ·
      跳过已确认 {{ batchPreview.skipped_confirmed?.length || 0 }}
    </div>

    <!-- 逐章结果 -->
    <div v-if="batchResult" class="w-full mt-2 space-y-1" data-batch-result>
      <div v-for="r in batchResult.accepted" :key="r.chapter_number"
           class="text-xs text-green-700">第{{ r.chapter_number }}章 → 任务 {{ r.task_id }}</div>
      <div v-for="r in batchResult.failed_to_enqueue" :key="r.chapter_number"
           class="text-xs text-red-700">第{{ r.chapter_number }}章 → {{ r.error }}</div>
      <div v-for="r in batchResult.results" :key="`control-${r.chapter_number}`"
           :class="['text-xs', r.status === 'ok' ? 'text-green-700' : 'text-red-700']">
        第{{ r.chapter_number }}章 →
        <template v-if="r.status === 'ok'">成功</template>
        <template v-else-if="r.status === 'conflict'">版本冲突（当前 v{{ r.current_version }}）</template>
        <template v-else>{{ r.error || r.status }}</template>
      </div>
      <div v-if="!batchResult.accepted?.length && !batchResult.failed_to_enqueue?.length && !batchResult.results?.length"
           class="text-xs text-ink-400">无结果</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  selectedSet: { type: Set, default: () => new Set() },
  batchPreview: { type: Object, default: null },
  batchResult: { type: Object, default: null },
})
const emit = defineEmits(['batch-generate', 'batch-confirm', 'batch-lock', 'batch-unlock', 'preview-generate'])
const selectedCount = computed(() => props.selectedSet.size)
function onPreview(kind) {
  if (kind === 'generate') emit('preview-generate')
}
</script>
