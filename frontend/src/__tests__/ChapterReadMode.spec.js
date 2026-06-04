import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ChapterReadMode from '../components/ChapterReadMode.vue'

const progressApi = vi.hoisted(() => ({
  saveProgress: vi.fn(),
  loadProgress: vi.fn(),
  dispose: vi.fn(),
}))

vi.mock('../composables/useReadingProgress.js', () => ({
  useReadingProgress: () => progressApi,
}))

const baseChapter = {
  id: 1,
  chapter_number: 1,
  title: 'Chapter 1',
  novel_id: 'novel-1',
  novel: { id: 'novel-1', title: 'Novel' },
}

function mountReader(props = {}) {
  return mount(ChapterReadMode, {
    props: {
      chapter: baseChapter,
      content: 'content',
      prevChapter: null,
      nextChapter: null,
      chapters: [],
      novelId: 'novel-1',
      activeTheme: 'white',
      activeFont: 'sans',
      fontSize: 18,
      showSettings: false,
      ...props,
    },
    global: {
      stubs: { ReadingTOC: true },
    },
  })
}

function setScrollMetrics(el, scrollHeight = 1000, clientHeight = 200) {
  Object.defineProperty(el, 'scrollHeight', { configurable: true, value: scrollHeight })
  Object.defineProperty(el, 'clientHeight', { configurable: true, value: clientHeight })
}

describe('ChapterReadMode.vue', () => {
  beforeEach(() => {
    progressApi.saveProgress.mockClear()
    progressApi.loadProgress.mockReset()
    progressApi.dispose.mockClear()
    progressApi.loadProgress.mockReturnValue(null)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('resets scrollTop when chapter_number changes without matching progress', async () => {
    const wrapper = mountReader()
    const el = wrapper.element
    setScrollMetrics(el)
    el.scrollTop = 400

    await wrapper.setProps({
      chapter: { ...baseChapter, id: 2, chapter_number: 2, title: 'Chapter 2' },
    })
    await nextTick()

    expect(el.scrollTop).toBe(0)
  })

  it('restores saved scroll progress when switching back to a matching chapter', async () => {
    progressApi.loadProgress.mockReturnValue({
      chapter: 3,
      scrollPercent: 25,
      timestamp: '2026-06-04T00:00:00.000Z',
    })

    const wrapper = mountReader()
    const el = wrapper.element
    setScrollMetrics(el)
    el.scrollTop = 500

    await wrapper.setProps({
      chapter: { ...baseChapter, id: 3, chapter_number: 3, title: 'Chapter 3' },
    })
    await nextTick()
    await nextTick()

    expect(el.scrollTop).toBe(200)
  })
})
