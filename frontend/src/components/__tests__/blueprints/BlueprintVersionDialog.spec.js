import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BlueprintVersionDialog from '../../blueprints/BlueprintVersionDialog.vue'

describe('BlueprintVersionDialog', () => {
  it('版本行可以先选择回退，再由确认按钮执行回退', async () => {
    const wrapper = mount(BlueprintVersionDialog, {
      props: {
        visible: true,
        versions: [{ version_number: 2, source: 'manual' }],
        targetVersion: null,
      },
    })

    await wrapper.get('[data-select-rollback="2"]').trigger('click')
    expect(wrapper.emitted('select-rollback')[0]).toEqual([2])

    await wrapper.setProps({ targetVersion: 2 })
    expect(wrapper.find('[data-rollback-confirm]').exists()).toBe(true)
    await wrapper.get('[data-confirm-rollback]').trigger('click')
    expect(wrapper.emitted('rollback')[0]).toEqual([2])
  })

  it('没有版本时显示明确说明', () => {
    const wrapper = mount(BlueprintVersionDialog, {
      props: { visible: true, versions: [] },
    })
    expect(wrapper.text()).toContain('尚无可回退的版本记录')
  })

  it('渲染后端字段差异结构', () => {
    const wrapper = mount(BlueprintVersionDialog, {
      props: {
        visible: true,
        versions: [{ version_number: 2, source: 'manual' }],
        compareResult: {
          fields: [{ field: 'plot_goal', old: '旧目标', new: '新目标', changed: true }],
        },
      },
    })
    expect(wrapper.find('[data-compare-table]').text()).toContain('旧目标')
    expect(wrapper.find('[data-compare-table]').text()).toContain('新目标')
  })

  it('加载回退影响范围时不显示可执行确认按钮', () => {
    const wrapper = mount(BlueprintVersionDialog, {
      props: {
        visible: true,
        versions: [{ version_number: 1, source: 'generation', is_active: false }],
        impactLoading: true,
      },
    })
    expect(wrapper.text()).toContain('正在加载回退影响范围')
    expect(wrapper.find('[data-confirm-rollback]').exists()).toBe(false)
  })
})
