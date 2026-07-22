<template>
  <div class="min-h-screen bg-paper-50">
    <div class="max-w-7xl mx-auto px-4 py-6">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <router-link :to="`/novels/${novelId}`" class="text-xs text-vermilion-500 font-semibold">← 返回</router-link>
          <h1 class="heading-serif text-2xl">章节蓝图工作台</h1>
        </div>
      </div>

      <BlueprintBatchToolbar
        :selected-set="wb.selectedSet.value"
        :batch-preview="batchPreview"
        :batch-result="batchResult"
        @preview-generate="onPreviewGenerate"
        @batch-generate="onBatchGenerate"
        @batch-confirm="onBatch('approve')"
        @batch-lock="onBatch('lock')"
        @batch-unlock="onBatch('unlock')"
      />

      <div class="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-0 border border-ink-200 rounded-lg overflow-hidden min-h-[600px]">
        <!-- 左栏 -->
        <BlueprintChapterList
          :summaries="wb.summaries.value"
          :status-counts="wb.statusCounts.value"
          :loading="wb.listLoading.value"
          :selected-chapter="wb.selectedChapter.value"
          :selected-set="wb.selectedSet.value"
          :page="wb.page.value"
          :page-size="wb.pageSize.value"
          :total="wb.total.value"
          @select="onSelect"
          @filter-change="onFilter"
          @page-change="onPage"
          @selection-change="wb.selectedSet.value = $event"
        />
        <!-- 中栏 -->
        <div class="border-x border-ink-200">
          <div v-if="dirty && showSwitchPrompt" class="p-2 bg-amber-50 text-xs text-amber-700 flex items-center gap-2">
            有未保存修改，切换将丢失。
            <button @click="confirmSwitch" class="btn-secondary text-xs">确认切换</button>
            <button @click="cancelSwitch" class="btn-secondary text-xs">取消</button>
          </div>
          <BlueprintEditor
            :workspace="wb.workspace.value"
            :options="wb.options.value"
            :draft="wb.draft.value"
            :dirty="wb.dirty.value"
            :saving="wb.saving.value"
            :conflict="wb.conflict.value"
            :selected-chapter="wb.selectedChapter.value"
            @update="wb.updateDraft"
            @save="onSave"
            @discard="wb.discardDraft"
            @refresh="onRefresh"
            @generate="onGenerateSingle"
          />
        </div>
        <!-- 右栏 -->
        <BlueprintContextPanel
          :workspace="wb.workspace.value"
          :impact="impact"
          @confirm="onControl('approve')"
          @lock="onControl('lock')"
          @unlock="onControl('unlock')"
          @regenerate="onRegenerate"
          @view-versions="showVersionDialog = true"
          @load-impact="onLoadImpact"
          @choice="onImpactChoice"
        />
      </div>
    </div>

    <BlueprintVersionDialog
      :visible="showVersionDialog"
      :versions="versions"
      :compare-result="compareResult"
      :target-version="targetVersion"
      :impact="versionImpact"
      @compare="onCompare"
      @rollback="onRollback"
      @close="showVersionDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useBlueprintWorkbench } from '../composables/useBlueprintWorkbench.js'
import { useCreativeControl } from '../composables/useCreativeControl.js'
import { authHeaders } from '../composables/useApi.js'
import BlueprintChapterList from '../components/blueprints/BlueprintChapterList.vue'
import BlueprintEditor from '../components/blueprints/BlueprintEditor.vue'
import BlueprintContextPanel from '../components/blueprints/BlueprintContextPanel.vue'
import BlueprintBatchToolbar from '../components/blueprints/BlueprintBatchToolbar.vue'
import BlueprintVersionDialog from '../components/blueprints/BlueprintVersionDialog.vue'

const route = useRoute()
const novelId = route.params.id
const wb = useBlueprintWorkbench(novelId)
const control = useCreativeControl(novelId)

const batchPreview = ref(null)
const batchResult = ref(null)
const impact = ref(null)
const versions = ref([])
const compareResult = ref(null)
const targetVersion = ref(null)
const versionImpact = ref(null)
const showVersionDialog = ref(false)

const dirty = wb.dirty
const showSwitchPrompt = ref(false)
let pendingChapter = null

onMounted(async () => {
  await wb.fetchOptions()
  await wb.fetchSummaries({ page: 1 })
})

async function onFilter(f) { await wb.fetchSummaries({ ...f, page: 1 }) }
async function onPage(p) { await wb.fetchSummaries({ page: p }) }

async function onSelect(ch) {
  if (dirty.value) {
    showSwitchPrompt.value = true
    pendingChapter = ch
    return
  }
  await wb.fetchWorkspace(ch)
}
function confirmSwitch() {
  showSwitchPrompt.value = false
  dirty.value = false
  if (pendingChapter) wb.fetchWorkspace(pendingChapter)
  pendingChapter = null
}
function cancelSwitch() { showSwitchPrompt.value = false; pendingChapter = null }

async function onSave() {
  try {
    await wb.saveDraft(control)
  } catch { /* 冲突已写入 wb.conflict */ }
}
function onRefresh() { if (wb.selectedChapter.value) wb.fetchWorkspace(wb.selectedChapter.value) }

async function onGenerateSingle(ch) {
  await control.regenerate('blueprint', String(ch), wb.workspace.value?.control?.version ?? 0)
  await wb.fetchSummaries({ page: wb.page.value })
}

async function onControl(action) {
  try {
    const ev = wb.workspace.value?.control?.version ?? 0
    if (action === 'lock') await control.lock('blueprint', String(wb.selectedChapter.value), ev)
    if (action === 'unlock') await control.unlock('blueprint', String(wb.selectedChapter.value), ev)
    if (action === 'approve') await control.approve('blueprint', String(wb.selectedChapter.value), ev)
    await onRefresh()
  } catch { /* 409 已解析 */ }
}
async function onRegenerate() {
  await onGenerateSingle(wb.selectedChapter.value)
}

async function onPreviewGenerate() {
  const chs = [...wb.selectedSet.value]
  batchPreview.value = await wb.previewBatchGenerate(chs)
}
async function onBatchGenerate() {
  const chs = [...wb.selectedSet.value]
  batchResult.value = await wb.batchGenerate(chs)
  await wb.fetchSummaries({ page: wb.page.value })
}
async function onBatch(action) {
  const chs = [...wb.selectedSet.value]
  batchResult.value = await wb.batchControl(action, chs)
  await wb.fetchSummaries({ page: wb.page.value })
}

async function onLoadImpact() {
  if (!wb.selectedChapter.value) return
  impact.value = await control.getImpact('blueprint', String(wb.selectedChapter.value))
}
async function onImpactChoice() { /* 复用 CreativeStudio 逻辑，简化：刷新 */ await onLoadImpact() }

async function loadVersions() {
  if (!wb.selectedChapter.value) return
  versions.value = await control.listVersions('blueprint', String(wb.selectedChapter.value))
}
// 打开版本对话框时自动加载版本列表
watch(showVersionDialog, (v) => { if (v) loadVersions() })

async function onCompare(b) {
  if (!wb.selectedChapter.value) return
  const a = versions.value[0]?.version_number
  if (!a) return
  // useCreativeControl 未封装 compareVersions，直接调用后端比较端点
  try {
    const res = await fetch(
      `/api/v1/projects/${novelId}/creative-control/artifacts/blueprint/${wb.selectedChapter.value}/versions/compare?a=${a}&b=${b}`,
      { headers: { ...authHeaders() } },
    )
    if (!res.ok) throw new Error('比较失败')
    compareResult.value = await res.json()
  } catch { compareResult.value = null }
}
async function onRollback(v) {
  targetVersion.value = v
  versionImpact.value = await control.getImpact('blueprint', String(wb.selectedChapter.value))
  const ev = wb.workspace.value?.control?.version ?? 0
  await control.rollback('blueprint', String(wb.selectedChapter.value), v, ev)
  showVersionDialog.value = false
  await onRefresh()
}
</script>
