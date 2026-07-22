<template>
  <div class="card p-4 space-y-4" data-impact-preview-panel>
    <h3 class="heading-serif text-lg">影响范围预览</h3>

    <div class="grid grid-cols-2 gap-3">
      <div
        v-for="col in columns"
        :key="col.key"
        :data-col="col.key"
        class="rounded-lg border border-ink-200 p-3 bg-paper-50"
      >
        <p class="text-xs font-semibold text-ink-500 mb-1">{{ col.label }}</p>
        <ul class="space-y-0.5">
          <li v-for="item in (impact[col.key] || [])" :key="itemKey(item)" class="text-sm text-ink-700">
            {{ itemLabel(item) }}
          </li>
          <li v-if="!(impact[col.key] || []).length" class="text-xs text-ink-300">—</li>
        </ul>
      </div>
    </div>

    <div class="space-y-2">
      <p class="text-xs font-semibold text-ink-500">选择处理方式</p>
      <label
        v-for="opt in choices"
        :key="opt.value"
        class="flex items-center gap-2 text-sm text-ink-700 cursor-pointer"
      >
        <input
          type="radio"
          name="impact-choice"
          :data-choice="opt.value"
          :value="opt.value"
          v-model="selected"
          @change="$emit('choice', opt.value)"
        />
        <span>{{ opt.label }}</span>
      </label>
    </div>
  </div>
</template>

<script setup>
/**
 * ImpactPreviewPanel —— 上游变更的影响范围展示 + 处理方式选择。
 *
 * props.impact: {
 *   upstream: string[],
 *   direct_downstream: string[],
 *   full_downstream: string[],
 *   regenerable: string[],     // 未锁/未确认 → 可重生成
 *   to_mark_stale: string[],   // 已锁/已确认 → 仅标记过期
 * }
 * emit choice(value): save_only | regen_direct | regen_all | mark_stale
 */
import { ref } from 'vue'

defineProps({
  impact: { type: Object, required: true },
})

defineEmits(['choice'])

const selected = ref('save_only')

function itemKey(item) {
  return typeof item === 'object'
    ? `${item.artifact_type}:${item.artifact_id}`
    : String(item)
}

function itemLabel(item) {
  return typeof item === 'object'
    ? `${item.artifact_type}/${item.artifact_id}`
    : String(item)
}

const columns = [
  { key: 'direct_downstream', label: '直接下游' },
  { key: 'full_downstream', label: '全部下游' },
  { key: 'regenerable', label: '可重生成' },
  { key: 'to_mark_stale', label: '仅标记过期' },
]

const choices = [
  { value: 'save_only', label: '仅保存（不动下游）' },
  { value: 'regen_direct', label: '重生成直接下游' },
  { value: 'regen_all', label: '重生成全部受影响' },
  { value: 'mark_stale', label: '保留下游，仅标记过期' },
]
</script>
