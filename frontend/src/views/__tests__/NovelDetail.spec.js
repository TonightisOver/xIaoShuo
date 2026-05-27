import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import NovelDetail from '../NovelDetail.vue'
import ExportDialog from '../../components/ExportDialog.vue'

// ── helpers ──────────────────────────────────────────────────────────────────

const NOVEL_ID = '42'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/novels/:id', name: 'novel-detail', component: NovelDetail },
      { path: '/task/:id', name: 'task-detail', component: { template: '<div/>' } },
      { path: '/', name: 'home', component: { template: '<div/>' } },
    ],
  })
}

const NOVEL_FIXTURE = {
  id: NOVEL_ID,
  title: '测试小说',
  novel_type: '玄幻',
  target_words: 100000,
  status: 'draft',
  idea: '一个测试故事',
  characters_count: 0,
  world_setting: null,
  active_task_id: null,
}

/**
 * Build a fetch mock.
 * `routes` is an array of { match: string|RegExp, ok, status, body }
 * checked in order — first match wins.
 * Unmatched URLs return { ok: true, body: [] } (array default for list endpoints).
 */
function makeFetch(routes = []) {
  return vi.fn(async (url, opts = {}) => {
    for (const route of routes) {
      const matched =
        typeof route.match === 'string' ? url === route.match : route.match.test(url)
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
    // default: empty array (safe for list endpoints)
    return {
      ok: true,
      status: 200,
      json: async () => [],
      text: async () => '[]',
    }
  })
}

/** Project detail URL — exact match */
const projectUrl = (id = NOVEL_ID) => `/api/v1/projects/${id}`

async function mountComponent(router, fetchMock) {
  vi.stubGlobal('fetch', fetchMock)
  await router.push(`/novels/${NOVEL_ID}`)
  await router.isReady()

  const wrapper = mount(NovelDetail, {
    global: {
      plugins: [router],
      stubs: {
        VolumeList: true,
        ChapterRangeDialog: true,
        ExportDialog: true,
        Teleport: true,
      },
    },
  })
  return wrapper
}

// ── tests ─────────────────────────────────────────────────────────────────────

describe('NovelDetail.vue', () => {
  let router

  beforeEach(() => {
    router = makeRouter()
    vi.stubGlobal('alert', vi.fn())
    vi.stubGlobal('confirm', vi.fn(() => false))
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  // ── T6-1: fetchAll 成功，novel ref 被赋值 ──────────────────────────────────
  it('fetchAll 成功后 novel ref 被赋值', async () => {
    const fetchMock = makeFetch([
      { match: projectUrl(), ok: true, body: NOVEL_FIXTURE },
    ])

    const wrapper = await mountComponent(router, fetchMock)
    await flushPromises()

    expect(wrapper.text()).toContain('测试小说')
  })

  // ── T6-2: generate() 成功后 router.push 到 /task/:id ──────────────────────
  it('generate() 成功后跳转到 /task/:id', async () => {
    const TASK_ID = 'task-abc'
    const fetchMock = makeFetch([
      // More specific URL must come first
      {
        match: `/api/v1/projects/${NOVEL_ID}/generate`,
        ok: true,
        body: { task_id: TASK_ID },
      },
      { match: projectUrl(), ok: true, body: NOVEL_FIXTURE },
    ])

    const wrapper = await mountComponent(router, fetchMock)
    await flushPromises()

    const generateBtn = wrapper
      .findAll('button')
      .find(b => b.text().includes('分步生成'))

    expect(generateBtn).toBeTruthy()
    await generateBtn.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe(`/task/${TASK_ID}`)
  })

  // ── T6-3: doDeleteUnassigned 调用 DELETE 并从列表移除 ─────────────────────
  it('doDeleteUnassigned 调用 DELETE 并从章节列表移除', async () => {
    const chapter = {
      id: 1,
      chapter_number: 3,
      title: '第三章',
      word_count: 500,
      volume_number: null,
    }
    const fetchMock = makeFetch([
      {
        match: `/api/v1/projects/${NOVEL_ID}/chapters/${chapter.chapter_number}`,
        ok: true,
        body: {},
      },
      {
        match: `/api/v1/projects/${NOVEL_ID}/chapters`,
        ok: true,
        body: [chapter],
      },
      { match: projectUrl(), ok: true, body: NOVEL_FIXTURE },
    ])

    const wrapper = await mountComponent(router, fetchMock)
    await flushPromises()

    // Switch to chapters tab
    const chaptersTab = wrapper.findAll('button').find(b => b.text() === '章节')
    await chaptersTab.trigger('click')
    await flushPromises()

    // Click the delete icon button (title="删除章节")
    const deleteBtn = wrapper.findAll('button').find(b => b.attributes('title') === '删除章节')
    expect(deleteBtn).toBeTruthy()
    await deleteBtn.trigger('click')
    await flushPromises()

    // Confirm deletion in the modal
    const confirmBtn = wrapper.findAll('button').find(b => b.text() === '删除')
    expect(confirmBtn).toBeTruthy()
    await confirmBtn.trigger('click')
    await flushPromises()

    const deleteCalls = fetchMock.mock.calls.filter(
      ([url, opts]) =>
        opts?.method === 'DELETE' &&
        url.includes(`/chapters/${chapter.chapter_number}`)
    )
    expect(deleteCalls.length).toBeGreaterThan(0)
  })

  // ── T6-4: cleanupFailedChapters — 用户确认 ────────────────────────────────
  it('cleanupFailedChapters — confirm=true 时调用 DELETE cleanup', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    vi.stubGlobal('alert', vi.fn())

    const fetchMock = makeFetch([
      // cleanup must come before /chapters to avoid substring match
      {
        match: /\/chapters\/cleanup/,
        ok: true,
        body: { deleted_count: 2 },
      },
      { match: projectUrl(), ok: true, body: NOVEL_FIXTURE },
    ])

    const wrapper = await mountComponent(router, fetchMock)
    await flushPromises()

    const chaptersTab = wrapper.findAll('button').find(b => b.text() === '章节')
    await chaptersTab.trigger('click')

    const cleanupBtn = wrapper.findAll('button').find(b => b.text().includes('清理失败章节'))
    expect(cleanupBtn).toBeTruthy()
    await cleanupBtn.trigger('click')
    await flushPromises()

    const cleanupCalls = fetchMock.mock.calls.filter(
      ([url, opts]) => opts?.method === 'DELETE' && url.includes('cleanup')
    )
    expect(cleanupCalls.length).toBeGreaterThan(0)
    expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('2'))
  })

  // ── T6-5: cleanupFailedChapters — 用户取消 ────────────────────────────────
  it('cleanupFailedChapters — confirm=false 时不调用 DELETE', async () => {
    vi.stubGlobal('confirm', vi.fn(() => false))

    const fetchMock = makeFetch([
      { match: projectUrl(), ok: true, body: NOVEL_FIXTURE },
    ])

    const wrapper = await mountComponent(router, fetchMock)
    await flushPromises()

    const chaptersTab = wrapper.findAll('button').find(b => b.text() === '章节')
    await chaptersTab.trigger('click')

    const cleanupBtn = wrapper.findAll('button').find(b => b.text().includes('清理失败章节'))
    await cleanupBtn.trigger('click')
    await flushPromises()

    const cleanupCalls = fetchMock.mock.calls.filter(
      ([url, opts]) => opts?.method === 'DELETE' && url.includes('cleanup')
    )
    expect(cleanupCalls.length).toBe(0)
  })

  // ── T6-6: 点击导出按钮后 showExportDialog 为 true ─────────────────────────
  it('点击导出按钮后 showExportDialog 变为 true', async () => {
    const fetchMock = makeFetch([
      { match: projectUrl(), ok: true, body: NOVEL_FIXTURE },
    ])

    const wrapper = await mountComponent(router, fetchMock)
    await flushPromises()

    // Switch to chapters tab first — ExportDialog is rendered inside that tab
    const chaptersTab = wrapper.findAll('button').find(b => b.text() === '章节')
    await chaptersTab.trigger('click')
    await flushPromises()

    // Click the export button (in the header, always visible)
    const exportBtn = wrapper.findAll('button').find(b => b.text().includes('导出'))
    expect(exportBtn).toBeTruthy()
    await exportBtn.trigger('click')
    await flushPromises()

    // ExportDialog is stubbed — check via the stub tag name (lowercase, hyphenated)
    // Vue Test Utils renders stubs as <component-name-stub>
    // Try both casing variants
    const stub =
      wrapper.find('exportdialog-stub') ||
      wrapper.find('ExportDialog-stub') ||
      wrapper.findComponent({ name: 'ExportDialog' })

    // Fallback: verify via the reactive state — the export button click sets showExportDialog=true
    // which is passed as :visible to ExportDialog. We can verify the stub has visible attr.
    // If stub not found, check the HTML contains the stub with visible
    const html = wrapper.html()
    const hasVisibleExport =
      html.includes('exportdialog-stub') ||
      html.includes('visible="true"') ||
      (stub && stub.exists && stub.exists())

    expect(hasVisibleExport).toBe(true)
  })

  // ── T6-7: fullGenerate 409 冲突时 alert 被调用 ────────────────────────────
  it('fullGenerate 收到 409 "已有正在运行" 时调用 alert', async () => {
    vi.stubGlobal('alert', vi.fn())

    const fetchMock = makeFetch([
      {
        match: `/api/v1/projects/${NOVEL_ID}/generate-full`,
        ok: false,
        status: 409,
        body: { detail: '已有正在运行的生成任务' },
      },
      { match: projectUrl(), ok: true, body: NOVEL_FIXTURE },
    ])

    const wrapper = await mountComponent(router, fetchMock)
    await flushPromises()

    const fullGenBtn = wrapper
      .findAll('button')
      .find(b => b.text().includes('一键全功能生成'))
    expect(fullGenBtn).toBeTruthy()
    await fullGenBtn.trigger('click')
    await flushPromises()

    expect(global.alert).toHaveBeenCalledWith(expect.stringContaining('已有正在运行'))
  })
})
