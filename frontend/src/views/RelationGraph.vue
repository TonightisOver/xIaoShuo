<template>
  <div class="max-w-7xl mx-auto px-6 py-10 font-sans">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
      <div>
        <div class="flex items-center gap-3 mb-2 flex-wrap">
          <h1 class="text-2xl font-bold tracking-tight text-[#1d1d1f] flex items-center gap-2">
            <span>全景故事与三层知识图谱</span>
            <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-purple-50 text-purple-600 border border-purple-200/50">
              双引擎分析
            </span>
          </h1>
        </div>
        <p class="text-[#86868b] text-xs md:text-sm">提供故事脉络骨架测绘与智能抽取的深层因果关系网模型</p>
      </div>
      <div>
        <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm flex items-center gap-1">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" />
          </svg>
          <span>返回小说详情</span>
        </router-link>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-1 mb-6 border-b border-gray-200/80">
      <button
        class="px-5 py-3 text-sm font-semibold transition-all relative"
        :class="activeTab === 'structure' ? 'text-purple-600 font-bold border-b-2 border-purple-600' : 'text-gray-500 hover:text-gray-800'"
        @click="activeTab = 'structure'"
      >
        🎨 故事框架拓扑
      </button>
      <button
        class="px-5 py-3 text-sm font-semibold transition-all relative"
        :class="activeTab === 'knowledge' ? 'text-purple-600 font-bold border-b-2 border-purple-600' : 'text-gray-500 hover:text-gray-800'"
        @click="switchToKnowledge"
      >
        🧠 活态三层图谱
      </button>
    </div>

    <!-- 故事结构 Tab -->
    <div v-show="activeTab === 'structure'" class="space-y-4">
      <div v-if="loading" class="flex flex-col items-center justify-center py-28 space-y-4">
        <div class="w-12 h-12 rounded-full border-4 border-purple-500/10 border-t-purple-600 animate-spin"></div>
        <p class="text-gray-500 text-sm">正在测绘小说故事框架，请稍候...</p>
      </div>
      <div v-else-if="!hasData" class="card text-center py-16 px-6 max-w-xl mx-auto rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div class="w-16 h-16 bg-purple-50 text-purple-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">🎨</div>
        <h3 class="text-base font-bold text-gray-800 mb-2">暂无故事大纲框架</h3>
        <p class="text-gray-500 text-xs md:text-sm mb-6 max-w-sm mx-auto leading-relaxed">
          小说尚未生成核心故事主线或人物弧光。您可以一键让 AI 自动生成故事线结构。
        </p>
        <div class="flex flex-col items-center gap-3">
          <button
            @click="generateStorylines"
            :disabled="generatingStorylines"
            class="btn-primary text-sm px-6 py-2.5 rounded-lg inline-flex items-center gap-2 shadow-sm disabled:opacity-50"
          >
            <svg v-if="generatingStorylines" class="w-4 h-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>{{ generatingStorylines ? '正在生成故事线...' : '一键生成故事线' }}</span>
          </button>
          <p v-if="storylineGenError" class="text-xs text-red-500 mt-1">{{ storylineGenError }}</p>
          <router-link :to="`/novels/${novelId}`" class="text-xs text-gray-400 hover:text-gray-600 mt-2">
            或返回小说详情手动配置
          </router-link>
        </div>
      </div>

      <div v-else class="card p-6 rounded-2xl bg-white overflow-x-auto relative">
        <div ref="treeContainer" class="min-h-[550px] w-full"></div>
      </div>

      <!-- Legend -->
      <div v-if="hasData" class="flex flex-wrap gap-4 px-5 py-3.5 rounded-xl bg-white border border-gray-200 text-xs text-gray-600 shadow-sm">
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-blue-500 shadow-[0_1px_4px_rgba(59,130,246,0.3)]"></span> 故事主线</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_1px_4px_rgba(16,185,129,0.3)]"></span> 角色卡</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-purple-500 shadow-[0_1px_4px_rgba(139,92,246,0.3)]"></span> 人物弧光</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-amber-500 shadow-[0_1px_4px_rgba(245,158,11,0.3)]"></span> 剧情场景</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-gray-500"></span> 情节事件</span>
      </div>
    </div>

    <!-- 活态知识图谱 Tab -->
    <div v-show="activeTab === 'knowledge'" class="space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <!-- 三层子 Tab 控制 -->
        <div class="flex items-center p-1 rounded-xl bg-gray-100 border border-gray-200/60 max-w-md shadow-inner">
          <button
            v-for="sub in subLayers"
            :key="sub.id"
            class="flex-1 py-1.5 px-3 text-xs font-bold rounded-lg transition-all"
            :class="activeSubLayer === sub.id
              ? `${sub.activeBg} text-white shadow-sm`
              : 'text-gray-500 hover:text-gray-800'"
            @click="changeSubLayer(sub.id)"
          >
            {{ sub.icon }} {{ sub.name }}
          </button>
        </div>
        <button
          @click="toggleShowAll"
          :disabled="kgLoading"
          class="text-xs font-medium px-3 py-1.5 rounded-lg border transition-all disabled:opacity-50"
          :class="showAll ? 'bg-purple-50 text-purple-600 border-purple-200' : 'bg-gray-50 text-gray-500 border-gray-200 hover:text-gray-800'"
        >
          {{ showAll ? '当前：显示全部' : '当前：只显示主要' }}
        </button>
      </div>

      <div v-if="kgLoading" class="flex flex-col items-center justify-center py-28 space-y-4">
        <div class="w-12 h-12 rounded-full border-4 border-purple-500/10 border-t-purple-600 animate-spin"></div>
        <p class="text-gray-500 text-sm">正在抽取并编译三层网络图谱中，请稍候...</p>
      </div>
      
      <!-- Graph Empty state with One-Click Extraction -->
      <div v-else-if="!kgHasData" class="card text-center py-16 px-6 max-w-xl mx-auto rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div class="w-16 h-16 bg-purple-50 text-purple-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">🧠</div>
        <h3 class="text-base font-bold text-gray-800 mb-2">暂无三层因果知识图谱</h3>
        <p class="text-gray-500 text-xs md:text-sm mb-6 max-w-sm mx-auto leading-relaxed">
          章节正文尚未产生，或尚未触发知识图谱自动解析。如果此小说已经完成生成（或属于导入的已有章节数据），您可以一键重新全量提取图谱。
        </p>
        <div class="flex flex-col items-center justify-center gap-3">
          <button 
            @click="reExtractKG" 
            :disabled="extracting"
            class="btn-primary text-sm px-6 py-2.5 rounded-lg inline-flex items-center gap-2 shadow-sm disabled:opacity-50"
          >
            <svg v-if="extracting" class="w-4 h-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span v-else>🔮</span>
            <span>一键全量抽取图谱</span>
          </button>
          <p v-if="extractProgress" class="text-xs font-semibold text-purple-700 bg-purple-50 px-3 py-1.5 rounded-lg border border-purple-100/50 animate-pulse mt-2">
            {{ extractProgress }}
          </p>
        </div>
      </div>

      <!-- Graph Canvas Panel -->
      <div v-else class="card p-4 rounded-2xl bg-white shadow-sm overflow-x-auto relative">
        <!-- Quick manual re-extract button in top-right of canvas panel -->
        <div class="absolute top-4 right-4 z-10 flex items-center gap-2">
          <button 
            @click="reExtractKG" 
            :disabled="extracting"
            class="bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-xs font-bold shadow-sm inline-flex items-center gap-1.5 disabled:opacity-50 transition-all"
          >
            <svg v-if="extracting" class="w-3 h-3 animate-spin text-purple-600" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span v-else>⚡</span>
            <span>重新全量提取</span>
          </button>
          <span v-if="extractProgress" class="bg-purple-50 text-purple-700 border border-purple-100 rounded-lg px-2.5 py-1 text-[11px] font-medium shadow-sm animate-pulse">
            {{ extractProgress }}
          </span>
        </div>

        <div ref="kgContainer" class="min-h-[600px] w-full rounded-xl overflow-hidden bg-radial-glow-light"></div>
      </div>

      <!-- KG Legends based on active sub tab -->
      <div v-if="kgHasData" class="flex flex-wrap gap-4 px-5 py-3.5 rounded-xl bg-white border border-gray-200 text-xs text-gray-600 shadow-sm">
        <template v-if="activeSubLayer === 'character'">
          <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-blue-500 shadow-[0_1px_4px_rgba(59,130,246,0.3)]"></span> 角色实体</span>
          <span class="flex items-center gap-1.5"><span class="w-3.5 h-0.5 bg-blue-400"></span> 人际关系网络</span>
        </template>
        <template v-else-if="activeSubLayer === 'plot'">
          <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-amber-500 shadow-[0_1px_4px_rgba(245,158,11,0.3)]"></span> 剧情事件</span>
          <span class="flex items-center gap-1.5"><span class="w-3.5 h-0.5 bg-amber-400"></span> 显式事件关联</span>
          <span class="flex items-center gap-1.5"><span class="w-3.5 h-0.5 border-t border-dashed border-amber-400"></span> 时序推进流 (Chapter Axis)</span>
        </template>
        <template v-else-if="activeSubLayer === 'foreshadowing'">
          <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-purple-500 shadow-[0_1px_4px_rgba(139,92,246,0.3)]"></span> 伏笔节点 (已埋/未收)</span>
          <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-blue-500"></span> 关联人物/事件</span>
          <span class="flex items-center gap-1.5"><span class="w-3.5 h-0.5 bg-purple-400"></span> 埋藏/回收生命线</span>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useRelationGraph } from '../composables/useRelationGraph.js'
import { useKnowledgeGraph } from '../composables/useKnowledgeGraph.js'

const route = useRoute()
const novelId = route.params.id

// --- DOM refs ---
const treeContainer = ref(null)
const kgContainer = ref(null)

// --- UI state ---
const activeTab = ref('structure')
const activeSubLayer = ref('character')
const showAll = ref(false)

const subLayers = [
  { id: 'character', name: '角色关系谱', icon: '👥', activeBg: 'bg-blue-600' },
  { id: 'plot', name: '剧情事件谱', icon: '⏳', activeBg: 'bg-amber-500' },
  { id: 'foreshadowing', name: '伏笔填坑谱', icon: '🔮', activeBg: 'bg-purple-600' }
]

// --- Relation graph (structure tab) ---
const { relations, loading, load } = useRelationGraph(novelId, treeContainer)

const hasData = computed(() => {
  if (!relations.value) return false
  const r = relations.value
  return r.storylines.length || r.character_arcs.length || r.scenes.length
})

// --- Knowledge graph (knowledge tab) ---
const {
  kgData, kgLoading, extracting, extractProgress,
  generatingStorylines, storylineGenError,
  loadThreeLayerGraph, reExtractKG: _reExtractKG, generateStorylines: _generateStorylines,
  renderKnowledgeGraph, getActiveGraphData,
} = useKnowledgeGraph(novelId, kgContainer, activeSubLayer)

const kgHasData = computed(() => {
  if (!kgData.value) return false
  const activeGraph = getActiveGraphData()
  return activeGraph && activeGraph.nodes && activeGraph.nodes.length > 0
})

// --- Tab / sub-layer actions ---
function changeSubLayer(layerId) {
  activeSubLayer.value = layerId
  nextTick(() => {
    const data = getActiveGraphData()
    if (data) renderKnowledgeGraph(data)
  })
}

async function toggleShowAll() {
  showAll.value = !showAll.value
  await loadThreeLayerGraph(showAll.value)
}

async function switchToKnowledge() {
  activeTab.value = 'knowledge'
  if (!kgData.value) {
    await loadThreeLayerGraph(showAll.value)
  }
}

// Wrappers that pass the load callback where needed
function reExtractKG() {
  _reExtractKG(load)
}

function generateStorylines() {
  _generateStorylines(load)
}

onMounted(load)
</script>

<style scoped>
.bg-radial-glow-light {
  background-color: #f9f9fb;
  background-image: radial-gradient(#e5e5ea 1.2px, transparent 1.2px);
  background-size: 20px 20px;
  position: relative;
}
.bg-radial-glow-light::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.02) 0%, transparent 70%);
  pointer-events: none;
}
</style>
