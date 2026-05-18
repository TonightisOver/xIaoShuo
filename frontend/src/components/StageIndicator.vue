<template>
  <div class="flex items-center gap-1">
    <div
      v-for="(stage, i) in stages"
      :key="stage.id"
      class="flex items-center"
    >
      <div class="flex flex-col items-center">
        <div
          :class="[
            'w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-all',
            stageStatus(stage.id) === 'done' ? 'bg-primary-600 text-white' :
            stageStatus(stage.id) === 'active' ? 'bg-primary-100 text-primary-700 ring-2 ring-primary-400' :
            'bg-ink-100 text-ink-400'
          ]"
        >
          <svg v-if="stageStatus(stage.id) === 'done'" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
          </svg>
          <span v-else>{{ i + 1 }}</span>
        </div>
        <span class="text-[10px] text-ink-500 mt-1 whitespace-nowrap">{{ stage.label }}</span>
      </div>
      <div
        v-if="i < stages.length - 1"
        :class="[
          'w-6 h-0.5 mx-0.5 mb-4',
          stageStatus(stage.id) === 'done' ? 'bg-primary-400' : 'bg-ink-200'
        ]"
      ></div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ currentStage: { type: String, default: '' } })

const stages = [
  { id: 'idea_expansion', label: '创意' },
  { id: 'world_building', label: '世界观' },
  { id: 'character_design', label: '人物' },
  { id: 'outline_generation', label: '大纲' },
  { id: 'chapter_generation', label: '章节' },
  { id: 'quality_check', label: '质检' },
  { id: 'human_review', label: '审核' },
  { id: 'power_systems', label: '力量体系' },
  { id: 'outline_persist', label: '大纲生成' },
  { id: 'storylines', label: '故事线' },
  { id: 'character_arcs', label: '人物弧光' },
  { id: 'scenes', label: '场景' },
  { id: 'auto_conversation', label: '自动对话' },
]

function stageStatus(id) {
  const currentIdx = stages.findIndex(s => s.id === props.currentStage)
  const thisIdx = stages.findIndex(s => s.id === id)
  if (thisIdx < currentIdx) return 'done'
  if (thisIdx === currentIdx) return 'active'
  return 'pending'
}
</script>
