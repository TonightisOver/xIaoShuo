import { describe, it, expect } from 'vitest'
import { CAREER_PRESETS, getPresetCareer } from '../careerPresets.js'

describe('careerPresets', () => {
  describe('CAREER_PRESETS 数据完整性', () => {
    it('包含 4 个类别（修仙/武道/魔法/科技）', () => {
      // 不依赖顺序，用集合比较
      expect(new Set(Object.keys(CAREER_PRESETS))).toEqual(new Set(['修仙', '武道', '魔法', '科技']))
    })

    it('每个预设含 name/category/description/stages 且 stages 为 10 级', () => {
      for (const [key, preset] of Object.entries(CAREER_PRESETS)) {
        expect(preset.name).toBeTruthy()
        expect(preset.category).toBe(key)
        expect(preset.description).toBeTruthy()
        expect(preset.stages).toHaveLength(10)
        // 每个 stage 含 level/name/description/breakthrough
        preset.stages.forEach((stage, i) => {
          expect(stage.level).toBe(i + 1)
          expect(stage.name).toBeTruthy()
          expect(stage.description).toBeTruthy()
          expect(stage.breakthrough).toBeTruthy()
        })
      }
    })
  })

  describe('getPresetCareer 查表', () => {
    it('已知 category 返回对应预设（含 category 字段）', () => {
      const c = getPresetCareer('修仙')
      expect(c.name).toBe('大罗九天太乙仙')
      expect(c.category).toBe('修仙')
      expect(c.stages).toHaveLength(10)
    })

    it('武道类别返回武道预设', () => {
      const c = getPresetCareer('武道')
      expect(c.name).toBe('万劫真龙武神')
      expect(c.category).toBe('武道')
    })

    it('魔法类别返回魔法预设', () => {
      const c = getPresetCareer('魔法')
      expect(c.name).toBe('奥术编织主宰')
    })

    it('科技类别返回科技预设', () => {
      const c = getPresetCareer('科技')
      expect(c.name).toBe('序列超脑掌控者')
    })

    it('未知 category 回退到科技预设', () => {
      const c = getPresetCareer('不存在的类别')
      expect(c.name).toBe('序列超脑掌控者')
      expect(c.category).toBe('科技')
    })

    it('返回对象是副本（修改不影响原数据）', () => {
      const c1 = getPresetCareer('修仙')
      c1.name = '被篡改'
      c1.stages[0].name = '被篡改'
      const c2 = getPresetCareer('修仙')
      expect(c2.name).toBe('大罗九天太乙仙')
      expect(c2.stages[0].name).toBe('凡砂蜕骨')
    })

    it('返回的对象 category 字段与传入一致（即使回退也用预设的 category）', () => {
      // 未知类别回退时，category 应是预设的 '科技' 而非传入值
      const c = getPresetCareer('乱七八糟')
      expect(c.category).toBe('科技')
    })
  })
})
