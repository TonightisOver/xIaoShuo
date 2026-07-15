<template>
  <div class="knowledge-graph animate-fade-up">
    <!-- Toolbar -->
    <div class="flex items-center justify-between gap-4 mb-4">
      <div class="flex items-center gap-2">
        <h2 class="text-base font-bold text-ink-700 heading-serif">实体关系知识图谱</h2>
        <span
          v-if="entities.length"
          class="text-[11px] bg-paper-100 text-vermilion-600 px-2 py-0.5 rounded-md font-medium border border-ink-100"
        >
          {{ entities.length }} 节点 / {{ triples.length }} 关系
        </span>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="selectedNodeId"
          @click="clearSelection"
          class="btn-secondary text-xs py-1.5 px-3"
        >
          清除高亮
        </button>
        <button
          @click="fitGraph"
          class="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3.5 h-3.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
          </svg>
          <span>适应视图</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-24">
      <div class="w-10 h-10 rounded-full border-4 border-purple-500/10 border-t-purple-600 animate-spin"></div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="text-center py-12 text-red-500 text-sm bg-red-50 rounded-xl border border-red-100 animate-fade-in">
      {{ error }}
    </div>

    <!-- Empty -->
    <div v-else-if="!entities.length" class="text-center py-12 text-ink-400 text-sm bg-paper-50 rounded-xl border border-ink-200 animate-fade-in">
      暂无知识图谱数据。请先生成章节内容后触发知识抽取。
    </div>

    <!-- Graph Canvas -->
    <div
      v-else
      ref="cyContainer"
      class="cy-canvas w-full min-h-[500px] rounded-xl border border-ink-200 bg-paper-50 overflow-hidden relative animate-fade-in"
    ></div>

    <!-- Legend -->
    <div class="flex flex-wrap gap-4 mt-3 px-4 py-2.5 rounded-lg bg-paper-50 border border-ink-200 text-xs text-ink-600">
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-blue-500"></span> 人物
      </span>
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-emerald-500"></span> 地点
      </span>
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-orange-500"></span> 事件
      </span>
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-purple-500"></span> 物品
      </span>
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 border border-ink-300 bg-paper-50"></span> 其他
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'

const props = defineProps({
  novelId: { type: String, required: true },
})

const emit = defineEmits(['node-click'])

const cyContainer = ref(null)
const loading = ref(false)
const error = ref('')
const entities = ref([])
const triples = ref([])
const selectedNodeId = ref(null)

let cy = null

// Node color mapping by entity_type
const typeColors = {
  character: '#3b82f6',
  location: '#10b981',
  event: '#f97316',
  item: '#8b5cf6',
}
const defaultColor = '#a3a3a3'

function getColor(type) {
  return typeColors[type] || defaultColor
}

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/v1/projects/${props.novelId}/knowledge-graph/visualization`)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `请求失败 (${res.status})`)
    }
    const data = await res.json()
    entities.value = data.nodes || []
    triples.value = data.edges || []
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function initCytoscape() {
  if (!cyContainer.value || !entities.value.length) return

  // Destroy previous instance
  if (cy) {
    cy.destroy()
    cy = null
  }

  const elements = []

  // Add nodes
  entities.value.forEach((e) => {
    elements.push({
      group: 'nodes',
      data: {
        id: e.id,
        label: e.name,
        type: e.type || 'unknown',
        entity: e,
      },
    })
  })

  // Add edges
  triples.value.forEach((t) => {
    elements.push({
      group: 'edges',
      data: {
        id: t.id || `${t.source}-${t.target}-${t.predicate}`,
        source: t.source,
        target: t.target,
        label: t.predicate,
        triple: t,
      },
    })
  })

  cy = cytoscape({
    container: cyContainer.value,
    elements,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': (ele) => getColor(ele.data('type')),
          label: 'data(label)',
          'font-size': '12px',
          'font-weight': '600',
          color: '#1c1c1e',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 8,
          width: 36,
          height: 36,
          'border-width': 2,
          'border-color': '#ffffff',
          'shadow-blur': 8,
          'shadow-opacity': 0.15,
          'shadow-color': (ele) => getColor(ele.data('type')),
        },
      },
      {
        selector: 'edge',
        style: {
          width: 1.5,
          'line-color': '#d4d4d8',
          'target-arrow-color': '#d4d4d8',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.8,
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': '9px',
          color: '#71717a',
          'text-background-color': '#ffffff',
          'text-background-opacity': 1,
          'text-background-padding': 2,
          'text-rotation': 'autorotate',
        },
      },
      {
        selector: 'node:selected',
        style: {
          'border-color': '#6366f1',
          'border-width': 3,
          'shadow-blur': 16,
          'shadow-opacity': 0.3,
        },
      },
      {
        selector: 'edge:selected',
        style: {
          'line-color': '#6366f1',
          'target-arrow-color': '#6366f1',
          width: 2.5,
        },
      },
    ],
    layout: {
      name: 'cose',
      animate: false,
      nodeRepulsion: () => 8000,
      idealEdgeLength: () => 180,
      gravity: 0.8,
      numIter: 1000,
      fit: true,
      padding: 40,
    },
    wheelSensitivity: 0.3,
  })

  // Click handler: highlight subgraph
  cy.on('tap', 'node', (evt) => {
    const node = evt.target
    const nodeId = node.id()
    selectedNodeId.value = nodeId
    emit('node-click', node.data('entity'))

    // Reset all styles
    cy.nodes().style({
      opacity: 0.15,
      'border-color': '#ffffff',
      'border-width': 2,
    })
    cy.edges().style({ opacity: 0.08 })

    // Highlight selected node and its neighbors
    node.style({ opacity: 1, 'border-color': '#6366f1', 'border-width': 3 })
    node.neighborhood().nodes().style({ opacity: 1 })
    node.neighborhood().edges().style({ opacity: 1 })
    node.connectedEdges().style({ opacity: 1 })
  })

  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      clearSelection()
    }
  })
}

function clearSelection() {
  selectedNodeId.value = null
  if (!cy) return
  cy.nodes().style({
    opacity: 1,
    'border-color': '#ffffff',
    'border-width': 2,
  })
  cy.edges().style({ opacity: 1 })
  cy.nodes().unselect()
  cy.edges().unselect()
}

function fitGraph() {
  if (cy) {
    cy.fit(undefined, 40)
    cy.center()
  }
}

watch(
  () => props.novelId,
  async () => {
    await fetchData()
    await nextTick()
    initCytoscape()
  },
)

onMounted(async () => {
  await fetchData()
  await nextTick()
  initCytoscape()
})

onUnmounted(() => {
  if (cy) {
    cy.destroy()
    cy = null
  }
})
</script>

<style scoped>
.cy-canvas {
  position: relative;
}
</style>
