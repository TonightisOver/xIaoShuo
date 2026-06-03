import { ref, nextTick, toValue, onUnmounted } from 'vue'
import { hierarchy, tree } from 'd3-hierarchy'
import { select } from 'd3-selection'
import { linkHorizontal } from 'd3-shape'

const nodeColors = {
  root: '#8b5cf6',
  category: '#1d1d1f',
  storyline: '#3b82f6',
  character: '#10b981',
  arc: '#8b5cf6',
  scene: '#f59e0b',
  event: '#8e8e93',
  stage: '#a78bfa',
}

export function useRelationGraph(novelId, treeContainer) {
  const relations = ref(null)
  const loading = ref(true)
  let controller = null

  onUnmounted(() => controller?.abort())

  function transformToTree(data) {
    const children = []

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
    const container = typeof treeContainer === 'object' && 'value' in treeContainer
      ? treeContainer.value
      : treeContainer
    if (!container) return

    container.innerHTML = ''

    const margin = { top: 20, right: 200, bottom: 20, left: 120 }
    const width = Math.max(container.clientWidth, 800)

    const root = hierarchy(data)
    const treeHeight = Math.max(root.descendants().length * 28, 450)

    const treeLayout = tree().size([treeHeight, width - margin.left - margin.right])
    treeLayout(root)

    const svg = select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', treeHeight + margin.top + margin.bottom)

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`)

    g.selectAll('.link')
      .data(root.links())
      .join('path')
      .attr('class', 'link')
      .attr('fill', 'none')
      .attr('stroke', '#e5e5ea')
      .attr('stroke-width', 1.5)
      .attr('d', linkHorizontal().x(d => d.y).y(d => d.x))

    const node = g.selectAll('.node')
      .data(root.descendants())
      .join('g')
      .attr('class', 'node')
      .attr('transform', d => `translate(${d.y},${d.x})`)

    node.append('circle')
      .attr('r', d => d.children ? 6 : 4)
      .attr('fill', d => nodeColors[d.data.type] || '#8e8e93')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 1.5)
      .style('filter', 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))')

    node.append('text')
      .attr('dy', '0.35em')
      .attr('x', d => d.children ? -10 : 10)
      .attr('text-anchor', d => d.children ? 'end' : 'start')
      .attr('font-size', '11px')
      .attr('font-weight', '500')
      .attr('fill', '#1d1d1f')
      .text(d => d.data.name.length > 30 ? d.data.name.slice(0, 30) + '...' : d.data.name)
      .style('text-shadow', '0 1px 2px #ffffff, 0 0 4px #ffffff')

    node.append('title')
      .text(d => d.data.name)
  }

  async function load() {
    controller?.abort()
    controller = new AbortController()
    loading.value = true
    try {
      const res = await fetch(`/api/v1/projects/${toValue(novelId)}/relations`, { signal: controller.signal })
      if (res.ok) {
        relations.value = await res.json()
        await nextTick()
        const hasData = relations.value &&
          (relations.value.storylines.length || relations.value.character_arcs.length || relations.value.scenes.length)
        if (hasData) {
          const treeData = transformToTree(relations.value)
          renderTree(treeData)
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') return
    } finally {
      if (!controller.signal.aborted) loading.value = false
    }
  }

  return {
    relations,
    loading,
    load,
    renderTree,
    transformToTree,
  }
}
