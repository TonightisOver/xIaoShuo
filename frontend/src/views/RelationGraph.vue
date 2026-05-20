<template>
  <div class="max-w-full mx-auto px-6 py-10">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <h1 class="text-2xl font-extrabold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">全景故事与知识图谱</h1>
        <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">双引擎</span>
      </div>
      <router-link :to="`/novels/${novelId}`" class="btn-secondary text-sm glass-panel hover:bg-white/10 transition-all px-4 py-2 rounded-lg border border-white/10 text-ink-300">返回小说详情</router-link>
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-2 mb-6 border-b border-white/10">
      <button
        class="px-5 py-3 text-sm font-semibold transition-all relative"
        :class="activeTab === 'structure' ? 'text-blue-400 font-bold border-b-2 border-blue-400' : 'text-ink-400 hover:text-ink-300'"
        @click="activeTab = 'structure'"
      >
        🎨 故事框架拓扑
      </button>
      <button
        class="px-5 py-3 text-sm font-semibold transition-all relative"
        :class="activeTab === 'knowledge' ? 'text-purple-400 font-bold border-b-2 border-purple-400' : 'text-ink-400 hover:text-ink-300'"
        @click="switchToKnowledge"
      >
        🧠 活态三层图谱
      </button>
    </div>

    <!-- 故事结构 Tab -->
    <div v-show="activeTab === 'structure'" class="space-y-4">
      <div v-if="loading" class="flex flex-col items-center justify-center py-28 space-y-4">
        <div class="w-12 h-12 rounded-full border-4 border-blue-500/30 border-t-blue-400 animate-spin"></div>
        <p class="text-ink-400 text-sm">正在测绘小说故事框架，请稍候...</p>
      </div>
      <div v-else-if="!hasData" class="glass-panel text-center py-20 rounded-2xl border border-white/5 bg-white/2 backdrop-blur-md">
        <p class="text-ink-400 mb-4">暂无预设框架，请先去添加故事线、人物弧光或场景情节</p>
        <router-link :to="`/novels/${novelId}`" class="btn-primary text-sm px-6 py-2.5 rounded-lg">前往添加</router-link>
      </div>

      <div v-else class="glass-panel p-6 rounded-2xl border border-white/5 bg-white/2 backdrop-blur-md overflow-x-auto shadow-2xl relative">
        <div ref="treeContainer" class="min-h-[550px] w-full"></div>
      </div>

      <!-- Legend -->
      <div v-if="hasData" class="flex flex-wrap gap-4 px-4 py-3 rounded-xl bg-white/5 border border-white/5 text-xs text-ink-400">
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-blue-500/80 shadow-[0_0_8px_#3b82f6]"></span> 故事主线</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-emerald-500/80 shadow-[0_0_8px_#10b981]"></span> 角色卡</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-purple-500/80 shadow-[0_0_8px_#8b5cf6]"></span> 人物弧光</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-amber-500/80 shadow-[0_0_8px_#f59e0b]"></span> 剧情场景</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-slate-500/80"></span> 情节事件</span>
      </div>
    </div>

    <!-- 活态知识图谱 Tab -->
    <div v-show="activeTab === 'knowledge'" class="space-y-4">
      <!-- 三层子 Tab 控制 -->
      <div class="flex items-center justify-between p-1.5 rounded-xl bg-white/5 border border-white/5 max-w-xl">
        <button
          v-for="sub in subLayers"
          :key="sub.id"
          class="flex-1 py-2 px-3 text-xs font-semibold rounded-lg transition-all"
          :class="activeSubLayer === sub.id 
            ? `${sub.activeBg} text-white shadow-lg` 
            : 'text-ink-400 hover:text-ink-300'"
          @click="changeSubLayer(sub.id)"
        >
          {{ sub.icon }} {{ sub.name }}
        </button>
      </div>

      <div v-if="kgLoading" class="flex flex-col items-center justify-center py-28 space-y-4">
        <div class="w-12 h-12 rounded-full border-4 border-purple-500/30 border-t-purple-400 animate-spin"></div>
        <p class="text-ink-400 text-sm">正在抽取并编译三层网络图谱中...</p>
      </div>
      <div v-else-if="!kgHasData" class="glass-panel text-center py-20 rounded-2xl border border-white/5 bg-white/2 backdrop-blur-md">
        <p class="text-ink-400">章节内容尚未产生或尚未触发抽取。请在章节生成完成后重新查看！</p>
      </div>

      <div v-else class="glass-panel p-4 rounded-2xl border border-white/5 bg-[#0d0f14]/80 backdrop-blur-xl overflow-x-auto shadow-2xl relative">
        <!-- 图谱画布 -->
        <div ref="kgContainer" class="min-h-[600px] w-full rounded-xl overflow-hidden bg-radial-glow"></div>
      </div>

      <!-- KG Legends based on active sub tab -->
      <div v-if="kgHasData" class="flex flex-wrap gap-4 px-4 py-3 rounded-xl bg-white/5 border border-white/5 text-xs text-ink-400">
        <template v-if="activeSubLayer === 'character'">
          <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full" style="background:#3b82f6; box-shadow: 0 0 8px #3b82f6"></span> 角色实体</span>
          <span class="flex items-center gap-1.5"><span class="w-3.5 h-0.5 bg-blue-400/80"></span> 人际关系网络</span>
        </template>
        <template v-else-if="activeSubLayer === 'plot'">
          <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full" style="background:#f59e0b; box-shadow: 0 0 8px #f59e0b"></span> 剧情事件</span>
          <span class="flex items-center gap-1.5"><span class="w-3.5 h-0.5 bg-amber-400/80"></span> 显式事件关联</span>
          <span class="flex items-center gap-1.5"><span class="w-3.5 h-0.5 border-t border-dashed border-amber-500/50"></span> 时序推进流 (Chapter Axis)</span>
        </template>
        <template v-else-if="activeSubLayer === 'foreshadowing'">
          <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full" style="background:#a78bfa; box-shadow: 0 0 8px #a78bfa"></span> 伏笔节点 (已埋/未收)</span>
          <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-full" style="background:#3b82f6"></span> 关联人物/事件</span>
          <span class="flex items-center gap-1.5"><span class="w-3.5 h-0.5 bg-purple-400/80"></span> 埋藏/回收生命线</span>
        </template>
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

// Three-layer knowledge graph state
const kgLoading = ref(false)
const kgData = ref(null) // holds { character_graph, plot_graph, foreshadowing_graph }
const kgContainer = ref(null)
const activeSubLayer = ref('character')

const subLayers = [
  { id: 'character', name: '角色关系谱', icon: '👥', activeBg: 'bg-blue-600' },
  { id: 'plot', name: '剧情事件谱', icon: '⏳', activeBg: 'bg-amber-600' },
  { id: 'foreshadowing', name: '伏笔填坑谱', icon: '🔮', activeBg: 'bg-purple-600' }
]

const hasData = computed(() => {
  if (!relations.value) return false
  const r = relations.value
  return r.storylines.length || r.character_arcs.length || r.scenes.length
})

const kgHasData = computed(() => {
  if (!kgData.value) return false
  const activeGraph = getActiveGraphData()
  return activeGraph && activeGraph.nodes && activeGraph.nodes.length > 0
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

function getActiveGraphData() {
  if (!kgData.value) return null
  if (activeSubLayer.value === 'character') return kgData.value.character_graph
  if (activeSubLayer.value === 'plot') return kgData.value.plot_graph
  if (activeSubLayer.value === 'foreshadowing') return kgData.value.foreshadowing_graph
  return null
}

function changeSubLayer(layerId) {
  activeSubLayer.value = layerId
  nextTick(() => {
    const data = getActiveGraphData()
    if (data) {
      renderKnowledgeGraph(data)
    }
  })
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
      const links = data.storyline_character_links.filter(l => l.storyline_id === sl.id)
      links.forEach(l => {
        slNode.children.push({ name: `人物#${l.character_id} (${l.role_in_line || '参与'})`, type: 'character' })
      })
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
    children.push({ name: '故事主线', type: 'category', children: slChildren })
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
    children.push({ name: '人物成长弧光', type: 'category', children: arcChildren })
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
    children.push({ name: '剧情场景', type: 'category', children: sceneChildren })
  }

  return { name: '小说核心大纲架构', type: 'root', children }
}

function renderTree(data) {
  const container = treeContainer.value
  if (!container) return

  container.innerHTML = ''

  const margin = { top: 20, right: 200, bottom: 20, left: 100 }
  const width = Math.max(container.clientWidth, 800)

  const root = d3.hierarchy(data)
  const treeHeight = Math.max(root.descendants().length * 25, 450)

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
    .attr('stroke', 'rgba(255, 255, 255, 0.12)')
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
    .attr('stroke', 'rgba(13, 15, 20, 0.8)')
    .attr('stroke-width', 1.5)

  node.append('text')
    .attr('dy', '0.35em')
    .attr('x', d => d.children ? -10 : 10)
    .attr('text-anchor', d => d.children ? 'end' : 'start')
    .attr('font-size', '12px')
    .attr('fill', '#c3c7d6')
    .text(d => d.data.name.length > 30 ? d.data.name.slice(0, 30) + '...' : d.data.name)

  // Tooltip
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
    await loadThreeLayerGraph()
  }
}

async function loadThreeLayerGraph() {
  kgLoading.value = true
  try {
    // 拉取最新的三层关系图谱
    const res = await fetch(`/api/v1/projects/${novelId}/knowledge-graph/three-layer`)
    if (res.ok) {
      kgData.value = await res.json()
      await nextTick()
      const currentGraph = getActiveGraphData()
      if (currentGraph) {
        renderKnowledgeGraph(currentGraph)
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
    .style('border-radius', '12px')

  // Theme customization colors based on active tab
  let themeColor = '#a78bfa' // Default purple
  let nodeGlowColor = 'rgba(167, 139, 250, 0.4)'
  if (activeSubLayer.value === 'character') {
    themeColor = '#3b82f6'
    nodeGlowColor = 'rgba(59, 130, 246, 0.4)'
  } else if (activeSubLayer.value === 'plot') {
    themeColor = '#f59e0b'
    nodeGlowColor = 'rgba(245, 158, 11, 0.4)'
  }

  // 1. Defined Arrow Markers for Link Directions
  svg.append('defs').append('marker')
    .attr('id', 'arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 22) // node radius (10) + arrow offset
    .attr('refY', 0)
    .attr('markerWidth', 5)
    .attr('markerHeight', 5)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-5L10,0L0,5')
    .attr('fill', '#4b5563')

  // Deep clone data to avoid simulation mutating state
  const nodes = data.nodes.map(d => ({ ...d }))
  const edges = data.edges.map(d => ({ ...d }))

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(140))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(25))

  // 2. Render Lines
  const link = svg.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', d => {
      if (d.type === 'narrative_flow') return 'rgba(245, 158, 11, 0.25)' // dashed temporal flow
      return 'rgba(255, 255, 255, 0.15)'
    })
    .attr('stroke-width', d => d.type === 'narrative_flow' ? 1.5 : 2)
    .attr('stroke-dasharray', d => d.type === 'narrative_flow' ? '5,5' : '0')
    .attr('marker-end', 'url(#arrow)')

  // 3. Render Link labels
  const linkLabel = svg.append('g')
    .selectAll('text')
    .data(edges)
    .join('text')
    .attr('font-size', '9px')
    .attr('fill', '#9ca3af')
    .attr('text-anchor', 'middle')
    .attr('dy', -4)
    .text(d => d.predicate)

  // 4. Render Nodes
  const node = svg.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .style('cursor', 'grab')
    .call(d3.drag()
      .on('start', (event, d) => { 
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y 
      })
      .on('drag', (event, d) => { 
        d.fx = event.x
        d.fy = event.y 
      })
      .on('end', (event, d) => { 
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null 
      })
    )

  // Glowing Outer Halo for nodes
  node.append('circle')
    .attr('r', 12)
    .attr('fill', d => {
      if (d.type === 'foreshadowing') return '#a78bfa'
      if (d.type === 'event') return '#f59e0b'
      return '#3b82f6'
    })
    .style('filter', `drop-shadow(0px 0px 8px ${themeColor})`)
    .attr('stroke', 'rgba(255, 255, 255, 0.35)')
    .attr('stroke-width', 1.5)

  node.append('circle')
    .attr('r', 4)
    .attr('fill', '#ffffff')

  // Text labels with drop shadow for premium legibility
  node.append('text')
    .attr('dx', 16)
    .attr('dy', '0.35em')
    .attr('font-size', '12px')
    .attr('font-weight', 'bold')
    .attr('fill', '#e5e7eb')
    .text(d => d.name)
    .style('text-shadow', '0 2px 4px rgba(0, 0, 0, 0.8)')

  node.append('title')
    .text(d => {
      let desc = `${d.name} (${d.type === 'character' ? '人物' : d.type === 'event' ? '事件' : '伏笔'})`
      if (d.attributes && Object.keys(d.attributes).length) {
        desc += `\n属性: ${JSON.stringify(d.attributes, null, 2)}`
      }
      return desc
    })

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
    
    linkLabel
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2)
      .attr('transform', d => {
        const x = (d.source.x + d.target.x) / 2
        const y = (d.source.y + d.target.y) / 2
        const dx = d.target.x - d.source.x
        const dy = d.target.y - d.source.y
        const angle = Math.atan2(dy, dx) * 180 / Math.PI
        // Make text readable upright
        const rotation = (angle > 90 || angle < -90) ? angle + 180 : angle
        return `rotate(${rotation}, ${x}, ${y})`
      })

    node.attr('transform', d => {
      // Bounding box constraint to keep nodes in canvas
      d.x = Math.max(20, Math.min(width - 20, d.x))
      d.y = Math.max(20, Math.min(height - 20, d.y))
      return `translate(${d.x},${d.y})`
    })
  })
}

onMounted(load)
</script>

<style scoped>
.glass-panel {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.bg-radial-glow {
  background: radial-gradient(circle at center, rgba(17, 24, 39, 0.95) 0%, rgba(3, 7, 18, 1) 100%);
  position: relative;
}
.bg-radial-glow::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.06) 0%, transparent 60%);
  pointer-events: none;
}
</style>
