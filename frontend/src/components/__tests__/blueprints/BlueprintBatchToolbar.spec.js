import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BlueprintBatchToolbar from '../../blueprints/BlueprintBatchToolbar.vue'

describe('BlueprintBatchToolbar', () => {
  it('批量生成预览展示逐章明细与部分失败', () => {
    const wrapper = mount(BlueprintBatchToolbar, {
      props: {
        selectedSet: new Set([1, 2, 3]),
        batchPreview: { target_chapters: [1, 2], skipped_locked: [3], skipped_confirmed: [] },
        batchResult: { accepted: [{ chapter_number: 1, task_id: 't1' }], failed_to_enqueue: [{ chapter_number: 2, error: 'queue down' }] },
      },
    })
    expect(wrapper.find('[data-batch-preview]').text()).toContain('将处理 2 章')
    expect(wrapper.find('[data-batch-result]').text()).toContain('第2章')
    expect(wrapper.find('[data-batch-result]').text()).toContain('queue down')
  })

  it('批量生成按钮触发 preview-generate', async () => {
    const wrapper = mount(BlueprintBatchToolbar, { props: { selectedSet: new Set([1]) } })
    await wrapper.find('[data-batch-generate]').trigger('click')
    expect(wrapper.emitted('preview-generate')).toBeTruthy()
  })

  it('没有选中章节时禁用全部批量按钮', () => {
    const wrapper = mount(BlueprintBatchToolbar, { props: { selectedSet: new Set() } })
    for (const button of wrapper.findAll('button')) {
      expect(button.attributes('disabled')).toBeDefined()
    }
  })

  it('展示批量控制逐章成功与冲突结果', () => {
    const wrapper = mount(BlueprintBatchToolbar, {
      props: {
        selectedSet: new Set([1, 2]),
        batchResult: {
          results: [
            { chapter_number: 1, status: 'ok', version: 3 },
            { chapter_number: 2, status: 'conflict', current_version: 4 },
          ],
        },
      },
    })
    expect(wrapper.text()).toContain('第1章 → 成功')
    expect(wrapper.text()).toContain('第2章 → 版本冲突（当前 v4）')
  })
})
