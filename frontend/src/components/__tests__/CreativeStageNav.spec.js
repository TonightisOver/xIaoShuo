import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CreativeStageNav from '../CreativeStageNav.vue'

const STAGES = [
  { number: 1, name: '创意拓展', artifact_type: 'idea', control: { control_status: 'approved' } },
  { number: 2, name: '世界观', artifact_type: 'world', control: { control_status: 'generated' } },
  { number: 3, name: '人设', artifact_type: 'character', control: { control_status: 'locked' } },
  { number: 4, name: '大纲', artifact_type: 'outline', control: { control_status: 'stale' } },
  { number: 5, name: '章节', artifact_type: 'chapter', control: { control_status: 'failed' } },
  { number: 6, name: '质检', artifact_type: 'quality', control: { control_status: 'generating' } },
  { number: 7, name: '审核', artifact_type: 'review', control: null },
  { number: 8, name: '力量体系', artifact_type: 'power', control: { control_status: 'approved' } },
  { number: 9, name: '入库', artifact_type: 'persist', control: { control_status: 'approved' } },
  { number: 10, name: '图谱', artifact_type: 'graph', control: { control_status: 'approved' } },
]

function mountNav(props = {}) {
  return mount(CreativeStageNav, {
    props: { stages: STAGES, creativeStage: 6, ...props },
  })
}

describe('CreativeStageNav.vue', () => {
  it('renders 10 stages', () => {
    const wrapper = mountNav()
    const items = wrapper.findAll('[data-stage-item]')
    expect(items.length).toBe(10)
  })

  it('maps control_status to correct color classes', () => {
    const wrapper = mountNav()
    const items = wrapper.findAll('[data-stage-item]')
    // stage 1 approved -> green
    expect(items[0].classes().some(c => c.includes('green') || c.includes('emerald'))).toBe(true)
    // stage 2 generated -> gray
    expect(items[1].classes().some(c => c.includes('gray') || c.includes('ink'))).toBe(true)
    // stage 3 locked -> deep green
    expect(items[2].classes().some(c => c.includes('emerald') || c.includes('green'))).toBe(true)
    // stage 4 stale -> yellow
    expect(items[3].classes().some(c => c.includes('yellow') || c.includes('amber'))).toBe(true)
    // stage 5 failed -> red
    expect(items[4].classes().some(c => c.includes('red') || c.includes('rose'))).toBe(true)
    // stage 6 generating -> blue
    expect(items[5].classes().some(c => c.includes('blue') || c.includes('sky'))).toBe(true)
  })

  it('emits select with stage number when clicked', async () => {
    const wrapper = mountNav()
    const items = wrapper.findAll('[data-stage-item]')
    await items[2].trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')[0][0]).toBe(3)
  })
})
