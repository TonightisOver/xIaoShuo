import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import GenerationScopeSelector from '../GenerationScopeSelector.vue'

function makeFetch(routes = []) {
  return vi.fn(async (url, _opts = {}) => {
    for (const route of routes) {
      const matched = typeof route.match === 'string' ? url === route.match : route.match.test(url)
      if (matched) {
        const body = route.body ?? {}
        return {
          ok: route.ok ?? true,
          status: route.status ?? 200,
          json: async () => body,
          text: async () => JSON.stringify(body),
        }
      }
    }
    return { ok: true, status: 200, json: async () => ({}), text: async () => '{}' }
  })
}

function mountSelector(props = {}) {
  return mount(GenerationScopeSelector, {
    props: { novelId: 'novel-1', ...props },
  })
}

describe('GenerationScopeSelector.vue', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: () => 'tok',
      removeItem: () => {},
    })
  })

  it('selecting mode=volume shows volume_number input', async () => {
    const wrapper = mountSelector()
    const select = wrapper.find('[data-mode-select]')
    await select.setValue('volume')
    expect(wrapper.find('[data-input="volume_number"]').exists()).toBe(true)
  })

  it('clicking preview fetches and shows estimated_chapters', async () => {
    const fetchMock = makeFetch([
      {
        match: /generate-scope\/preview/,
        body: {
          estimated_chapters: 4,
          estimated_tokens: 12000,
          target_chapters: 4,
          skipped_locked: 0,
          skipped_confirmed: 0,
          impact: { upstream: [], direct_downstream: [], full_downstream: [], regenerable: [], to_mark_stale: [] },
        },
      },
    ])
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mountSelector()
    await wrapper.find('[data-mode-select]').setValue('volume')
    await wrapper.find('[data-input="volume_number"]').setValue(2)
    await wrapper.find('[data-preview-btn]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('4 章')
    expect(fetchMock).toHaveBeenCalled()
    const calledUrl = fetchMock.mock.calls[0][0]
    expect(calledUrl).toContain('generate-scope/preview')
  })

  it('emits plan with mode+volume_number', async () => {
    const wrapper = mountSelector()
    await wrapper.find('[data-mode-select]').setValue('volume')
    await wrapper.find('[data-input="volume_number"]').setValue(3)
    await wrapper.find('[data-plan-btn]').trigger('click')
    expect(wrapper.emitted('plan')).toBeTruthy()
    const payload = wrapper.emitted('plan')[0][0]
    expect(payload.mode).toBe('volume')
    expect(payload.volume_number).toBe(3)
  })
})
