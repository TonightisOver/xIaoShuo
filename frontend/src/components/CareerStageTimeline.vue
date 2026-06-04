<template>
  <div class="relative pl-8 py-2 space-y-6">
    <!-- 垂直连接线 -->
    <div class="absolute left-3.5 top-3 bottom-3 w-0.5 bg-neutral-200/80"></div>

    <div
      v-for="(stage, index) in displayStages"
      :key="index"
      class="relative group"
    >
      <!-- 节点状态徽标 -->
      <div
        class="absolute -left-[27px] top-1.5 w-5 h-5 rounded-full flex items-center justify-center cursor-pointer transition-all duration-300 border shadow-sm"
        :class="getBadgeClass(index)"
        @click="selectStage(index)"
      >
        <!-- 已完成阶段：勾号 -->
        <svg v-if="index < currentStageIndex" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor" class="w-3 h-3 text-white">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
        <!-- 当前阶段：高亮呼吸点 -->
        <span v-else-if="index === currentStageIndex" class="relative flex h-2 w-2">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-accent-600"></span>
        </span>
        <!-- 未完成阶段：小空心圆 -->
        <span v-else class="w-1.5 h-1.5 rounded-full bg-neutral-300 group-hover:bg-neutral-400"></span>
      </div>

      <!-- 节点卡片内容 -->
      <div
        class="glass-panel rounded-xl p-3.5 border transition-all duration-300 cursor-pointer text-left"
        :class="[
          index === currentStageIndex ? 'border-accent-400/40 bg-accent-50/40 shadow-sm ring-1 ring-accent-400/20' : 'border-neutral-200/50 bg-white/70 hover:border-neutral-300 hover:bg-neutral-50/50',
          activeDetailIndex === index ? 'shadow-md border-neutral-300 bg-white/90' : ''
        ]"
        @click="selectStage(index)"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded" :class="index <= currentStageIndex ? 'bg-accent-100 text-accent-700' : 'bg-neutral-100 text-neutral-500'">
              Lvl {{ stage.level || index + 1 }}
            </span>
            <h4 class="text-xs font-semibold text-neutral-800" :class="index === currentStageIndex ? 'text-accent-700 font-bold' : ''">
              {{ stage.name || `阶段 ${index + 1}` }}
            </h4>
          </div>
          <div class="flex items-center gap-1.5">
            <span v-if="index < currentStageIndex" class="text-[9px] text-emerald-600 font-semibold bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-100">已达标</span>
            <span v-else-if="index === currentStageIndex" class="text-[9px] text-accent-600 font-semibold bg-accent-50 px-1.5 py-0.2 rounded border border-accent-100 animate-pulse">当前修习</span>
            <span v-else class="text-[9px] text-neutral-400 font-medium">未解锁</span>
          </div>
        </div>

        <!-- 阶段简述与展开描述 -->
        <transition name="expand">
          <div v-if="activeDetailIndex === index" class="mt-2 pt-2 border-t border-neutral-100/80 text-[11px] text-neutral-600 leading-relaxed space-y-1">
            <p><strong class="text-neutral-700">修行描述：</strong>{{ stage.description || '暂无详细描述。' }}</p>
            <p v-if="stage.breakthrough"><strong class="text-amber-700">突破条件：</strong>{{ stage.breakthrough }}</p>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  stages: {
    type: Array,
    default: () => []
  },
  currentStageIndex: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['select-stage'])

const activeDetailIndex = ref(props.currentStageIndex)

// 保证正好 10 个阶段
const displayStages = computed(() => {
  const result = [...props.stages]
  while (result.length < 10) {
    const nextLvl = result.length + 1
    result.push({
      level: nextLvl,
      name: `阶段 ${nextLvl}`,
      description: `这是职业体系的第 ${nextLvl} 阶段，包含深入的修行与探索。`,
      breakthrough: `修为达到当前阶段圆满并突破瓶颈。`
    })
  }
  return result.slice(0, 10)
})

watch(() => props.currentStageIndex, (newVal) => {
  activeDetailIndex.value = newVal
})

function selectStage(index) {
  activeDetailIndex.value = activeDetailIndex.value === index ? -1 : index
  emit('select-stage', { index, stage: displayStages.value[index] })
}

function getBadgeClass(index) {
  if (index < props.currentStageIndex) {
    return 'bg-emerald-500 border-emerald-500 hover:bg-emerald-600 hover:border-emerald-600 text-white'
  } else if (index === props.currentStageIndex) {
    return 'bg-white border-accent-600 ring-2 ring-accent-100'
  } else {
    return 'bg-neutral-100 border-neutral-300 hover:bg-neutral-200 text-neutral-400'
  }
}
</script>

<style scoped>
.glass-panel {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.25s ease-out;
  max-height: 150px;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  margin-top: 0;
  border-top-color: transparent;
}
</style>
