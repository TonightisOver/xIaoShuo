import { describe, it, expect, vi, beforeEach } from 'vitest'
import { forceSimulation } from 'd3-force'

// Build a chainable mock for d3-force simulation
const simProto = {
  force: vi.fn().mockReturnThis(),
  alphaTarget: vi.fn().mockReturnThis(),
  restart: vi.fn().mockReturnThis(),
  stop: vi.fn(),
  on: vi.fn(),
}

vi.mock('d3-selection', () => ({
  select: () => {
    const chain = {
      append: () => chain,
      attr: () => chain,
      style: () => chain,
      text: () => chain,
      on: () => chain,
      selectAll: () => ({ data: () => ({ join: () => chain }) }),
      call: () => chain,
    }
    return chain
  },
}))

vi.mock('d3-force', () => ({
  forceSimulation: vi.fn(() => Object.create(simProto)),
  forceLink: vi.fn(() => ({ id: vi.fn().mockReturnThis(), distance: vi.fn().mockReturnThis() })),
  forceManyBody: vi.fn(() => ({ strength: vi.fn().mockReturnThis() })),
  forceCenter: vi.fn(),
  forceCollide: vi.fn(() => ({ radius: vi.fn().mockReturnThis() })),
}))

vi.mock('d3-drag', () => {
  function createDrag() {
    const fn = function () { return fn }
    fn.on = vi.fn().mockReturnValue(fn)
    return fn
  }
  return { drag: vi.fn(createDrag) }
})

beforeEach(() => {
  simProto.stop.mockClear()
  forceSimulation.mockClear()
})

describe('useKnowledgeGraph simulation cleanup', () => {
  it('stops the previous simulation before re-rendering', async () => {
    // Use a minimal container stub with ref-like interface
    const container = { clientWidth: 800, innerHTML: '' }

    // Import after mocks are installed
    const { useKnowledgeGraph } = await import('../composables/useKnowledgeGraph.js')
    const { renderKnowledgeGraph } = useKnowledgeGraph('n1', container, 'character')

    // First render: no prior sim exists, stop should NOT be called
    renderKnowledgeGraph({
      nodes: [{ id: 'a' }, { id: 'b' }],
      edges: [],
    })
    expect(simProto.stop).not.toHaveBeenCalled()
    expect(forceSimulation).toHaveBeenCalledTimes(1)

    // Second render: the prior sim should be stopped before re-creating
    renderKnowledgeGraph({
      nodes: [{ id: 'c' }, { id: 'd' }],
      edges: [],
    })
    expect(simProto.stop).toHaveBeenCalledTimes(1)
    expect(forceSimulation).toHaveBeenCalledTimes(2)
  })
})
