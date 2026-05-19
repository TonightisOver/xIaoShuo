<template>
  <div class="max-w-full mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-ink-900">关系图谱</h1>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm">返回</router-link>
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-2 mb-4 border-b border-ink-200">
      <button
        class="px-4 py-2 text-sm font-medium transition-colors"
        :class="activeTab === 'structure' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-ink-500 hover:text-ink-700'"
        @click="activeTab = 'structure'"
      >故事结构</button>
      <button
        class="px-4 py-2 text-sm font-medium transition-colors"
        :class="activeTab === 'knowledge' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-ink-500 hover:text-ink-700'"
        @click="switchToKnowledge"
      >知识图谱</button>
    </div>

    <!-- 故事结构 Tab -->
    <div v-show="activeTab === 'structure'">
      <div v-if="loading" class="text-center py-20 text-ink-500">加载中...</div>
      <div v-else-if="!hasData" class="text-center py-20 text-ink-400">
        暂无数据，请先添加故事线、人物弧光或场景
      </div>

      <div v-else class="card p-4 overflow-x-auto">
        <div ref="treeContainer" class="min-h-[500px]"></div>
      </div>

      <!-- Legend -->
      <div v-if="hasData" class="flex gap-4 mt-4 text-xs text-ink-600">
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-blue-500"></span> 故事线</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-emerald-500"></span> 人物</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-purple-500"></span> 弧光</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-amber-500"></span> 场景</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-ink-400"></span> 事件</span>
      </div>
    </div>

    <!-- 知识图谱 Tab -->
    <div v-show="activeTab === 'knowledge'">
      <div v-if="kgLoading" class="text-center py-20 text-ink-500">加载中...</div>
      <div v-else-if="!kgHasData" class="text-center py-20 text-ink-400">
        暂无知识图谱数据，请先生成章节后触发抽取
      </div>

      <div v-else class="card p-4 overflow-x-auto">
        <div ref="kgContainer" class="min-h-[500px]"></div>
      </div>

      <!-- KG Legend -->
      <div v-if="kgHasData" class="flex gap-4 mt-4 text-xs text-ink-600">
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full" style="background:#3b82f6"></span> 人物</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full" style="background:#10b981"></span> 地点</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full" style="background:#f59e0b"></span> 组织</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full" style="background:#8b5cf6"></span> 物品</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full" style="background:#ef4444"></span> 事件</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-full" style="background:#6b7280"></span> 伏笔</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as d3 from 'd3'

const route = useRoute()
const novelId = route.params.id

const activeTab = ref('structure')
const loading = ref(true)
const relations = ref(null)
const treeContainer = ref(null)

// Knowledge graph state
const kgLoading = ref(false)
const kgData = ref(null)
const kgContainer = ref(null)

const hasData = computed(() => {
  if (!relations.value) return false
  const r = relations.value
  return r.storylines.length || r.character_arcs.length || r.scenes.length
})

const kgHasData = computed(() => {
  if (!kgData.value) return false
  return kgData.value.nodes.length > 0
})

const nodeColors = {
  root: '#1a6dff',
  category: '#495057',
  storyline: '#3b82f6',
  character: '#10b981',
  arc: '#8b5cf6',
  scene: '#f59e0b',
  event: '#6b7280',
  stage: '#a78bfa',
}

const kgTypeColors = {
  character: '#3b82f6',
  location: '#10b981',
  organization: '#f59e0b',
  item: '#8b5cf6',
  event: '#ef4444',
  foreshadowing: '#6b7280',
}

function transformToTree(data) {
  const children = []

  // Storylines branch
  if (data.storylines.length) {
    const slChildren = data.storylines.map(sl => {
      const slNode = {
        name: `[${sl.type}] ${sl.name}`,
        type: 'storyline',
        children: [],
      }
      // Linked characters
      const links = data.storyline_character_links.filter(l => l.storyline_id === sl.id)
      links.forEach(l => {
        slNode.children.push({ name: `人物#${l.character_id} (${l.role_in_line || '参与'})`, type: 'character' })
      })
      // Key events
      if (sl.key_events) {
        sl.key_events.forEach(ev => {
          slNode.children.push({ name: `${ev.event} Ch.${ev.chapter}`, type: 'event' })
        })
      }
      if (!slNode.children.length) {
        slNode.children.push({ name: '(空)', type: 'event' })
      }
      return slNode
    })
    children.push({ name: '故事线', type: 'category', children: slChildren })
  }

  // Character arcs branch
  if (data.character_arcs.length) {
    const arcChildren = data.character_arcs.map(arc => {
      const arcNode = {
        name: `角色#${arc.character_id}: ${arc.arc_type}`,
        type: 'arc',
        children: [],
      }
      if (arc.stages) {
        arc.stages.forEach(s => {
          arcNode.children.push({ name: `${s.state} (Ch.${s.chapter_range?.[0] || '?'}-${s.chapter_range?.[1] || '?'})`, type: 'stage' })
        })
      }
      if (arc.description) {
        arcNode.children.push({ name: arc.description, type: 'event' })
      }
      if (!arcNode.children.length) {
        arcNode.children.push({ name: '(空)', type: 'event' })
      }
      return arcNode
    })
    children.push({ name: '人物弧光', type: 'category', children: arcChildren })
  }

  // Scenes branch
  if (data.scenes.length) {
    const sceneChildren = data.scenes.map(sc => {
      const scNode = {
        name: sc.name + (sc.location ? ` (${sc.location})` : ''),
        type: 'scene',
        children: [],
      }
      if (sc.appearances) {
        sc.appearances.forEach(a => {
          scNode.children.push({ name: `${a.event || '出现'} Ch.${a.chapter}`, type: 'event' })
        })
      }
      if (!scNode.children.length) {
        scNode.children.push({ name: '(空)', type: 'event' })
      }
      return scNode
    })
    children.push({ name: '场景', type: 'category', children: sceneChildren })
  }

  return { name: '小说图谱', type: 'root', children }
}

function renderTree(data) {
  const container = treeContainer.value
  if (!container) return

  container.innerHTML = ''

  const margin = { top: 20, right: 200, bottom: 20, left: 100 }
  const width = Math.max(container.clientWidth, 800)

  const root = d3.hierarchy(data)
  const treeHeight = Math.max(root.descendants().length * 25, 400)

  const treeLayout = d3.tree().size([treeHeight, width - margin.left - margin.right])
  treeLayout(root)

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', treeHeight + margin.top + margin.bottom)

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  // Links
  g.selectAll('.link')
    .data(root.links())
    .join('path')
    .attr('class', 'link')
    .attr('fill', 'none')
    .attr('stroke', '#dee2e6')
    .attr('stroke-width', 1.5)
    .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x))

  // Nodes
  const node = g.selectAll('.node')
    .data(root.descendants())
    .join('g')
    .attr('class', 'node')
    .attr('transform', d => `translate(${d.y},${d.x})`)

  node.append('circle')
    .attr('r', d => d.children ? 6 : 4)
    .attr('fill', d => nodeColors[d.data.type] || '#6b7280')
    .attr('stroke', '#fff')
    .attr('stroke-width', 1.5)

  node.append('text')
    .attr('dy', '0.35em')
    .attr('x', d => d.children ? -10 : 10)
    .attr('text-anchor', d => d.children ? 'end' : 'start')
    .attr('font-size', '12px')
    .attr('fill', '#333')
    .text(d => d.data.name.length > 30 ? d.data.name.slice(0, 30) + '...' : d.data.name)

  // Tooltip on hover
  node.append('title')
    .text(d => d.data.name)
}

async function load() {
  loading.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/relations`)
    if (res.ok) {
      relations.value = await res.json()
      await nextTick()
      if (hasData.value) {
        const treeData = transformToTree(relations.value)
        renderTree(treeData)
      }
    }
  } finally {
    loading.value = false
  }
}

async function switchToKnowledge() {
  activeTab.value = 'knowledge'
  if (!kgData.value) {
    await loadKnowledgeGraph()
  }
}

async function loadKnowledgeGraph() {
  kgLoading.value = true
  try {
    const res = await fetch(`/api/v1/projects/${novelId}/knowledge-graph/visualization`)
    if (res.ok) {
      kgData.value = await res.json()
      await nextTick()
      if (kgHasData.value) {
        renderKnowledgeGraph(kgData.value)
      }
    }
  } finally {
    kgLoading.value = false
  }
}

function renderKnowledgeGraph(data) {
  const container = kgContainer.value
  if (!container) return
  container.innerHTML = ''

  const width = Math.max(container.clientWidth, 800)
  const height = 600

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)

  const simulation = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.edges).id(d => d.id).distance(120))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))

  // Edges
  const link = svg.append('g')
    .selectAll('line')
    .data(data.edges)
    .join('line')
    .attr('stroke', '#dee2e6')
    .attr('stroke-width', 1.5)

  // Edge labels
  const linkLabel = svg.append('g')
    .selectAll('text')
    .data(data.edges)
    .join('text')
    .attr('font-size', '10px')
    .attr('fill', '#6b7280')
    .attr('text-anchor', 'middle')
    .text(d => d.predicate)

  // Nodes
  const node = svg.append('g')
    .selectAll('g')
    .data(data.nodes)
    .join('g')
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null })
    )

  node.append('circle')
    .attr('r', 8)
    .attr('fill', d => kgTypeColors[d.type] || '#6b7280')
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  node.append('text')
    .attr('dx', 12)
    .attr('dy', '0.35em')
    .attr('font-size', '12px')
    .attr('fill', '#333')
    .text(d => d.name.length > 15 ? d.name.slice(0, 15) + '...' : d.name)

  node.append('title')
    .text(d => `${d.name} (${d.type})`)

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
    linkLabel
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2)
    node.attr('transform', d => `translate(${d.x},${d.y})`)
  })
}

onMounted(load)
</script>
