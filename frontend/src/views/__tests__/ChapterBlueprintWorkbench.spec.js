import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ChapterBlueprintWorkbench from '../ChapterBlueprintWorkbench.vue'

const NOVEL_ID = '7'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/novels/:id/blueprints', name: 'blueprints', component: ChapterBlueprintWorkbench },
      { path: '/novels/:id', name: 'novel-detail', component: { template: '<div/>' } },
    ],
  })
}

function makeFetch(routes = []) {
  return vi.fn(async (url, opts = {}) => {
    const method = (opts.method || 'GET').toUpperCase()
    for (const route of routes) {
      const matched = typeof route.match === 'string' ? url === route.match : route.match.test(url)
      if (matched && (!route.method || route.method === method)) {
        const body = route.body ?? {}
        return { ok: route.ok ?? true, status: route.status ?? 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
    }
    return { ok: false, status: 404, json: async () => ({ detail: 'nf' }), text: async () => '' }
  })
}

beforeEach(() => {
  vi.stubGlobal('localStorage', {
    getItem: () => null,
    removeItem: () => {},
  })
})

describe('ChapterBlueprintWorkbench', () => {
  it('挂载后加载列表与选项', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'not_generated', has_blueprint: false }], total: 1, page: 1, page_size: 50, status_counts: { not_generated: 1 } } },
    ]))
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()
    expect(wrapper.find('[data-chapter-list]').exists()).toBe(true)
    expect(wrapper.find('[data-status="not_generated"]').text()).toContain('未生成')
  })

  it('选择章节后加载结构化表单', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'draft', has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { chapter_type: 'main_advance', plot_goal: 'x', foreshadow_actions: [], key_characters: [], word_target: 3000, pacing_target: 'medium' }, control: { version: 1, locked: false, control_status: 'draft' }, available_characters: [], versions: [], outline: null, previous_state_delta: null, chapter_summary: null, quality_status: null } },
    ]))
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-field-chapter_type]').exists()).toBe(true)
  })

  it('未保存修改时切章提示', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'draft', has_blueprint: true }, { chapter_number: 2, control_status: 'draft', has_blueprint: true }], total: 2, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { chapter_type: 'main_advance', plot_goal: 'x', foreshadow_actions: [], key_characters: [], word_target: 3000, pacing_target: 'medium' }, control: { version: 1, locked: false, control_status: 'draft' }, available_characters: [], versions: [], outline: null, previous_state_delta: null, chapter_summary: null, quality_status: null } },
    ]))
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    // 触发编辑使 dirty
    await wrapper.find('[data-field-plot_goal]').setValue('改了')
    await wrapper.find('[data-field-plot_goal]').trigger('input')
    await flushPromises()
    // 切到第二章
    await wrapper.findAll('[data-chapter-list] li')[1].trigger('click')
    expect(wrapper.text()).toContain('有未保存修改')
  })
})
