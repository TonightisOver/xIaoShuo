import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Landing from '../Landing.vue'

const CHARS = ['落', '笔', '生', '花']

function makeCharData(char) {
  return {
    strokes: [`M 10 10 L 20 20 Z ${char}`, `M 30 30 L 40 40 Z ${char}`],
    medians: [
      [[10, 10], [20, 20]],
      [[30, 30], [40, 40]],
    ],
  }
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/welcome', component: Landing },
      { path: '/login', component: { template: '<div />' } },
      { path: '/', component: { template: '<div />' } },
      { path: '/create', component: { template: '<div />' } },
    ],
  })
}

async function mountLanding() {
  const router = makeRouter()
  await router.push('/welcome')
  await router.isReady()
  const wrapper = mount(Landing, { global: { plugins: [router] } })
  await flushPromises()
  vi.advanceTimersByTime(300)
  await flushPromises()
  return wrapper
}

describe('Landing.vue hero brush writing', () => {
  let rafCallbacks
  let storage

  beforeEach(() => {
    vi.useFakeTimers()
    storage = new Map()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key) => storage.get(key) ?? null),
      setItem: vi.fn((key, value) => storage.set(key, String(value))),
      removeItem: vi.fn((key) => storage.delete(key)),
      clear: vi.fn(() => storage.clear()),
    })
    rafCallbacks = []
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback) => {
      rafCallbacks.push(callback)
      return rafCallbacks.length
    }))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    vi.stubGlobal('IntersectionObserver', class {
      observe() {}
      disconnect() {}
    })
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      scale: vi.fn(),
      save: vi.fn(),
      setTransform: vi.fn(),
      fillRect: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
    })
    Object.defineProperty(SVGElement.prototype, 'getTotalLength', {
      configurable: true,
      value: vi.fn(() => 100),
    })
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      const filename = decodeURIComponent(String(url).split('/').pop())
      const char = filename.replace('.json', '')
      return { ok: true, json: async () => makeCharData(char) }
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    vi.useRealTimers()
    delete SVGElement.prototype.getTotalLength
  })

  it('uses the authoritative stroke outlines in character and stroke order', async () => {
    const wrapper = await mountLanding()
    const strokes = wrapper.findAll('.ink-stroke')

    expect(strokes).toHaveLength(CHARS.length * 2)
    expect(strokes.map((stroke) => stroke.attributes('data-stroke-key'))).toEqual([
      '0-0', '0-1', '1-0', '1-1', '2-0', '2-1', '3-0', '3-1',
    ])
    expect(strokes.map((stroke) => stroke.attributes('d'))).toEqual(
      CHARS.flatMap((char) => makeCharData(char).strokes),
    )
    expect(wrapper.findAll('.stroke-reveal').slice(0, 2).map((path) => path.attributes('d'))).toEqual([
      'M10 10 L20 20',
      'M30 30 L40 40',
    ])
    expect(wrapper.find('.glyph text').exists()).toBe(false)

    wrapper.unmount()
  })

  it('reveals one stroke completely before starting the next stroke', async () => {
    const wrapper = await mountLanding()
    const reveals = wrapper.findAll('.stroke-reveal')

    expect(reveals[0].element.style.strokeDashoffset).toBe('100')
    expect(reveals[1].element.style.strokeDashoffset).toBe('100')

    rafCallbacks.at(-1)(0)
    rafCallbacks.at(-1)(300)
    expect(reveals[0].element.style.strokeDashoffset).toBe('0')
    expect(reveals[1].element.style.strokeDashoffset).toBe('100')

    vi.advanceTimersByTime(180)
    rafCallbacks.at(-1)(500)
    rafCallbacks.at(-1)(800)
    expect(reveals[1].element.style.strokeDashoffset).toBe('0')

    wrapper.unmount()
  })

  it('connects signed-in visitors to the existing home and create views', async () => {
    storage.set('session_token', 'valid-session')
    const wrapper = await mountLanding()
    const links = wrapper.findAll('a')
    const linkByText = (text) => links.find((link) => link.text().includes(text))

    expect(linkByText('进入书房').attributes('href')).toBe('/')
    expect(linkByText('开始创作').attributes('href')).toBe('/create')
    expect(linkByText('执笔入局').attributes('href')).toBe('/create')

    wrapper.unmount()
  })
})
