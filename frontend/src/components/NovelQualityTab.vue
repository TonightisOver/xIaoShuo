<template>
  <div class="space-y-6 animate-fade-up">
    <div v-if="loading" class="flex flex-col items-center justify-center py-20 space-y-3">
      <div class="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
      <p class="text-xs text-ink-300">正在生成深度质量审计报告...</p>
    </div>

    <div v-else-if="error" class="card p-6 text-center text-rose-400 bg-rose-950/20 border-rose-900 text-sm">
      {{ error }}
    </div>

    <div v-else-if="!report || !report.volume_reports || report.volume_reports.length === 0" class="card p-8 text-center text-ink-300 text-sm">
      暂无足够的章节数据生成质量评估报告。请在“章节”面板中生成章节后再查看。
    </div>

    <template v-else>
      <!-- Overall Score Grid -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div v-for="(val, key, idx) in report.overall_avg_scores" :key="key" class="card card-hover shine-on-hover animate-fade-up-stagger p-4 bg-paper-100 border border-ink-200 flex flex-col justify-between h-28" :style="{ animationDelay: `${Math.min(idx,8)*60}ms` }">
          <div class="text-[10px] text-ink-300 uppercase font-bold tracking-wider">{{ dimensionLabel(key) }}</div>
          <div class="flex items-baseline justify-between mt-2">
            <span class="text-3xl font-extrabold" :class="scoreColorClass(val)">{{ (val * 10).toFixed(1) }}</span>
            <span class="text-[10px] text-ink-400 font-medium">/ 10.0</span>
          </div>
          <div class="w-full bg-neutral-900 h-1.5 rounded-full mt-2 overflow-hidden">
            <div class="h-full rounded-full transition-all duration-500" :class="scoreProgressClass(val)" :style="{ width: (val * 100) + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- Warnings & Alerts Section -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Warnings list (Col span 2) -->
        <div class="lg:col-span-2 card p-6 bg-paper-100 border border-ink-200 space-y-4">
          <h3 class="text-sm font-bold text-ink-700 heading-serif flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 text-amber-500">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            <span>剧情与写作合规告警</span>
          </h3>

          <div v-if="allWarnings.length === 0 && !hasUnverified" class="text-xs text-emerald-400 bg-emerald-950/20 border border-emerald-900 rounded-xl p-4 flex items-center gap-2">
            ✅ 暂无严重质量告警，全书逻辑及推进节奏状态良好。
          </div>
          <div v-else-if="hasUnverified" class="text-xs text-amber-300 bg-amber-950/20 border border-amber-900/50 rounded-xl p-4 flex items-center gap-2">
            ⚠️ 部分章节质量未评估（生成失败或评审异常），以下数据不完整。
          </div>

          <div v-else class="space-y-2">
            <div v-for="(warn, index) in allWarnings" :key="index" class="animate-fade-up-stagger text-xs text-amber-300 bg-amber-950/20 border border-amber-900/50 rounded-xl p-3 flex items-start gap-2.5 leading-relaxed" :style="{ animationDelay: `${Math.min(index,8)*60}ms` }">
              <span class="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 shrink-0"></span>
              <div>
                <div class="font-bold text-ink-700">异常检测：{{ warn }}</div>
                <div class="text-[11px] text-ink-300 mt-0.5">建议：{{ getSuggestion(warn) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Side: Special Status chapters -->
        <div class="card p-6 bg-paper-100 border border-ink-200 space-y-4">
          <h3 class="text-sm font-bold text-ink-700 heading-serif">段落状态检测</h3>

          <div class="space-y-4">
            <div>
              <span class="text-xs text-ink-300 font-semibold block mb-1.5">灌水嫌疑章节 (Filler chapters)</span>
              <div v-if="fillerChapters.length === 0" class="text-xs text-ink-400 italic">暂无灌水嫌疑</div>
              <div v-else class="flex flex-wrap gap-1.5">
                <span v-for="ch in fillerChapters" :key="ch" class="text-[10px] font-bold text-rose-300 bg-rose-950/40 border border-rose-900 px-2 py-0.5 rounded-full">第 {{ ch }} 章</span>
              </div>
            </div>

            <div class="border-t border-ink-200 pt-3">
              <span class="text-xs text-ink-300 font-semibold block mb-1.5">情节推进缓慢章节 (Stalled chapters)</span>
              <div v-if="stalledChapters.length === 0" class="text-xs text-ink-400 italic">推进节奏良好</div>
              <div v-else class="flex flex-wrap gap-1.5">
                <span v-for="ch in stalledChapters" :key="ch" class="text-[10px] font-bold text-amber-300 bg-amber-950/40 border border-amber-900/50 px-2 py-0.5 rounded-full">第 {{ ch }} 章</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Volume breakdown cards -->
      <div class="space-y-4">
        <h3 class="text-sm font-bold text-ink-700 heading-serif">分卷趋势深度追踪</h3>
        <div v-for="(vol, vidx) in report.volume_reports" :key="vol.volume_number" class="card animate-fade-up-stagger p-6 bg-paper-100 border border-ink-200 space-y-4" :style="{ animationDelay: `${Math.min(vidx,8)*60}ms` }">
          <div class="flex justify-between items-center pb-2 border-b border-ink-200">
            <h4 class="font-extrabold text-ink-600 text-sm">
              {{ vol.volume_number === 0 ? '未分卷章节质量快照' : `第 ${vol.volume_number} 卷质量快照` }}
            </h4>
            <span class="text-xs text-ink-300 font-medium">共 {{ vol.chapter_count }} 章 · {{ (vol.total_word_count / 1000).toFixed(1) }}k 字</span>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
            <div v-for="(score, dim) in vol.avg_scores" :key="dim" class="bg-paper-200 border border-ink-200 rounded-xl p-2.5 text-center">
              <div class="text-[9px] text-ink-400 uppercase font-bold truncate">{{ dimensionLabel(dim) }}</div>
              <div class="text-lg font-black mt-1" :class="scoreColorClass(score)">{{ (score * 10).toFixed(1) }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'

export default {
  name: 'NovelQualityTab',
  props: {
    novelId: { type: String, required: true }
  },
  setup(props) {
    const report = ref(null)
    const loading = ref(false)
    const error = ref('')

    const dimensionMap = {
      'advancement': '剧情推进',
      'character_consistency': '角色一致',
      'world_consistency': '世界拟真',
      'pacing': '节奏掌控',
      'conflict': '冲突对抗',
      'foreshadowing': '伏笔铺设',
      'dialogue_quality': '对话文笔',
      'emotional_impact': '情感张力',
      'consistency': '合规一致'
    }

    const dimensionLabel = (key) => dimensionMap[key] || key

    const loadReport = async () => {
      loading.value = true
      error.value = ''
      try {
        const res = await fetch(`/api/v1/projects/${props.novelId}/quality-report`)
        if (res.ok) {
          report.value = await res.json()
        } else {
          const data = await res.json().catch(() => ({}))
          error.value = data.detail || '生成质量评估报告失败'
        }
      } catch (err) {
        error.value = '网络错误，加载质量报告失败'
      } finally {
        loading.value = false
      }
    }

    const scoreColorClass = (val) => {
      if (val >= 0.8) return 'text-emerald-400'
      if (val >= 0.6) return 'text-amber-400'
      return 'text-rose-400'
    }

    const scoreProgressClass = (val) => {
      if (val >= 0.8) return 'bg-emerald-500'
      if (val >= 0.6) return 'bg-amber-500'
      return 'bg-rose-500'
    }

    const hasUnverified = computed(() => {
      if (!report.value || !report.value.volume_reports) return false
      return report.value.volume_reports.some(v => v.has_unverified)
    })

    const allWarnings = computed(() => {
      if (!report.value || !report.value.volume_reports) return []
      const list = []
      report.value.volume_reports.forEach(v => {
        if (v.warnings && v.warnings.length > 0) {
          v.warnings.forEach(w => {
            const label = v.volume_number === 0 ? `未分卷章节: ${w}` : `第${v.volume_number}卷: ${w}`
            if (!list.includes(label)) list.push(label)
          })
        }
      })
      return list
    })

    const fillerChapters = computed(() => {
      if (!report.value || !report.value.volume_reports) return []
      const list = []
      report.value.volume_reports.forEach(v => {
        if (v.filler_chapters && v.filler_chapters.length > 0) {
          list.push(...v.filler_chapters)
        }
      })
      return Array.from(new Set(list)).sort((a, b) => a - b)
    })

    const stalledChapters = computed(() => {
      if (!report.value || !report.value.volume_reports) return []
      const list = []
      report.value.volume_reports.forEach(v => {
        if (v.stalled_chapters && v.stalled_chapters.length > 0) {
          list.push(...v.stalled_chapters)
        }
      })
      return Array.from(new Set(list)).sort((a, b) => a - b)
    })

    const getSuggestion = (warning) => {
      if (warning.includes('均分偏低')) {
        const dim = warning.split("'")[1] || ''
        return `该卷的【${dimensionLabel(dim)}】分数落入低位，建议在章节编辑框选中对应章节正文，使用【AI 改写】并指定指令“加强该片段的${dimensionLabel(dim)}”以自动重构润色。`
      }
      if (warning.includes('连续')) {
        return '检测到连续数章剧情几乎没有向前推进，疑似落入流水账/灌水模式。建议重新调整该分卷的大纲，或合并过渡章节以加快小说整体剧情节奏。'
      }
      if (warning.includes('字数异常偏少')) {
        return '该章节的字数明显偏少，内容细节不够充实。建议选中章节，利用 AI 改写或者手动重组并补充场景描写、心理描写等细节以充实章节字数。'
      }
      return '建议参考各章节版本历史中记录的 AI 修改建议，逐步对该卷章节进行润色与迭代。'
    }

    onMounted(loadReport)

    return {
      report,
      loading,
      error,
      dimensionLabel,
      scoreColorClass,
      scoreProgressClass,
      allWarnings,
      hasUnverified,
      fillerChapters,
      stalledChapters,
      getSuggestion,
    }
  }
}
</script>

<style scoped>
.card {
  border-radius: 16px;
  background-color: #12131e;
  border-color: #d9d0c2;
}
.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 9999px; }
</style>
