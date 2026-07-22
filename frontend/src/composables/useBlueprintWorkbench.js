import { ref } from 'vue'
import { useApi, authHeaders } from './useApi.js'

/**
 * useBlueprintWorkbench —— 章节蓝图工作台状态与 API。
 *
 * 只负责工作台独有的聚合查询（list/workspace/options）+ 批量操作。
 * 控制操作（edit/lock/unlock/approve/regenerate/rollback/impact/versions）
 * 复用 useCreativeControl（artifact_type="blueprint"）。
 *
 * 快速切章防覆盖：reqSeq 请求序号，旧请求结果丢弃。
 */
export function useBlueprintWorkbench(novelId) {
  const { apiGet, apiPost } = useApi()

  const summaries = ref([])
  const statusCounts = ref({})
  const page = ref(1)
  const pageSize = ref(50)
  const total = ref(0)
  const listLoading = ref(false)
  const listError = ref(null)

  const workspace = ref(null)
  const workspaceLoading = ref(false)
  const workspaceError = ref(null)

  const options = ref({ chapter_type: [], pacing_target: [], foreshadow_action: [] })

  const selectedChapter = ref(null)
  const selectedSet = ref(new Set())
  const draft = ref(null)
  const dirty = ref(false)
  const conflict = ref(null) // 409 冲突信息
  const saving = ref(false)

  let reqSeq = 0

  const base = `/api/v1/projects/${novelId}`

  async function fetchOptions() {
    try {
      options.value = await apiGet(`${base}/blueprints/options`)
    } catch (e) { /* 静默降级 */ }
  }

  async function fetchSummaries(filters = {}) {
    listLoading.value = true
    listError.value = null
    try {
      const qs = new URLSearchParams()
      if (filters.volume_number != null) qs.set('volume_number', filters.volume_number)
      if (filters.status) qs.set('status', filters.status)
      if (filters.search) qs.set('search', filters.search)
      if (filters.chapter_start != null) qs.set('chapter_start', filters.chapter_start)
      if (filters.chapter_end != null) qs.set('chapter_end', filters.chapter_end)
      qs.set('page', filters.page ?? page.value)
      qs.set('page_size', filters.page_size ?? pageSize.value)
      const suffix = qs.toString() ? `?${qs.toString()}` : ''
      const res = await apiGet(`${base}/blueprints${suffix}`)
      summaries.value = res.items || []
      statusCounts.value = res.status_counts || {}
      total.value = res.total || 0
      page.value = res.page || 1
      pageSize.value = res.page_size || 50
    } catch (e) {
      listError.value = e
    } finally {
      listLoading.value = false
    }
  }

  async function fetchWorkspace(chapterNumber) {
    // 防快速切章：旧请求结果丢弃
    const seq = ++reqSeq
    workspaceLoading.value = true
    workspaceError.value = null
    try {
      const res = await apiGet(`${base}/blueprints/${chapterNumber}/workspace`)
      if (seq !== reqSeq) return // 旧请求，丢弃
      workspace.value = res
      selectedChapter.value = chapterNumber
      draft.value = res.blueprint ? structuredClone(res.blueprint) : null
      dirty.value = false
      conflict.value = null
    } catch (e) {
      if (seq !== reqSeq) return
      workspaceError.value = e
    } finally {
      if (seq === reqSeq) workspaceLoading.value = false
    }
  }

  function updateDraft(field, value) {
    if (!draft.value) draft.value = {}
    draft.value[field] = value
    dirty.value = true
  }

  function discardDraft() {
    draft.value = workspace.value?.blueprint ? structuredClone(workspace.value.blueprint) : null
    dirty.value = false
    conflict.value = null
  }

  // 控制操作复用 useCreativeControl：由视图层注入 controlApi
  async function saveDraft(controlApi) {
    if (!workspace.value || !draft.value) return
    saving.value = true
    conflict.value = null
    try {
      await controlApi.editArtifact(
        'blueprint', String(selectedChapter.value), draft.value,
        workspace.value.control?.version ?? 0,
      )
      dirty.value = false
      await fetchWorkspace(selectedChapter.value) // 刷新
      return true
    } catch (e) {
      if (e.code === 'stale_version' || e.current_version != null) {
        conflict.value = { current_version: e.current_version, expected_version: e.expected_version }
      }
      throw e
    } finally {
      saving.value = false
    }
  }

  async function batchGenerate(chapterNumbers, { respect_locked = true, skip_confirmed = false } = {}) {
    return apiPost(`${base}/creative-control/generate-scope`, {
      mode: 'blueprint_only',
      chapter_numbers: chapterNumbers,
      respect_locked,
      skip_confirmed,
    })
  }

  async function previewBatchGenerate(chapterNumbers, { respect_locked = true, skip_confirmed = false } = {}) {
    const res = await fetch(`${base}/creative-control/generate-scope/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ mode: 'blueprint_only', chapter_numbers: chapterNumbers, respect_locked, skip_confirmed }),
    })
    if (!res.ok) throw new Error('预览失败')
    return res.json()
  }

  async function batchControl(action, chapterNumbers, expectedVersions = {}) {
    return apiPost(`${base}/creative-control/batch`, {
      action,
      artifact_type: 'blueprint',
      chapter_numbers: chapterNumbers,
      expected_versions: expectedVersions,
    })
  }

  return {
    summaries, statusCounts, page, pageSize, total, listLoading, listError,
    workspace, workspaceLoading, workspaceError, options,
    selectedChapter, selectedSet, draft, dirty, conflict, saving,
    fetchOptions, fetchSummaries, fetchWorkspace, updateDraft, discardDraft,
    saveDraft, batchGenerate, previewBatchGenerate, batchControl,
  }
}
