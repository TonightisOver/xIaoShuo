import { ref, nextTick } from 'vue'
import * as d3 from 'd3'

export function useKnowledgeGraph(novelId, kgContainer, activeSubLayer) {
  const kgData = ref(null)
  const kgLoading = ref(false)
  const extracting = ref(false)
  const extractProgress = ref('')
  const generatingStorylines = ref(false)
  const storylineGenError = ref('')

  function _id() { return typeof novelId === 'object' ? novelId.value : novelId }

  function getActiveGraphData() {
    if (!kgData.value) return null
    const layer = typeof activeSubLayer === 'object' ? activeSubLayer.value : activeSubLayer
    if (layer === 'character') return kgData.value.character_graph
    if (layer === 'plot') return kgData.value.plot_graph
    if (layer === 'foreshadowing') return kgData.value.foreshadowing_graph
    return null
  }

  async function loadThreeLayerGraph(showAll) {
    kgLoading.value = true
    try {
      const minFreq = showAll ? 1 : 2
      const res = await fetch(`/api/v1/projects/${_id()}/knowledge-graph/three-layer?min_frequency=${minFreq}`)
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

  async function reExtractKG(loadRelationsFn) {
    if (extracting.value) return
    extracting.value = true
    extractProgress.value = '正在读取章节文本并清除旧数据...'
    try {
      const res = await fetch(`/api/v1/projects/${_id()}/knowledge-graph/extract-all`, {
        method: 'POST'
      })
      if (res.ok) {
        const data = await res.json()
        extractProgress.value = `抽取成功！共重新测绘 ${data.total_entities} 个实体，${data.total_triples} 组三元组。`
        await loadThreeLayerGraph(false)
      } else {
        const err = await res.json().catch(() => ({}))
        extractProgress.value = `提取异常：${err.detail || '服务错误'}`
      }
    } catch (err) {
      console.error(err)
      extractProgress.value = '提取网络通信异常，请重试'
    } finally {
      setTimeout(() => {
        extracting.value = false
        extractProgress.value = ''
      }, 4500)
    }
  }

  async function generateStorylines(loadFn) {
    if (generatingStorylines.value) return
    generatingStorylines.value = true
    storylineGenError.value = ''
    try {
      const res = await fetch(`/api/v1/projects/${_id()}/storylines/generate-ai`, { method: 'POST' })
      if (res.ok) {
        if (loadFn) await loadFn()
      } else {
        const err = await res.json().catch(() => ({}))
        storylineGenError.value = err.detail || '生成失败，请重试'
      }
    } catch (e) {
      storylineGenError.value = '网络错误，请重试'
    } finally {
      generatingStorylines.value = false
    }
  }

  function renderKnowledgeGraph(data) {
    const container = typeof kgContainer === 'object' && 'value' in kgContainer
      ? kgContainer.value
      : kgContainer
    if (!container) return
    container.innerHTML = ''

    const width = Math.max(container.clientWidth, 800)
    const height = 600

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .style('border-radius', '12px')

    const layer = typeof activeSubLayer === 'object' ? activeSubLayer.value : activeSubLayer
    let themeColor = '#8b5cf6'
    if (layer === 'character') themeColor = '#3b82f6'
    else if (layer === 'plot') themeColor = '#f59e0b'

    svg.append('defs').append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 22)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#8e8e93')

    const nodes = data.nodes.map(d => ({ ...d }))
    const edges = data.edges.map(d => ({ ...d }))

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id(d => d.id).distance(150))
      .force('charge', d3.forceManyBody().strength(-450))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(28))

    const link = svg.append('g')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', d => {
        if (d.type === 'narrative_flow') return 'rgba(245, 158, 11, 0.4)'
        return 'rgba(0, 0, 0, 0.08)'
      })
      .attr('stroke-width', d => d.type === 'narrative_flow' ? 1.5 : 2)
      .attr('stroke-dasharray', d => d.type === 'narrative_flow' ? '5,5' : '0')
      .attr('marker-end', 'url(#arrow)')

    const linkLabel = svg.append('g')
      .selectAll('text')
      .data(edges)
      .join('text')
      .attr('font-size', '9px')
      .attr('font-weight', '500')
      .attr('fill', '#636366')
      .attr('text-anchor', 'middle')
      .attr('dy', -4)
      .text(d => d.predicate)
      .style('text-shadow', '0 1px 2px #ffffff, 0 0 4px #ffffff')

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

    node.append('circle')
      .attr('r', 11)
      .attr('fill', d => {
        if (d.type === 'foreshadowing') return '#a78bfa'
        if (d.type === 'event') return '#f59e0b'
        return '#3b82f6'
      })
      .style('filter', `drop-shadow(0px 2px 5px ${themeColor})`)
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2)

    node.append('circle')
      .attr('r', 3)
      .attr('fill', '#ffffff')

    node.append('text')
      .attr('dx', 16)
      .attr('dy', '0.35em')
      .attr('font-size', '12px')
      .attr('font-weight', '700')
      .attr('fill', '#1c1c1e')
      .text(d => d.name)
      .style('text-shadow', '0 1px 2px #ffffff, 0 0 4px #ffffff')

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
          const rotation = (angle > 90 || angle < -90) ? angle + 180 : angle
          return `rotate(${rotation}, ${x}, ${y})`
        })

      node.attr('transform', d => {
        d.x = Math.max(20, Math.min(width - 20, d.x))
        d.y = Math.max(20, Math.min(height - 20, d.y))
        return `translate(${d.x},${d.y})`
      })
    })
  }

  return {
    kgData,
    kgLoading,
    extracting,
    extractProgress,
    generatingStorylines,
    storylineGenError,
    loadThreeLayerGraph,
    reExtractKG,
    generateStorylines,
    renderKnowledgeGraph,
    getActiveGraphData,
  }
}
