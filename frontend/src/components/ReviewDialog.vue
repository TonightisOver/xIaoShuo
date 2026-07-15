<template>
  <Teleport to="body">
    <div v-if="visible" class="review-overlay" @click.self="handleBackdropClick">
      <!-- 毛玻璃遮罩 -->
      <div class="absolute inset-0 bg-black/25 backdrop-blur-sm"></div>

      <!-- 对话框 -->
      <div class="review-dialog glass-panel ring-1 ring-black/5">
        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-neutral-200/60">
          <div class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                   stroke-width="2" stroke="currentColor" class="w-4.5 h-4.5 text-amber-600">
                <path stroke-linecap="round" stroke-linejoin="round"
                      d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.091-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.091L9 5.25l.813 2.846a4.5 4.5 0 003.091 3.091L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.091zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.456-2.456L14.25 6l1.035-.259a3.375 3.375 0 002.456-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
              </svg>
            </div>
            <div>
              <h3 class="text-sm font-semibold text-neutral-900">人工审核</h3>
              <p class="text-xs text-neutral-500 mt-0.5">章节质量检查 — 请决策</p>
            </div>
          </div>
          <button @click="handleCancel" class="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-600
                   hover:bg-neutral-100 transition-colors" :disabled="submitting">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2"
                 stroke="currentColor" class="w-4 h-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Body -->
        <div class="px-6 py-5 space-y-4 max-h-[60vh] overflow-y-auto">
          <!-- Quality Scores -->
          <div v-if="displayReviewData?.quality_scores" class="space-y-2">
            <div class="text-xs font-semibold text-neutral-500 uppercase tracking-wide">质量评分</div>
            <div class="grid grid-cols-2 gap-2">
              <div v-for="score in safeQualityScores(displayReviewData.quality_scores)" :key="score.name"
                   class="rounded-lg border border-neutral-200 bg-white/60 px-3 py-2">
                <div class="text-xs text-neutral-500">{{ score.name }}</div>
                <div class="text-lg font-bold mt-0.5"
                     :class="scoreScoreColor(score.value)">
                  {{ (typeof score.value === 'number' ? (score.value * 10).toFixed(0) : score.value) }}/10
                </div>
              </div>
            </div>
          </div>

          <!-- Consistency Warnings -->
          <div v-if="displayReviewData?.consistency_warnings?.length" class="space-y-2">
            <div class="text-xs font-semibold text-amber-700 uppercase tracking-wide flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2"
                   stroke="currentColor" class="w-3.5 h-3.5">
                <path stroke-linecap="round" stroke-linejoin="round"
                      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              一致性警告
            </div>
            <ul class="space-y-1.5">
              <li v-for="(warning, idx) in displayReviewData.consistency_warnings" :key="idx"
                  class="text-xs text-amber-800 bg-amber-50/70 border border-amber-200 rounded-lg px-3 py-2">
                {{ typeof warning === 'string' ? warning : warning.message || warning }}
              </li>
            </ul>
          </div>

          <!-- Revision Requests -->
          <div v-if="displayReviewData?.revision_requests?.length" class="space-y-2">
            <div class="text-xs font-semibold text-neutral-500 uppercase tracking-wide flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2"
                   stroke="currentColor" class="w-3.5 h-3.5 text-neutral-500">
                <path stroke-linecap="round" stroke-linejoin="round"
                      d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
              </svg>
              修改请求
            </div>
            <ul class="space-y-1.5">
              <li v-for="(req, idx) in displayReviewData.revision_requests" :key="idx"
                  class="text-xs text-neutral-700 bg-neutral-50 border border-neutral-200 rounded-lg px-3 py-2">
                {{ typeof req === 'string' ? req : req.description || req }}
              </li>
            </ul>
          </div>

          <!-- 无审核数据时的提示 -->
          <div v-if="!displayReviewData?.quality_scores?.length
                    && !displayReviewData?.consistency_warnings?.length
                    && !displayReviewData?.revision_requests?.length"
               class="text-center py-4 text-xs text-neutral-400">
            暂无审核详情，请基于上下文做出决策。
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-neutral-200/60">
          <!-- Revision text area (expandable) -->
          <div v-if="showRevisionInput" class="mb-4 space-y-2">
            <label class="text-xs font-semibold text-neutral-600">修改意见 / 驳回原因</label>
            <textarea v-model="instructions"
                      placeholder="请描述需要修改或驳回的原因…"
                      class="w-full px-3.5 py-2.5 bg-neutral-100 border border-neutral-200 rounded-lg
                             text-sm text-neutral-900 focus:outline-none focus:ring-2 focus:ring-accent-500/20
                             focus:border-accent-500 focus:bg-white resize-none"
                      rows="3" :disabled="submitting" />
          </div>

          <div class="flex gap-3">
            <button @click="handleRevise"
                    class="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 text-sm font-medium
                           rounded-lg border border-neutral-300 bg-white hover:bg-neutral-50
                           text-neutral-700 transition-colors active:scale-[0.98]"
                    :disabled="submitting">
              <span>✏️</span> 修改意见
            </button>
            <button @click="handleReject"
                    class="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 text-sm font-medium
                           rounded-lg border border-rose-300 bg-white hover:bg-rose-50
                           text-rose-700 transition-colors active:scale-[0.98]"
                    :disabled="submitting">
              <span>❌</span> 驳回
            </button>
            <button @click="handleApprove"
                    class="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 text-sm font-medium
                           rounded-lg border border-green-300 bg-white hover:bg-green-50
                           text-green-700 transition-colors active:scale-[0.98]"
                    :disabled="submitting">
              <span>✅</span> 通过
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { authHeaders } from '../composables/useApi.js'

const props = defineProps({
  taskId: { type: [String, Number], required: true },
  visible: { type: Boolean, default: false },
  reviewData: { type: Object, default: null },
  autoClose: { type: Boolean, default: false },
})

const emit = defineEmits(['update:visible', 'update:reviewData', 'cancel', 'decision'])

const submitting = ref(false)
const error = ref(null)
const instructions = ref('')
const showRevisionInput = ref(false)

// 优先使用 props 传入的 reviewData，否则 fallback 到本地（由 useReview fetch）
const localReviewData = ref(null)
const displayReviewData = computed(() => props.reviewData || localReviewData.value)

function scoreScoreColor(value) {
  if (typeof value !== 'number') return 'text-neutral-700'
  if (value >= 0.8) return 'text-green-600'
  if (value >= 0.6) return 'text-amber-600'
  return 'text-rose-600'
}

function safeQualityScores(scores) {
  if (Array.isArray(scores)) return scores
  if (scores && typeof scores === 'object') {
    return Object.entries(scores).map(([name, value]) => ({ name, value }))
  }
  return []
}

function closeModal() {
  showRevisionInput.value = false
  instructions.value = ''
  emit('update:visible', false)
}

async function submitDecision(status, instructionsValue) {
  if (submitting.value) return
  submitting.value = true
  error.value = null
  try {
    const body = { approval_status: status }
    if (instructionsValue) {
      body.revision_instructions = instructionsValue
    }
    const res = await fetch(`/api/v1/tasks/${props.taskId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '提交失败')
    }
    const data = await res.json()
    // 通知父组件：决策完成，带上响应
    emit('decision', { status, data })
    if (props.autoClose) {
      closeModal()
    }
  } catch (e) {
    error.value = e
    alert(e.message || '提交审核决策失败')
  } finally {
    submitting.value = false
  }
}

function handleApprove() {
  submitDecision('approved')
}

function handleReject() {
  // 如果没有意见，弹出简易提示让用户补充（可选 UX）
  submitDecision('rejected', instructions.value || undefined)
}

function handleRevise() {
  if (!showRevisionInput.value) {
    showRevisionInput.value = true
    return
  }
  if (!instructions.value?.trim()) {
    alert('请输入修改意见后再提交')
    return
  }
  submitDecision('revision', instructions.value)
}

function handleCancel() {
  showRevisionInput.value = false
  instructions.value = ''
  emit('cancel')
  if (props.autoClose) closeModal()
}

function handleBackdropClick() {
  // 有 pending review 时不允许背景关闭，必须做决策
}
</script>

<style scoped>
.review-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.review-dialog {
  position: relative;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  border-radius: 16px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.18), 0 4px 16px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

/* 毛玻璃面板 */
.glass-panel {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.5);
}
</style>
