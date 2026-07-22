import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BlueprintEditor from '../../blueprints/BlueprintEditor.vue'

const WS = {
  blueprint: { chapter_type: 'main_advance', plot_goal: 'x', hook_design: '', foreshadow_actions: [], cliffhanger: '', pacing_target: 'medium', key_characters: [], word_target: 3000 },
  control: { version: 1, control_status: 'draft', locked: false },
  available_characters: [{ id: 1, name: '主角', role: 'protagonist' }],
}

describe('BlueprintEditor', () => {
  it('锁定蓝图禁用编辑', async () => {
    const wrapper = mount(BlueprintEditor, {
      props: { workspace: { ...WS, control: { ...WS.control, locked: true, control_status: 'locked' } }, options: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] }, draft: WS.blueprint, dirty: false, saving: false, conflict: null, selectedChapter: 1 },
    })
    await flushPromises()
    expect(wrapper.find('[data-field-chapter_type]').attributes('disabled')).toBeDefined()
  })

  it('409 冲突保留草稿并提示', async () => {
    const wrapper = mount(BlueprintEditor, {
      props: { workspace: WS, options: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] }, draft: { ...WS.blueprint, plot_goal: '改' }, dirty: true, saving: false, conflict: { current_version: 3, expected_version: 1 }, selectedChapter: 1 },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('版本冲突')
    expect(wrapper.text()).toContain('v3')
    expect(wrapper.find('[data-field-plot_goal]').element.value).toBe('改')
  })

  it('保存按钮触发 save 事件', async () => {
    const wrapper = mount(BlueprintEditor, {
      props: { workspace: WS, options: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] }, draft: WS.blueprint, dirty: true, saving: false, conflict: null, selectedChapter: 1 },
    })
    await flushPromises()
    await wrapper.find('[data-save-btn]').trigger('click')
    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('无蓝图时显示生成按钮', async () => {
    const wrapper = mount(BlueprintEditor, {
      props: { workspace: { blueprint: null, control: { version: 0, locked: false }, available_characters: [] }, options: { chapter_type: [], pacing_target: [], foreshadow_action: [] }, draft: null, dirty: false, saving: false, conflict: null, selectedChapter: 1 },
    })
    expect(wrapper.find('[data-generate-btn]').exists()).toBe(true)
  })
})
