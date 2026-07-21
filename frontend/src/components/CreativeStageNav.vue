<template>
  <nav class="flex flex-wrap gap-2" data-creative-stage-nav>
    <button
      v-for="stage in stages"
      :key="stage.number"
      type="button"
      :data-stage-item="stage.number"
      :data-stage-status="stage.control ? stage.control.control_status : 'none'"
      :class="[
        'flex flex-col items-center justify-center rounded-lg border px-3 py-2 min-w-[72px] transition-colors text-center',
        stageClasses(stage),
        stage.number === creativeStage ? 'ring-2 ring-vermilion-500 ring-offset-1' : '',
      ]"
      :title="stage.control ? stage.control.control_status : '未生成'"
      @click="$emit('select', stage.number)"
    >
      <span class="text-[10px] text-ink-400 font-semibold">{{ stage.number }}</span>
      <span class="text-xs font-medium text-ink-700 leading-tight">{{ stage.name }}</span>
      <span v-if="stage.control" class="text-[9px] mt-0.5 opacity-80">
        {{ statusLabel(stage.control.control_status) }}
      </span>
    </button>
  </nav>
</template>

<script setup>
/**
 * CreativeStageNav —— 10 阶段创作导航条。
 *
 * props.stages: [{ number, name, artifact_type, control: { control_status } | null }]
 * props.creativeStage: 当前所在阶段（高亮）
 * emit select(stageNumber)
 *
 * control_status → 颜色：
 *   approved/locked → emerald/green（已确认/锁定）
 *   generated      → gray/ink（已生成待审）
 *   edited/draft   → gray/ink
 *   stale          → yellow/amber（上游变更过期）
 *   failed         → red/rose
 *   generating     → blue/sky（生成中）
 */
defineProps({
  stages: { type: Array, required: true },
  creativeStage: { type: Number, default: 1 },
})

defineEmits(['select'])

function statusLabel(status) {
  const map = {
    draft: '草稿', generated: '已生成', edited: '已编辑',
    approved: '已确认', locked: '锁定', stale: '过期',
    generating: '生成中', failed: '失败',
  }
  return map[status] || status
}

function stageClasses(stage) {
  const status = stage.control ? stage.control.control_status : 'none'
  // 基色：approved/locked 绿，generated/edited/draft 灰，stale 黄，failed 红，generating 蓝，none 灰边
  if (status === 'approved' || status === 'locked') {
    return 'bg-emerald-50 border-emerald-300 text-emerald-700'
  }
  if (status === 'stale') {
    return 'bg-amber-50 border-amber-300 text-amber-700'
  }
  if (status === 'failed') {
    return 'bg-rose-50 border-rose-300 text-rose-700'
  }
  if (status === 'generating') {
    return 'bg-sky-50 border-sky-300 text-sky-700'
  }
  // generated / edited / draft / none
  return 'bg-paper-50 border-ink-200 text-ink-600'
}
</script>
