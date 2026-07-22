import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BlueprintChapterList from '../../blueprints/BlueprintChapterList.vue'

describe('BlueprintChapterList', () => {
  it('渲染含未生成状态的章节列表', async () => {
    const wrapper = mount(BlueprintChapterList, {
      props: {
        summaries: [
          { chapter_number: 1, title: '首章', has_blueprint: true, control_status: 'draft', has_outline: true },
          { chapter_number: 2, title: '', has_blueprint: false, control_status: 'not_generated' },
        ],
        statusCounts: {}, loading: false, selectedChapter: null, selectedSet: new Set(),
        page: 1, pageSize: 50, total: 2,
      },
    })
    const items = wrapper.findAll('[data-chapter-list] li')
    expect(items.length).toBe(2)
    expect(wrapper.find('[data-status="not_generated"]').text()).toContain('未生成')
  })

  it('点击章节触发 select', async () => {
    const wrapper = mount(BlueprintChapterList, {
      props: {
        summaries: [{ chapter_number: 5, title: 'x', has_blueprint: true, control_status: 'draft' }],
        statusCounts: {}, loading: false, selectedChapter: null, selectedSet: new Set(),
        page: 1, pageSize: 50, total: 1,
      },
    })
    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual([5])
  })

  it('状态筛选触发 filter-change', async () => {
    const wrapper = mount(BlueprintChapterList, {
      props: { summaries: [], statusCounts: {}, loading: false, selectedChapter: null, selectedSet: new Set(), page: 1, pageSize: 50, total: 0 },
    })
    await wrapper.find('[data-status-filter]').setValue('locked')
    await wrapper.find('[data-status-filter]').trigger('change')
    expect(wrapper.emitted('filter-change')[0][0].status).toBe('locked')
  })
})
