import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBlueprintWorkbench } from '../useBlueprintWorkbench.js'

function makeFetch(routes = []) {
  return vi.fn(async (url, opts = {}) => {
    const method = (opts.method || 'GET').toUpperCase()
    for (const route of routes) {
      const matched = typeof route.match === 'string' ? url === route.match : route.match.test(url)
      if (matched && (!route.method || route.method === method)) {
        const body = route.body ?? {}
        return {
          ok: route.ok ?? true, status: route.status ?? 200,
          json: async () => body,
          text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
        }
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
  vi.stubGlobal('fetch', makeFetch([]))
})

describe('useBlueprintWorkbench', () => {
  it('fetchSummaries 加载列表含未生成章节', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\?/, method: 'GET', body: {
        items: [{ chapter_number: 1, has_blueprint: false, control_status: 'not_generated' }],
        total: 1, page: 1, page_size: 50, status_counts: { not_generated: 1 },
      } },
    ]))
    const wb = useBlueprintWorkbench('novel-1')
    await wb.fetchSummaries({ page: 1 })
    expect(wb.summaries.value.length).toBe(1)
    expect(wb.summaries.value[0].control_status).toBe('not_generated')
  })

  it('快速切章时旧请求不覆盖新选择', async () => {
    let resolveFirst
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (/\/blueprints\/11\/workspace$/.test(url)) {
        // ch11 旧请求挂起，稍后 resolve
        return new Promise(r => {
          resolveFirst = () => r({
            ok: true, status: 200,
            json: async () => ({ blueprint: { chapter_type: 'OLD' } }),
            text: async () => JSON.stringify({ blueprint: { chapter_type: 'OLD' } }),
          })
        })
      }
      return {
        ok: true, status: 200,
        json: async () => ({ blueprint: { chapter_type: 'NEW' } }),
        text: async () => JSON.stringify({ blueprint: { chapter_type: 'NEW' } }),
      }
    }))
    const wb = useBlueprintWorkbench('novel-1')
    const p1 = wb.fetchWorkspace(11)   // 旧请求挂起
    const p2 = wb.fetchWorkspace(12)   // 新请求先返回
    await p2
    expect(wb.workspace.value.blueprint.chapter_type).toBe('NEW')
    resolveFirst()  // 旧请求晚返回
    await p1
    // 旧结果被丢弃，仍为 NEW
    expect(wb.workspace.value.blueprint.chapter_type).toBe('NEW')
  })

  it('batchGenerate 发 blueprint_only + chapter_numbers', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true, status: 202,
      json: async () => ({ accepted: [{ chapter_number: 1, task_id: 't1' }] }),
      text: async () => '',
    }))
    vi.stubGlobal('fetch', fetchMock)
    const wb = useBlueprintWorkbench('novel-1')
    await wb.batchGenerate([1, 2])
    const call = fetchMock.mock.calls[0]
    const body = JSON.parse(call[1].body)
    expect(body.mode).toBe('blueprint_only')
    expect(body.chapter_numbers).toEqual([1, 2])
  })
})
