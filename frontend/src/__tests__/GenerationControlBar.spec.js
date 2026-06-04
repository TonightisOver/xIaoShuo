import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import GenerationControlBar from '../components/GenerationControlBar.vue'

let wrapper

function mountBar(props = {}) {
  wrapper = mount(GenerationControlBar, {
    props: {
      isPaused: false,
      isStreaming: true,
      currentChapter: 1,
      totalChapters: 3,
      wordCount: 1200,
      ...props,
    },
  })
  return wrapper
}

function stopButton(wrapper) {
  return wrapper.find('button[title="Esc"]')
}

describe('GenerationControlBar.vue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    document.body.innerHTML = ''
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.clearAllTimers()
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('shows confirmation without emitting stop on first click', async () => {
    const wrapper = mountBar()

    await stopButton(wrapper).trigger('click')

    expect(wrapper.emitted('stop')).toBeUndefined()
    expect(document.body.textContent).toContain('确定停止生成？')
    expect(document.body.textContent).toContain('未保存进度将丢失')
  })

  it('emits stop when stop is clicked again within two seconds', async () => {
    const wrapper = mountBar()

    await stopButton(wrapper).trigger('click')
    await stopButton(wrapper).trigger('click')

    expect(wrapper.emitted('stop')).toHaveLength(1)
    expect(document.body.textContent).not.toContain('确定停止生成？')
  })

  it('emits stop from the confirmation button', async () => {
    const wrapper = mountBar()

    await stopButton(wrapper).trigger('click')
    document.body.querySelectorAll('button')[1].click()
    await nextTick()

    expect(wrapper.emitted('stop')).toHaveLength(1)
  })

  it('expires confirmation after two seconds', async () => {
    const wrapper = mountBar()

    await stopButton(wrapper).trigger('click')
    vi.advanceTimersByTime(2000)
    await nextTick()
    await stopButton(wrapper).trigger('click')

    expect(wrapper.emitted('stop')).toBeUndefined()
    expect(document.body.textContent).toContain('确定停止生成？')
  })

  it('closes confirmation with Escape', async () => {
    const wrapper = mountBar()

    await stopButton(wrapper).trigger('click')
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await nextTick()

    expect(wrapper.emitted('stop')).toBeUndefined()
    expect(document.body.textContent).not.toContain('确定停止生成？')
  })
})
