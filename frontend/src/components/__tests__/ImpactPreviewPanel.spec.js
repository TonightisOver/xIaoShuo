import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ImpactPreviewPanel from '../ImpactPreviewPanel.vue'

const IMPACT = {
  upstream: ['outline'],
  direct_downstream: ['character', 'power'],
  full_downstream: ['character', 'power', 'chapter'],
  regenerable: ['character', 'power'],
  to_mark_stale: ['chapter'],
}

function mountPanel(props = {}) {
  return mount(ImpactPreviewPanel, {
    props: { impact: IMPACT, ...props },
  })
}

describe('ImpactPreviewPanel.vue', () => {
  it('renders 4 columns', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('[data-col="direct_downstream"]').text()).toContain('character')
    expect(wrapper.find('[data-col="full_downstream"]').text()).toContain('chapter')
    expect(wrapper.find('[data-col="regenerable"]').text()).toContain('character')
    expect(wrapper.find('[data-col="to_mark_stale"]').text()).toContain('chapter')
  })

  it('renders 4 radio options', () => {
    const wrapper = mountPanel()
    const radios = wrapper.findAll('[data-choice]')
    expect(radios.length).toBe(4)
    const values = radios.map(r => r.attributes('data-choice'))
    expect(values).toEqual(
      expect.arrayContaining(['save_only', 'regen_direct', 'regen_all', 'mark_stale']),
    )
  })

  it('selecting save_only emits choice=save_only', async () => {
    const wrapper = mountPanel()
    const radio = wrapper.find('[data-choice="save_only"]')
    await radio.trigger('change')
    expect(wrapper.emitted('choice')).toBeTruthy()
    expect(wrapper.emitted('choice')[0][0]).toBe('save_only')
  })
})
