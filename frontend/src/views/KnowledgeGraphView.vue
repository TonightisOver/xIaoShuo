<template>
  <div class="max-w-7xl mx-auto px-6 py-10 font-sans">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-ink-900 flex items-center gap-2">
          <span>🧠 知识图谱</span>
        </h1>
        <p class="text-ink-500 text-xs md:text-sm mt-1">
          实体关系可视化 · 跨章节演化时间线 · 一致性冲突检测
        </p>
      </div>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm flex items-center gap-1">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
        </svg>
        <span>返回小说详情</span>
      </router-link>
    </div>

    <!-- Sub-tabs -->
    <div class="flex gap-1 mb-6 border-b border-ink-200/80">
      <button
        class="px-5 py-3 text-sm font-semibold transition-all relative"
        :class="activeTab === 'graph'
          ? 'text-vermilion-600 font-bold border-b-2 border-vermilion-600'
          : 'text-ink-500 hover:text-ink-800'"
        @click="activeTab = 'graph'"
      >
        🌐 实体关系网络
      </button>
      <button
        class="px-5 py-3 text-sm font-semibold transition-all relative"
        :class="activeTab === 'timeline'
          ? 'text-vermilion-600 font-bold border-b-2 border-vermilion-600'
          : 'text-ink-500 hover:text-ink-800'"
        @click="activeTab = 'timeline'"
      >
        📅 演化时间线
      </button>
      <button
        class="px-5 py-3 text-sm font-semibold transition-all relative"
        :class="activeTab === 'conflicts'
          ? 'text-vermilion-600 font-bold border-b-2 border-vermilion-600'
          : 'text-ink-500 hover:text-ink-800'"
        @click="activeTab = 'conflicts'"
      >
        ⚠️ 一致性冲突
      </button>
    </div>

    <!-- Tab: Entity Graph -->
    <div v-show="activeTab === 'graph'" class="space-y-4">
      <KnowledgeGraph :novel-id="novelId" @node-click="onNodeClick" />
    </div>

    <!-- Tab: Timeline -->
    <div v-show="activeTab === 'timeline'" class="space-y-4">
      <TimelineView :novel-id="novelId" />
    </div>

    <!-- Tab: Conflicts -->
    <div v-show="activeTab === 'conflicts'" class="space-y-4">
      <ConflictPanel :novel-id="novelId" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import KnowledgeGraph from '../components/KnowledgeGraph.vue'
import TimelineView from '../components/TimelineView.vue'
import ConflictPanel from '../components/ConflictPanel.vue'

const route = useRoute()
const novelId = route.params.id
const activeTab = ref('graph')

function onNodeClick(entity) {
  // When a node is clicked, optionally switch to timeline tab for that entity
  // For now just log; can be enhanced to auto-switch and select entity
  console.log('Node clicked:', entity)
}
</script>
