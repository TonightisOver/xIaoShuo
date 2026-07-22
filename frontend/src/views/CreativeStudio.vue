<template>
  <div class="max-w-6xl mx-auto px-6 py-10 bg-paper-50 min-h-screen animate-fade-up">
    <div v-if="loading" class="flex flex-col items-center justify-center py-32 space-y-4">
      <div class="w-10 h-10 border-4 border-vermilion-500 border-t-transparent rounded-full animate-spin"></div>
      <p class="text-sm text-ink-400 font-medium">创作控制台加载中...</p>
    </div>

    <div v-else-if="!novel" class="text-center py-20 card p-8">
      <p class="text-ink-400 text-lg mb-4">该小说不存在或已被移除</p>
      <router-link to="/" class="btn-secondary">返回书架</router-link>
    </div>

    <template v-else>
      <!-- 顶部：返回 + 标题 + 模式切换 -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <router-link
            :to="`/novels/${novelId}`"
            class="text-xs text-vermilion-500 hover:text-vermilion-600 font-semibold"
          >← 返回详情</router-link>
          <h1 class="heading-serif text-3xl tracking-tight mt-1">{{ novel.title }}</h1>
          <p class="text-xs text-ink-400 mt-1">创作控制台</p>
        </div>

        <div class="flex items-center gap-2" data-mode-switch>
          <label class="text-xs text-ink-500 font-medium">创作模式</label>
          <select
            v-model="mode"
            @change="onModeChange"
            class="input text-sm"
            data-mode-select
          >
            <option value="auto">自动（连续生成）</option>
            <option value="assisted">辅助（关键阶段等确认）</option>
            <option value="manual">手动（逐阶段）</option>
          </select>
        </div>
      </div>

      <!-- 阶段导航 -->
      <div class="card p-4 mb-4">
        <CreativeStageNav
          :stages="stages"
          :creative-stage="creativeStage"
          @select="onSelectStage"
        />
      </div>

      <!-- 选中阶段产物详情 -->
      <div v-if="selectedStage" class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div class="card p-4" data-artifact-detail>
          <div class="flex items-center justify-between mb-3">
            <h3 class="heading-serif text-lg">{{ selectedStage.name }}</h3>
            <span v-if="control" class="text-xs text-ink-500">
              v{{ control.version }} · {{ statusLabel(control.control_status) }}
            </span>
          </div>

          <select
            v-if="(selectedStage.artifacts || []).length > 1"
            v-model="selectedArtifactId"
            data-artifact-select
            class="input text-sm w-full mb-3"
            @change="loadSelectedArtifact"
          >
            <option
              v-for="artifact in selectedStage.artifacts"
              :key="artifact.artifact_id"
              :value="artifact.artifact_id"
            >{{ artifact.label }}</option>
          </select>

          <textarea
            v-model="editContent"
            class="input text-sm w-full h-48 font-mono"
            placeholder="产物内容（JSON 或文本）"
            data-artifact-editor
          ></textarea>

          <div v-if="conflictHint" class="text-xs text-amber-600 mt-2" data-conflict-hint>
            {{ conflictHint }}
          </div>

          <div class="flex flex-wrap items-center gap-2 mt-3">
            <button
              class="btn-secondary text-xs"
              data-action="edit"
              @click="onEdit"
              :disabled="control && control.locked"
            >保存编辑</button>
            <button
              class="btn-secondary text-xs"
              data-action="approve"
              @click="onApprove"
            >确认</button>
            <button
              class="btn-secondary text-xs"
              data-action="lock"
              @click="onLock"
              :disabled="!control || control.control_status !== 'approved'"
            >锁定</button>
            <button
              class="btn-secondary text-xs"
              data-action="unlock"
              @click="onUnlock"
              :disabled="!control || !control.locked"
            >解锁</button>
            <button
              class="btn-primary text-xs"
              data-action="regenerate"
              @click="onRegenerate"
            >重新生成</button>
          </div>

          <p v-if="localError" class="text-xs text-rose-600 mt-2">{{ localError }}</p>
        </div>

        <ImpactPreviewPanel
          v-if="impact"
          :impact="impact"
          @choice="onImpactChoice"
        />
        <div v-else class="card p-4">
          <button class="btn-secondary text-xs" @click="loadImpact" data-load-impact>
            预览影响范围
          </button>
        </div>
      </div>

      <!-- 版本历史 + 操作记录 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div class="card p-4" data-versions>
          <h3 class="heading-serif text-lg mb-3">版本历史</h3>
          <ul v-if="versions.length" class="space-y-1">
            <li
              v-for="v in versions"
              :key="v.version_number || v.version"
              class="flex items-center justify-between text-sm text-ink-700"
            >
              <span>v{{ v.version_number || v.version }} · {{ v.source || v.created_at || '' }}</span>
              <button
                v-if="selectedStage"
                class="text-xs text-vermilion-500 hover:underline"
                @click="onRollback(v.version_number || v.version)"
              >回退</button>
            </li>
          </ul>
          <p v-else class="text-xs text-ink-400">暂无版本记录</p>
        </div>

        <div class="card p-4" data-operations>
          <h3 class="heading-serif text-lg mb-3">操作记录</h3>
          <ul v-if="operations.length" class="space-y-1 max-h-64 overflow-y-auto">
            <li
              v-for="op in operations"
              :key="op.id"
              class="text-xs text-ink-600"
            >
              <span class="font-medium">{{ op.action }}</span>
              · {{ op.artifact_type }}/{{ op.artifact_id }}
              <span v-if="op.from_version !== null && op.from_version !== undefined">v{{ op.from_version }}→v{{ op.to_version }}</span>
              · {{ op.created_at || '' }}
            </li>
          </ul>
          <p v-else class="text-xs text-ink-400">暂无操作记录</p>
        </div>
      </div>

      <!-- 生成范围 -->
      <div class="card p-4">
        <GenerationScopeSelector
          :novel-id="novelId"
          @plan="onScopePlan"
        />
        <p v-if="generationTask" class="text-xs text-emerald-700 mt-2" data-generation-task>
          生成任务已提交：{{ generationTask.task_id }}
        </p>
      </div>
    </template>
  </div>
</template>

<script setup>
/**
 * CreativeStudio —— 创作控制台主视图。
 *
 * 组合 CreativeStageNav / ImpactPreviewPanel / GenerationScopeSelector
 * + useCreativeControl composable，呈现 10 阶段导航 + 产物详情（编辑/确认/锁定/重生成）
 * + 影响范围 + 版本历史 + 操作记录 + 生成范围。
 *
 * 写操作带 expected_version 乐观锁；409 冲突时提示刷新并刷新最新版本。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import CreativeStageNav from '../components/CreativeStageNav.vue'
import ImpactPreviewPanel from '../components/ImpactPreviewPanel.vue'
import GenerationScopeSelector from '../components/GenerationScopeSelector.vue'
import { useCreativeControl } from '../composables/useCreativeControl.js'

const route = useRoute()
const novelId = computed(() => route.params.id)

const {
  getStage, getArtifact, editArtifact, lock, unlock, approve,
  regenerate, markStale, getImpact, listVersions, rollback, listOperations, setCreationMode,
  executeGenerateScope,
} = useCreativeControl(novelId)

const loading = ref(true)
const novel = ref(null)
const stages = ref([])
const creativeStage = ref(1)
const mode = ref('auto')

const selectedStageNumber = ref(null)
const control = ref(null)
const versions = ref([])
const impact = ref(null)
const operations = ref([])
const editContent = ref('')
const localError = ref('')
const conflictHint = ref('')
const generationTask = ref(null)
const activeArtifactVersion = ref(null)
const selectedArtifactId = ref(null)

const selectedStage = computed(() =>
  stages.value.find(s => s.number === selectedStageNumber.value) || null
)

function statusLabel(status) {
  const map = {
    draft: '草稿', generated: '已生成', edited: '已编辑',
    approved: '已确认', locked: '锁定', stale: '过期',
    generating: '生成中', failed: '失败',
  }
  return map[status] || status || '未生成'
}

async function loadAll() {
  loading.value = true
  localError.value = ''
  try {
    // novel 详情（复用 novels 端点）
    const nres = await fetch(`/api/v1/novels/${novelId.value}`)
    if (nres.ok) novel.value = await nres.json()
    const stageData = await getStage()
    stages.value = stageData.stages || []
    creativeStage.value = stageData.creative_stage || 1
    mode.value = stageData.creation_mode || 'auto'
    // 默认选中当前阶段
    await selectStage(creativeStage.value)
    await loadOperations()
  } catch (e) {
    localError.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function selectStage(num) {
  selectedStageNumber.value = num
  const st = selectedStage.value
  if (!st) return
  selectedArtifactId.value = st.artifacts?.[0]?.artifact_id || novelId.value
  await loadSelectedArtifact()
}

async function loadSelectedArtifact() {
  const st = selectedStage.value
  if (!st || !selectedArtifactId.value) return
  impact.value = null
  conflictHint.value = ''
  try {
    const art = await getArtifact(st.artifact_type, selectedArtifactId.value)
    control.value = art.control
    versions.value = art.versions || []
    activeArtifactVersion.value = art.active_version_number ?? null
    // 初始编辑内容：control 的 generation_meta 或产物内容
    editContent.value = typeof art.content === 'string'
      ? art.content
      : JSON.stringify(art.content ?? {}, null, 2)
  } catch (e) {
    localError.value = e.message
  }
}

async function onSelectStage(num) {
  await selectStage(num)
}

async function loadImpact() {
  if (!selectedStage.value) return
  try {
    impact.value = await getImpact(selectedStage.value.artifact_type, selectedArtifactId.value)
  } catch (e) {
    localError.value = e.message
  }
}

async function loadOperations() {
  try {
    operations.value = await listOperations({ limit: 50 })
  } catch (_) { /* best-effort */ }
}

function _handleConflict(e) {
  if (e.code === 'stale_version' || e.code === 'locked' || e.code === 'busy') {
    conflictHint.value = e.message + (e.current_version !== undefined ? `（当前版本 v${e.current_version}）` : '')
  } else {
    localError.value = e.message
  }
}

async function onEdit() {
  localError.value = ''
  conflictHint.value = ''
  if (!control.value || !selectedStage.value) return
  try {
    // 正文（chapter/chapter_version）作为纯文本提交；结构化产物尝试解析为 JSON。
    const isProse = ['chapter', 'chapter_version'].includes(selectedStage.value.artifact_type)
    let content = editContent.value
    if (!isProse) {
      try { content = JSON.parse(content) } catch (_) { /* 保留文本 */ }
    }
    const res = await editArtifact(
      selectedStage.value.artifact_type, selectedArtifactId.value,
      content, control.value.version, activeArtifactVersion.value,
    )
    await selectStage(selectedStageNumber.value)
    await loadOperations()
    return res
  } catch (e) {
    _handleConflict(e)
  }
}

async function onApprove() {
  if (!control.value) return
  try {
    await approve(selectedStage.value.artifact_type, selectedArtifactId.value, control.value.version)
    await selectStage(selectedStageNumber.value)
    await loadOperations()
  } catch (e) { _handleConflict(e) }
}

async function onLock() {
  if (!control.value) return
  try {
    await lock(selectedStage.value.artifact_type, selectedArtifactId.value, control.value.version)
    await selectStage(selectedStageNumber.value)
    await loadOperations()
  } catch (e) { _handleConflict(e) }
}

async function onUnlock() {
  if (!control.value) return
  try {
    await unlock(selectedStage.value.artifact_type, selectedArtifactId.value, control.value.version)
    await selectStage(selectedStageNumber.value)
    await loadOperations()
  } catch (e) { _handleConflict(e) }
}

async function onRegenerate() {
  if (!control.value) return
  try {
    await regenerate(
      selectedStage.value.artifact_type, selectedArtifactId.value, control.value.version,
      { force: control.value.locked },
    )
    await selectStage(selectedStageNumber.value)
    await loadOperations()
  } catch (e) { _handleConflict(e) }
}

async function onRollback(versionNumber) {
  if (!control.value) return
  try {
    await rollback(
      selectedStage.value.artifact_type, selectedArtifactId.value,
      versionNumber, control.value.version, activeArtifactVersion.value,
    )
    await selectStage(selectedStageNumber.value)
    await loadOperations()
  } catch (e) { _handleConflict(e) }
}

async function onImpactChoice(choice) {
  if (!control.value || !selectedStage.value || choice === 'save_only') return
  try {
    if (choice === 'mark_stale') {
      await markStale(
        selectedStage.value.artifact_type,
        selectedArtifactId.value,
        '用户选择保留下游并标记过期',
        control.value.version,
      )
    } else {
      const items = choice === 'regen_direct'
        ? (impact.value?.direct_downstream || [])
        : (impact.value?.full_downstream || [])
      const executable = items.filter(item =>
        item && !item.locked && item.version !== null && item.version !== undefined
      )
      await Promise.all(executable.map(item => regenerate(
        item.artifact_type,
        item.artifact_id,
        item.version,
      )))
    }
    await loadOperations()
  } catch (e) {
    _handleConflict(e)
  }
}

async function onScopePlan(payload) {
  // 调用 generate-scope 端点获取实际生成指令并跳转/触发
  try {
    generationTask.value = await executeGenerateScope(payload)
    await loadOperations()
  } catch (e) { localError.value = e.message }
}

async function onModeChange() {
  try {
    await setCreationMode(mode.value)
  } catch (e) { localError.value = e.message }
}

onMounted(loadAll)
</script>
