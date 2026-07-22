import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import CreativeStudio from '../CreativeStudio.vue'

const NOVEL_ID = '42'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/novels/:id', name: 'novel-detail', component: { template: '<div/>' } },
      { path: '/novels/:id/studio', name: 'studio', component: CreativeStudio },
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
        return {
          ok: route.ok ?? true,
          status: route.status ?? 200,
          json: async () => body,
          text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
        }
      }
    }
    return { ok: true, status: 200, json: async () => ({}), text: async () => '{}' }
  })
}

async function mountStudio(fetchMock) {
  const router = makeRouter()
  vi.stubGlobal('fetch', fetchMock)
  await router.push(`/novels/${NOVEL_ID}/studio`)
  await router.isReady()
  const wrapper = mount(CreativeStudio, {
    global: {
      plugins: [router],
      stubs: { Teleport: true },
    },
  })
  await flushPromises()
  return wrapper
}

describe('CreativeStudio.vue', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', { getItem: () => 'tok', removeItem: () => {} })
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('loads novel + stage nav (10 stages) on mount', async () => {
    const fetchMock = makeFetch([
      { match: `/api/v1/novels/${NOVEL_ID}`, body: { id: NOVEL_ID, title: '测试小说' } },
      {
        match: /creative-control\/stage$/,
        body: {
          creation_mode: 'manual',
          creative_stage: 1,
          stages: Array.from({ length: 10 }, (_, i) => ({
            number: i + 1,
            name: `阶段${i + 1}`,
            artifact_type: 'world',
            control: { control_status: 'generated', version: 1 },
          })),
        },
      },
      { match: /artifacts\/world\/42$/, body: { control: { control_status: 'generated', version: 1 }, versions: [] } },
      { match: /operations/, body: [] },
    ])
    const wrapper = await mountStudio(fetchMock)
    expect(wrapper.text()).toContain('测试小说')
    expect(wrapper.findAll('[data-stage-item]')).toHaveLength(10)
    expect(wrapper.find('[data-mode-select]').element.value).toBe('manual')
  })

  it('shows conflict hint on 409 stale_version when editing', async () => {
    const fetchMock = makeFetch([
      { match: `/api/v1/novels/${NOVEL_ID}`, body: { id: NOVEL_ID, title: '冲突小说' } },
      {
        match: /creative-control\/stage$/,
        body: {
          creation_mode: 'auto', creative_stage: 1,
          stages: [{ number: 1, name: '世界观', artifact_type: 'world', control: null }],
        },
      },
      { match: /artifacts\/world\/42$/, method: 'GET', body: { control: { control_status: 'generated', version: 2 }, versions: [] } },
      { match: /operations/, body: [] },
      {
        match: /artifacts\/world\/42$/,
        method: 'PUT',
        ok: false, status: 409,
        body: { code: 'stale_version', message: '版本已变化', current_version: 5 },
      },
    ])
    const wrapper = await mountStudio(fetchMock)
    // 选中阶段1
    await wrapper.find('[data-stage-item]').trigger('click')
    await flushPromises()
    // 点保存编辑
    await wrapper.find('[data-action="edit"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-conflict-hint]').text()).toContain('版本已变化')
    expect(wrapper.find('[data-conflict-hint]').text()).toContain('5')
  })

  it('editing chapter (正文) sends plain text, not JSON-parsed', async () => {
    const fetchMock = makeFetch([
      { match: `/api/v1/novels/${NOVEL_ID}`, body: { id: NOVEL_ID, title: '正文小说' } },
      {
        match: /creative-control\/stage$/,
        body: {
          creation_mode: 'manual', creative_stage: 7,
          stages: [{ number: 7, name: '章节正文', artifact_type: 'chapter', control: { control_status: 'generated', version: 3 } }],
        },
      },
      { match: /artifacts\/chapter\/42$/, method: 'GET', body: { control: { control_status: 'generated', version: 3 }, versions: [] } },
      { match: /operations/, body: [] },
      { match: /artifacts\/chapter\/42$/, method: 'PUT', body: { status: 'edited', version: 5 } },
    ])
    const wrapper = await mountStudio(fetchMock)
    await wrapper.find('[data-stage-item]').trigger('click')
    await flushPromises()
    // 正文纯文本恰好是合法 JSON（纯数字），不能被 JSON.parse 误解析
    await wrapper.find('[data-artifact-editor]').setValue('42')
    await wrapper.find('[data-action="edit"]').trigger('click')
    await flushPromises()
    const putCall = fetchMock.mock.calls.find(
      c => /artifacts\/chapter\/42$/.test(c[0]) && (c[1]?.method || '').toUpperCase() === 'PUT',
    )
    expect(putCall).toBeTruthy()
    const sent = JSON.parse(putCall[1].body)
    // 正文应作为字符串发送，而非被解析成数字 42
    expect(sent.content).toBe('42')
    expect(typeof sent.content).toBe('string')
  })

  it('clicking regenerate triggers regenerate endpoint', async () => {
    const fetchMock = makeFetch([
      { match: `/api/v1/novels/${NOVEL_ID}`, body: { id: NOVEL_ID, title: '重生成小说' } },
      {
        match: /creative-control\/stage$/,
        body: {
          creation_mode: 'auto', creative_stage: 1,
          stages: [{ number: 1, name: '世界观', artifact_type: 'world', control: null }],
        },
      },
      { match: /artifacts\/world\/42$/, body: { control: { control_status: 'generated', version: 1, locked: false }, versions: [] } },
      { match: /operations/, body: [] },
      { match: /regenerate$/, body: { status: 'generating', version: 2 } },
    ])
    const wrapper = await mountStudio(fetchMock)
    await wrapper.find('[data-stage-item]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-action="regenerate"]').trigger('click')
    await flushPromises()
    const regenCall = fetchMock.mock.calls.find(c => /regenerate$/.test(c[0]))
    expect(regenCall).toBeTruthy()
    expect(regenCall[1].method).toBe('POST')
  })

  it('loads and edits the selected real artifact id and content', async () => {
    const fetchMock = makeFetch([
      { match: `/api/v1/novels/${NOVEL_ID}`, body: { id: NOVEL_ID, title: '多角色小说' } },
      {
        match: /creative-control\/stage$/,
        body: {
          creation_mode: 'manual', creative_stage: 2,
          stages: [{
            number: 2,
            name: '角色',
            artifact_type: 'character',
            artifacts: [{ artifact_id: 'character-7', label: '主角' }],
            control: { control_status: 'generated', version: 4 },
          }],
        },
      },
      {
        match: /artifacts\/character\/character-7$/,
        method: 'GET',
        body: {
          artifact_id: 'character-7',
          content: { name: '林川' },
          control: { control_status: 'generated', version: 4 },
          versions: [],
        },
      },
      { match: /operations/, body: [] },
      {
        match: /artifacts\/character\/character-7$/,
        method: 'PUT',
        body: { status: 'edited', version: 5 },
      },
    ])
    const wrapper = await mountStudio(fetchMock)

    expect(wrapper.find('[data-artifact-editor]').element.value).toContain('林川')
    await wrapper.find('[data-action="edit"]').trigger('click')
    await flushPromises()

    const putCall = fetchMock.mock.calls.find(
      call => /artifacts\/character\/character-7$/.test(call[0]) && call[1]?.method === 'PUT',
    )
    expect(putCall).toBeTruthy()
  })

  it('can select a different artifact instance in the same stage', async () => {
    const fetchMock = makeFetch([
      { match: `/api/v1/novels/${NOVEL_ID}`, body: { id: NOVEL_ID, title: '群像小说' } },
      {
        match: /creative-control\/stage$/,
        body: {
          creation_mode: 'manual', creative_stage: 2,
          stages: [{
            number: 2, name: '角色', artifact_type: 'character',
            artifacts: [
              { artifact_id: '7', label: '林川' },
              { artifact_id: '8', label: '苏白' },
            ],
          }],
        },
      },
      { match: /artifacts\/character\/7$/, body: { content: { name: '林川' }, control: { version: 1 }, versions: [] } },
      { match: /artifacts\/character\/8$/, body: { content: { name: '苏白' }, control: { version: 1 }, versions: [] } },
      { match: /operations/, body: [] },
    ])
    const wrapper = await mountStudio(fetchMock)

    await wrapper.find('[data-artifact-select]').setValue('8')
    await flushPromises()

    expect(wrapper.find('[data-artifact-editor]').element.value).toContain('苏白')
    expect(fetchMock.mock.calls.some(call => /artifacts\/character\/8$/.test(call[0]))).toBe(true)
  })

  it('executes mark-stale impact choice instead of ignoring it', async () => {
    const fetchMock = makeFetch([
      { match: `/api/v1/novels/${NOVEL_ID}`, body: { id: NOVEL_ID, title: '影响测试' } },
      {
        match: /creative-control\/stage$/,
        body: {
          creation_mode: 'manual', creative_stage: 1,
          stages: [{ number: 1, name: '世界观', artifact_type: 'world', artifacts: [{ artifact_id: '42', label: '世界观' }] }],
        },
      },
      { match: /artifacts\/world\/42$/, method: 'GET', body: { content: { rules: '旧' }, control: { version: 2 }, versions: [] } },
      { match: /artifacts\/world\/42\/impact$/, body: { direct_downstream: [], full_downstream: [], regenerable: [], to_mark_stale: [] } },
      { match: /artifacts\/world\/42\/mark-stale$/, method: 'POST', body: { to_mark_stale: [] } },
      { match: /operations/, body: [] },
    ])
    const wrapper = await mountStudio(fetchMock)

    await wrapper.find('[data-load-impact]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-choice="mark_stale"]').trigger('change')
    await flushPromises()

    expect(fetchMock.mock.calls.some(
      call => /artifacts\/world\/42\/mark-stale$/.test(call[0]) && call[1]?.method === 'POST',
    )).toBe(true)
  })
})
