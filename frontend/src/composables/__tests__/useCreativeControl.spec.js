import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useCreativeControl } from '../useCreativeControl.js'

function makeFetch(routes = []) {
  return vi.fn(async (url, opts = {}) => {
    for (const route of routes) {
      const matched = typeof route.match === 'string' ? url === route.match : route.match.test(url)
      if (matched) {
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

describe('useCreativeControl', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: () => 'tok',
      removeItem: () => {},
    })
  })

  it('getStage fetches /creative-control/stage and returns stages', async () => {
    const fetchMock = makeFetch([
      {
        match: /creative-control\/stage$/,
        body: {
          creation_mode: 'manual',
          creative_stage: 3,
          stages: [{ number: 1, name: '世界观', artifact_type: 'world', control: null }],
        },
      },
    ])
    vi.stubGlobal('fetch', fetchMock)
    const { getStage } = useCreativeControl('novel-1')
    const data = await getStage()
    expect(data.stages).toHaveLength(1)
    expect(data.creation_mode).toBe('manual')
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/projects/novel-1/creative-control/stage')
  })

  it('editArtifact sends PUT with expected_version', async () => {
    const fetchMock = makeFetch([
      { match: /artifacts\/world\/novel-1$/, body: { status: 'edited', version: 3 } },
    ])
    vi.stubGlobal('fetch', fetchMock)
    const { editArtifact } = useCreativeControl('novel-1')
    const res = await editArtifact('world', 'novel-1', { rules: 'x' }, 2)
    expect(res.version).toBe(3)
    const call = fetchMock.mock.calls[0]
    expect(call[1].method).toBe('PUT')
    const body = JSON.parse(call[1].body)
    expect(body.expected_version).toBe(2)
    expect(body.content.rules).toBe('x')
  })

  it('throws error with code+current_version on 409 stale_version', async () => {
    const fetchMock = makeFetch([
      {
        match: /artifacts\/world\/novel-1\/lock$/,
        ok: false,
        status: 409,
        body: { code: 'stale_version', message: '版本已变化', current_version: 5, expected_version: 2 },
      },
    ])
    vi.stubGlobal('fetch', fetchMock)
    const { lock, error } = useCreativeControl('novel-1')
    await expect(lock('world', 'novel-1', 2)).rejects.toThrow()
    expect(error.value).toBeTruthy()
    expect(error.value.code).toBe('stale_version')
    expect(error.value.current_version).toBe(5)
  })

  it('listOperations builds query string from filters', async () => {
    const fetchMock = makeFetch([
      { match: /operations\?action=edit&limit=20/, body: [{ action: 'edit' }] },
    ])
    vi.stubGlobal('fetch', fetchMock)
    const { listOperations } = useCreativeControl('novel-1')
    const res = await listOperations({ action: 'edit', limit: 20 })
    expect(res).toEqual([{ action: 'edit' }])
    expect(fetchMock.mock.calls[0][0]).toContain('action=edit')
    expect(fetchMock.mock.calls[0][0]).toContain('limit=20')
  })

  it('setCreationMode sends PUT /mode', async () => {
    const fetchMock = makeFetch([
      { match: /creative-control\/mode$/, body: { status: 'updated', creation_mode: 'assisted' } },
    ])
    vi.stubGlobal('fetch', fetchMock)
    const { setCreationMode } = useCreativeControl('novel-1')
    const res = await setCreationMode('assisted')
    expect(res.creation_mode).toBe('assisted')
    expect(fetchMock.mock.calls[0][1].method).toBe('PUT')
  })
})
