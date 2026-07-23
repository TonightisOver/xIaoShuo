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

  it('批量控制携带每章当前控制版本', async () => {
    const fetchMock = makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: [], pacing_target: [], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'generated', control_version: 5, has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/creative-control\/batch$/, method: 'POST', body: { action: 'lock', results: [{ chapter_number: 1, status: 'ok', version: 6 }] } },
    ])
    vi.stubGlobal('fetch', fetchMock)
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-batch-checkbox="1"]').trigger('click')
    await wrapper.get('[data-batch-lock]').trigger('click')
    await flushPromises()

    const request = fetchMock.mock.calls.find(([url, opts = {}]) =>
      url.endsWith('/creative-control/batch') && opts.method === 'POST'
    )
    expect(JSON.parse(request[1].body).expected_versions).toEqual({ 1: 5 })
  })

  it('批量操作后保留当前筛选条件', async () => {
    const fetchMock = makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: [], pacing_target: [], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 20, control_status: 'generated', control_version: 1, has_blueprint: true, title: '第二十章' }], total: 1, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/creative-control\/batch$/, method: 'POST', body: { action: 'approve', results: [{ chapter_number: 20, status: 'ok', version: 2 }] } },
    ])
    vi.stubGlobal('fetch', fetchMock)
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('input[placeholder="搜索章号/标题"]').setValue('20')
    await wrapper.findAll('button').find(button => button.text() === '筛选').trigger('click')
    await flushPromises()
    await wrapper.get('[data-batch-checkbox="20"]').trigger('click')
    await wrapper.get('[data-batch-confirm]').trigger('click')
    await flushPromises()

    const listRequests = fetchMock.mock.calls.filter(([url]) => url.includes('/blueprints?'))
    expect(listRequests.at(-1)[0]).toContain('search=20')
  })

  it('连续批量操作使用上一操作返回的新版本', async () => {
    let batchCall = 0
    const fetchMock = vi.fn(async (url, opts = {}) => {
      if (url.endsWith('/blueprints/options')) {
        return { ok: true, status: 200, json: async () => ({ chapter_type: [], pacing_target: [], foreshadow_action: [] }), text: async () => '{}' }
      }
      if (url.includes('/blueprints?')) {
        const body = { items: [{ chapter_number: 1, control_status: 'generated', control_version: 5, has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} }
        return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
      if (url.endsWith('/creative-control/batch')) {
        batchCall += 1
        const body = { action: batchCall === 1 ? 'approve' : 'lock', results: [{ chapter_number: 1, status: 'ok', version: batchCall === 1 ? 6 : 7 }] }
        return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
      return { ok: false, status: 404, json: async () => ({}), text: async () => '' }
    })
    vi.stubGlobal('fetch', fetchMock)
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-batch-checkbox="1"]').trigger('click')
    await wrapper.get('[data-batch-confirm]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-batch-lock]').trigger('click')
    await flushPromises()

    const requests = fetchMock.mock.calls.filter(([url, opts = {}]) =>
      url.endsWith('/creative-control/batch') && opts.method === 'POST'
    )
    expect(JSON.parse(requests[1][1].body).expected_versions).toEqual({ 1: 6 })
  })

  it('批量冲突后使用服务端当前版本重试', async () => {
    let batchCall = 0
    const fetchMock = vi.fn(async (url, opts = {}) => {
      if (url.endsWith('/blueprints/options')) {
        return { ok: true, status: 200, json: async () => ({ chapter_type: [], pacing_target: [], foreshadow_action: [] }), text: async () => '{}' }
      }
      if (url.includes('/blueprints?')) {
        const body = { items: [{ chapter_number: 1, control_status: 'generated', control_version: 5, has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} }
        return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
      if (url.endsWith('/creative-control/batch')) {
        batchCall += 1
        const body = batchCall === 1
          ? { action: 'approve', results: [{ chapter_number: 1, status: 'conflict', current_version: 6 }] }
          : { action: 'approve', results: [{ chapter_number: 1, status: 'ok', version: 7 }] }
        return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
      return { ok: false, status: 404, json: async () => ({}), text: async () => '' }
    })
    vi.stubGlobal('fetch', fetchMock)
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-batch-checkbox="1"]').trigger('click')
    await wrapper.get('[data-batch-confirm]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-batch-confirm]').trigger('click')
    await flushPromises()

    const requests = fetchMock.mock.calls.filter(([url, opts = {}]) =>
      url.endsWith('/creative-control/batch') && opts.method === 'POST'
    )
    expect(JSON.parse(requests[1][1].body).expected_versions).toEqual({ 1: 6 })
  })

  it('批量操作进行中忽略重复点击', async () => {
    let resolveBatch
    const pendingBatch = new Promise(resolve => { resolveBatch = resolve })
    const fetchMock = vi.fn(async (url, opts = {}) => {
      if (url.endsWith('/blueprints/options')) {
        return { ok: true, status: 200, json: async () => ({ chapter_type: [], pacing_target: [], foreshadow_action: [] }), text: async () => '{}' }
      }
      if (url.includes('/blueprints?')) {
        const body = { items: [{ chapter_number: 1, control_status: 'generated', control_version: 5, has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} }
        return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
      if (url.endsWith('/creative-control/batch')) {
        await pendingBatch
        const body = { action: 'approve', results: [{ chapter_number: 1, status: 'ok', version: 6 }] }
        return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
      return { ok: false, status: 404, json: async () => ({}), text: async () => '' }
    })
    vi.stubGlobal('fetch', fetchMock)
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-batch-checkbox="1"]').trigger('click')
    const firstClick = wrapper.get('[data-batch-confirm]').trigger('click')
    const secondClick = wrapper.get('[data-batch-confirm]').trigger('click')
    await Promise.resolve()

    const pendingRequests = fetchMock.mock.calls.filter(([url, opts = {}]) =>
      url.endsWith('/creative-control/batch') && opts.method === 'POST'
    )
    expect(pendingRequests).toHaveLength(1)
    resolveBatch()
    await Promise.all([firstClick, secondClick])
    await flushPromises()
  })

  it('批量操作后同步当前章节控制状态', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: [], pacing_target: [], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'generated', control_version: 5, has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { plot_goal: '一' }, control: { version: 5, control_status: 'generated', locked: false }, available_characters: [] } },
      { match: /\/creative-control\/batch$/, method: 'POST', body: { action: 'approve', results: [{ chapter_number: 1, status: 'ok', version: 6 }] } },
    ]))
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    await wrapper.get('[data-field-plot_goal]').setValue('未保存修改')
    await wrapper.get('[data-batch-checkbox="1"]').trigger('click')
    await wrapper.get('[data-batch-confirm]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('版本 6')
    expect(wrapper.text()).toContain('approved')
    expect(wrapper.get('[data-field-plot_goal]').element.value).toBe('未保存修改')
  })

  it('当前章节批量冲突时不提升带草稿的工作区版本', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: [], pacing_target: [], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'generated', control_version: 5, has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { plot_goal: '一' }, control: { version: 5, control_status: 'generated', locked: false }, available_characters: [] } },
      { match: /\/creative-control\/batch$/, method: 'POST', body: { action: 'approve', results: [{ chapter_number: 1, status: 'conflict', current_version: 6 }] } },
    ]))
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    await wrapper.get('[data-field-plot_goal]').setValue('未保存修改')
    await wrapper.get('[data-batch-checkbox="1"]').trigger('click')
    await wrapper.get('[data-batch-confirm]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('版本 5')
    expect(wrapper.get('[data-field-plot_goal]').element.value).toBe('未保存修改')
  })

  it('切换章节时清除上一章影响预览', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: [], pacing_target: [], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'generated', has_blueprint: true }, { chapter_number: 2, control_status: 'generated', has_blueprint: true }], total: 2, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { plot_goal: '一' }, control: { version: 1, control_status: 'generated' }, available_characters: [] } },
      { match: /\/blueprints\/2\/workspace$/, body: { blueprint: { plot_goal: '二' }, control: { version: 1, control_status: 'generated' }, available_characters: [] } },
      { match: /\/artifacts\/blueprint\/1\/impact$/, body: { direct_downstream: ['chapter/1'], full_downstream: [], regenerable: [], to_mark_stale: [] } },
    ]))
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '预览影响').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-impact-preview-panel]').exists()).toBe(true)
    await wrapper.findAll('[data-chapter-list] li')[1].trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-impact-preview-panel]').exists()).toBe(false)
  })

  it('版本比较使用后端差异结论处理数组字段', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: [], pacing_target: [], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'generated', has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { plot_goal: '一' }, control: { version: 2, control_status: 'generated' }, available_characters: [] } },
      { match: /\/artifacts\/blueprint\/1\/versions$/, body: [{ version_number: 3, source: 'manual', is_active: false }, { version_number: 2, source: 'rollback', is_active: true }, { version_number: 1, source: 'generation', is_active: false }] },
      { match: /\/versions\/compare\?a=2&b=1$/, body: { changed: [], unchanged: ['key_characters'], a: { content_snapshot: { key_characters: ['主角'] } }, b: { content_snapshot: { key_characters: ['主角'] } } } },
    ]))
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '版本历史').trigger('click')
    await flushPromises()
    await wrapper.findAll('button').filter(button => button.text() === '对比')[2].trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-compare-table]').text()).toContain('否')
  })

  it('跨分页选择时保留每章的乐观锁版本', async () => {
    const fetchMock = vi.fn(async (url, opts = {}) => {
      if (url.endsWith('/blueprints/options')) {
        return { ok: true, status: 200, json: async () => ({ chapter_type: [], pacing_target: [], foreshadow_action: [] }), text: async () => '{}' }
      }
      if (url.includes('/blueprints?')) {
        const requestedPage = new URL(url, 'http://local').searchParams.get('page')
        const item = requestedPage === '2'
          ? { chapter_number: 2, control_status: 'generated', control_version: 7, has_blueprint: true }
          : { chapter_number: 1, control_status: 'generated', control_version: 5, has_blueprint: true }
        const body = { items: [item], total: 2, page: Number(requestedPage), page_size: 1, status_counts: {} }
        return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
      if (url.endsWith('/creative-control/batch')) {
        const body = { action: 'lock', results: [] }
        return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
      return { ok: false, status: 404, json: async () => ({}), text: async () => '' }
    })
    vi.stubGlobal('fetch', fetchMock)
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-batch-checkbox="1"]').trigger('click')
    await wrapper.findAll('button').find(button => button.text() === '下一页').trigger('click')
    await flushPromises()
    await wrapper.get('[data-batch-checkbox="2"]').trigger('click')
    await wrapper.get('[data-batch-lock]').trigger('click')
    await flushPromises()

    const request = fetchMock.mock.calls.find(([url, opts = {}]) =>
      url.endsWith('/creative-control/batch') && opts.method === 'POST'
    )
    expect(JSON.parse(request[1].body).expected_versions).toEqual({ 1: 5, 2: 7 })
  })

  it('切章后忽略上一章迟到的影响响应', async () => {
    let resolveImpact
    const delayedImpact = new Promise(resolve => { resolveImpact = resolve })
    const fetchMock = makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: [], pacing_target: [], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'generated', has_blueprint: true }, { chapter_number: 2, control_status: 'generated', has_blueprint: true }], total: 2, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { plot_goal: '一' }, control: { version: 1 }, available_characters: [] } },
      { match: /\/blueprints\/2\/workspace$/, body: { blueprint: { plot_goal: '二' }, control: { version: 1 }, available_characters: [] } },
    ])
    fetchMock.mockImplementationOnce(fetchMock.getMockImplementation())
    vi.stubGlobal('fetch', vi.fn(async (url, opts) => {
      if (url.endsWith('/artifacts/blueprint/1/impact')) {
        await delayedImpact
        const body = { direct_downstream: ['chapter/1'], full_downstream: [], regenerable: [], to_mark_stale: [] }
        return { ok: true, status: 200, text: async () => JSON.stringify(body), json: async () => body }
      }
      return fetchMock(url, opts)
    }))
    const router = makeRouter()
    await router.push(`/novels/${NOVEL_ID}/blueprints`)
    await router.isReady()
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    const impactRequest = wrapper.findAll('button').find(button => button.text() === '预览影响').trigger('click')
    await wrapper.findAll('[data-chapter-list] li')[1].trigger('click')
    await flushPromises()
    resolveImpact()
    await impactRequest
    await flushPromises()

    expect(wrapper.find('[data-impact-preview-panel]').exists()).toBe(false)
  })
})
