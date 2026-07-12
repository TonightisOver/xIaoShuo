import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ReviewDialog from '../ReviewDialog.vue'

// ── helpers ──────────────────────────────────────────────────────────────────

const TASK_ID = 'task-123'

/**
 * Build a fetch mock.
 * `routes` is an array of { match: string|RegExp, ok, status, body }
 * checked in order — first match wins.
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
    return {
      ok: true,
      status: 200,
      json: async () => ({}),
      text: async () => '{}',
    }
  })
}

const REVIEW_API_URL = `/api/v1/tasks/${TASK_ID}/review`

function mountDialog(props = {}, fetchMock = vi.fn()) {
  vi.stubGlobal('fetch', fetchMock)
  return mount(ReviewDialog, {
    props: {
      taskId: TASK_ID,
      visible: false,
      ...props,
    },
    global: {
      stubs: { Teleport: true },
    },
  })
}

// ── tests ─────────────────────────────────────────────────────────────────────

describe('ReviewDialog.vue', () => {
  beforeEach(() => {
    vi.stubGlobal('alert', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  // ── visibility ──────────────────────────────────────────────────────────────

  it('visible=false 时不渲染对话框', () => {
    const wrapper = mountDialog({ visible: false })
    expect(wrapper.find('.review-overlay').exists()).toBe(false)
  })

  it('visible=true 时渲染对话框', () => {
    const wrapper = mountDialog({ visible: true })
    expect(wrapper.find('.review-overlay').exists()).toBe(true)
    expect(wrapper.text()).toContain('人工审核')
    expect(wrapper.text()).toContain('通过')
    expect(wrapper.text()).toContain('驳回')
    expect(wrapper.text()).toContain('修改意见')
  })

  // ── handleApprove ───────────────────────────────────────────────────────────

  it('handleApprove 发送 approved 决策并 emit decision', async () => {
    const response = { id: 1, status: 'approved' }
    const fetchMock = makeFetch([
      { match: REVIEW_API_URL, ok: true, body: response },
    ])
    const wrapper = mountDialog({ visible: true }, fetchMock)

    const approveBtn = wrapper.findAll('button').find(b => b.text().includes('通过'))
    expect(approveBtn).toBeTruthy()
    await approveBtn.trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      REVIEW_API_URL,
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approval_status: 'approved' }),
      }),
    )

    const decisionEvent = wrapper.emitted('decision')
    expect(decisionEvent).toHaveLength(1)
    expect(decisionEvent[0]).toEqual([{ status: 'approved', data: response }])
  })

  // ── handleReject ────────────────────────────────────────────────────────────

  it('handleReject 发送 rejected 决策', async () => {
    const response = { id: 1, status: 'rejected' }
    const fetchMock = makeFetch([
      { match: REVIEW_API_URL, ok: true, body: response },
    ])
    const wrapper = mountDialog({ visible: true }, fetchMock)

    const rejectBtn = wrapper.findAll('button').find(b => b.text().includes('驳回'))
    expect(rejectBtn).toBeTruthy()
    await rejectBtn.trigger('click')
    await flushPromises()

    const decisionEvent = wrapper.emitted('decision')
    expect(decisionEvent).toHaveLength(1)
    expect(decisionEvent[0][0].status).toBe('rejected')
  })

  // ── handleRevise ────────────────────────────────────────────────────────────

  it('handleRevise 首次点击展开输入框，第二次点击提交 revision', async () => {
    const response = { id: 1, status: 'revision' }
    const fetchMock = makeFetch([
      { match: REVIEW_API_URL, ok: true, body: response },
    ])
    const wrapper = mountDialog({ visible: true }, fetchMock)

    const reviseBtn = wrapper.findAll('button').find(b => b.text().includes('修改意见'))
    expect(reviseBtn).toBeTruthy()

    // First click: expand textarea
    await reviseBtn.trigger('click')
    await flushPromises()
    const textarea = wrapper.find('textarea')
    expect(textarea.exists()).toBe(true)

    // Fill in instructions
    await textarea.setValue('需要修改第三段的描述')

    // Second click: submit revise
    await reviseBtn.trigger('click')
    await flushPromises()

    const decisionEvent = wrapper.emitted('decision')
    expect(decisionEvent).toHaveLength(1)
    expect(decisionEvent[0][0].status).toBe('revision')

    // Verify instructions were sent（后端契约：approval_status + revision_instructions）
    expect(fetchMock).toHaveBeenCalledWith(
      REVIEW_API_URL,
      expect.objectContaining({
        body: JSON.stringify({
          approval_status: 'revision',
          revision_instructions: '需要修改第三段的描述',
        }),
      }),
    )
  })

  it('handleRevise 未填写意见时提示 alert 不提交', async () => {
    const fetchMock = makeFetch([
      { match: REVIEW_API_URL, ok: true, body: {} },
    ])
    const wrapper = mountDialog({ visible: true }, fetchMock)

    const reviseBtn = wrapper.findAll('button').find(b => b.text().includes('修改意见'))

    // First click: expand
    await reviseBtn.trigger('click')
    await flushPromises()

    // Second click: try to submit empty
    await reviseBtn.trigger('click')
    await flushPromises()

    expect(global.alert).toHaveBeenCalledWith('请输入修改意见后再提交')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(wrapper.emitted('decision')).toBeUndefined()
  })

  // ── autoClose ───────────────────────────────────────────────────────────────

  it('autoClose=true 时决策成功后自动关闭', async () => {
    const fetchMock = makeFetch([
      { match: REVIEW_API_URL, ok: true, body: { id: 1 } },
    ])
    const wrapper = mountDialog({ visible: true, autoClose: true }, fetchMock)

    const approveBtn = wrapper.findAll('button').find(b => b.text().includes('通过'))
    await approveBtn.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('autoClose=false 时决策成功后不自动关闭', async () => {
    const fetchMock = makeFetch([
      { match: REVIEW_API_URL, ok: true, body: { id: 1 } },
    ])
    const wrapper = mountDialog({ visible: true, autoClose: false }, fetchMock)

    const approveBtn = wrapper.findAll('button').find(b => b.text().includes('通过'))
    await approveBtn.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('update:visible')).toBeUndefined()
  })

  // ── cancel ──────────────────────────────────────────────────────────────────

  it('handleCancel 发出 cancel 事件', async () => {
    const wrapper = mountDialog({ visible: true })

    const cancelBtn = wrapper.find('[disabled]') // cancel button may be the close icon
    // Find the close icon button (small button with the X icon)
    const allBtns = wrapper.findAll('button')
    const closeBtn = allBtns.find(b => !b.text().includes('通过') && !b.text().includes('驳回') && !b.text().includes('修改'))
    expect(closeBtn).toBeTruthy()
    await closeBtn.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('cancel')).toEqual([[]])
  })

  it('autoClose 模式下 cancel 同时关闭对话框', async () => {
    const wrapper = mountDialog({ visible: true, autoClose: true })

    const allBtns = wrapper.findAll('button')
    const closeBtn = allBtns.find(b => !b.text().includes('通过') && !b.text().includes('驳回') && !b.text().includes('修改'))
    await closeBtn.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('cancel')).toEqual([[]])
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  // ── error handling ──────────────────────────────────────────────────────────

  it('submitDecision 收到非 ok 响应时调用 alert', async () => {
    const fetchMock = makeFetch([
      {
        match: REVIEW_API_URL,
        ok: false,
        status: 500,
        body: { detail: '服务器内部错误' },
      },
    ])
    const wrapper = mountDialog({ visible: true }, fetchMock)

    const approveBtn = wrapper.findAll('button').find(b => b.text().includes('通过'))
    await approveBtn.trigger('click')
    await flushPromises()

    expect(global.alert).toHaveBeenCalledWith('服务器内部错误')
    expect(wrapper.emitted('decision')).toBeUndefined()
  })

  // ── submitting guard ────────────────────────────────────────────────────────

  it('submitting=true 时按钮被禁用', async () => {
    const fetchMock = vi.fn().mockReturnValue(
      new Promise(() => {
        // never resolves — simulates slow server
      }),
    )
    const wrapper = mountDialog({ visible: true }, fetchMock)

    const approveBtn = wrapper.findAll('button').find(b => b.text().includes('通过'))
    expect(approveBtn).toBeTruthy()
    await approveBtn.trigger('click')

    // 等待 Vue 响应式更新
    await flushPromises()

    // 重新获取按钮引用（因为 Vue 可能重新渲染）
    const buttons = wrapper.findAll('button')
    const approveBtnAfter = buttons.find(b => b.text().includes('通过'))
    expect(approveBtnAfter).toBeTruthy()
    expect(approveBtnAfter.attributes('disabled')).toBeDefined()
    expect(buttons.every(b => b.attributes('disabled') !== undefined)).toBe(true)
  })

  // ── display data ────────────────────────────────────────────────────────────

  it('展示 quality_scores 和 consistency_warnings', () => {
    const reviewData = {
      quality_scores: [{ name: '文笔', value: 0.85 }, { name: '逻辑', value: 0.6 }],
      consistency_warnings: ['主角姓名前后不一致'],
    }
    const wrapper = mountDialog({ visible: true, reviewData })

    expect(wrapper.text()).toContain('文笔')
    expect(wrapper.text()).toContain('逻辑')
    expect(wrapper.text()).toContain('主角姓名前后不一致')
  })

  it('quality_scores 为对象时也正确渲染', () => {
    const reviewData = {
      quality_scores: { '文笔': 0.9, '逻辑': 0.7 },
      consistency_warnings: [],
    }
    const wrapper = mountDialog({ visible: true, reviewData })

    expect(wrapper.text()).toContain('文笔')
    expect(wrapper.text()).toContain('逻辑')
  })

  it('无审核数据时显示空状态提示', () => {
    const wrapper = mountDialog({ visible: true, reviewData: {} })
    expect(wrapper.text()).toContain('暂无审核详情')
  })
})
