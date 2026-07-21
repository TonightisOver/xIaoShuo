import { ref, readonly } from 'vue'
import { authHeaders } from './useApi.js'

/**
 * useCreativeControl —— 创作控制台 API 封装。
 *
 * 调用 /api/v1/projects/{novelId}/creative-control/* 系列端点：
 * - getStage: 阶段导航 + 各产物 control 摘要 + 创作模式
 * - getArtifact / editArtifact / lock / unlock / approve / regenerate / markStale
 * - getImpact / listVersions / rollback / listOperations / setMode
 *
 * 写操作失败时若 HTTP 409（并发冲突），抛出带 { code, current_version } 的错误，
 * 调用方可据此提示"刷新后重试"并返回最新版本。
 */
export function useCreativeControl(novelIdRef) {
  const loading = ref(false)
  const error = ref(null)

  function id() {
    return typeof novelIdRef === 'object' && novelIdRef !== null && 'value' in novelIdRef
      ? novelIdRef.value
      : novelIdRef
  }

  async function _req(method, path, body) {
    error.value = null
    const headers = { ...authHeaders() }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const opts = { method, headers }
    if (body !== undefined) opts.body = JSON.stringify(body)
    const res = await fetch(`/api/v1/projects/${id()}/creative-control${path}`, opts)
    if (res.status === 409) {
      const detail = await res.json().catch(() => ({}))
      const err = new Error(detail.message || '产物版本已变化，请刷新后重试')
      err.code = detail.code || 'conflict'
      err.current_version = detail.current_version
      err.expected_version = detail.expected_version
      err.detail = detail
      error.value = err
      throw err
    }
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      const err = new Error(detail.detail || detail.message || `请求失败 (HTTP ${res.status})`)
      err.detail = detail
      error.value = err
      throw err
    }
    const text = await res.text()
    return text ? JSON.parse(text) : null
  }

  async function getStage() {
    loading.value = true
    try {
      return await _req('GET', '/stage')
    } finally {
      loading.value = false
    }
  }

  async function getArtifact(artifactType, artifactId) {
    return _req('GET', `/artifacts/${artifactType}/${artifactId}`)
  }

  async function editArtifact(artifactType, artifactId, content, expectedVersion) {
    return _req('PUT', `/artifacts/${artifactType}/${artifactId}`, {
      content,
      expected_version: expectedVersion,
    })
  }

  async function lock(artifactType, artifactId, expectedVersion) {
    return _req('POST', `/artifacts/${artifactType}/${artifactId}/lock`, {
      expected_version: expectedVersion,
    })
  }

  async function unlock(artifactType, artifactId, expectedVersion) {
    return _req('POST', `/artifacts/${artifactType}/${artifactId}/unlock`, {
      expected_version: expectedVersion,
    })
  }

  async function approve(artifactType, artifactId, expectedVersion) {
    return _req('POST', `/artifacts/${artifactType}/${artifactId}/approve`, {
      expected_version: expectedVersion,
    })
  }

  async function regenerate(artifactType, artifactId, expectedVersion, opts = {}) {
    return _req('POST', `/artifacts/${artifactType}/${artifactId}/regenerate`, {
      expected_version: expectedVersion,
      force: !!opts.force,
      reason: opts.reason || null,
    })
  }

  async function markStale(artifactType, artifactId, reason, expectedVersion) {
    return _req('POST', `/artifacts/${artifactType}/${artifactId}/mark-stale`, {
      expected_version: expectedVersion,
      reason: reason || null,
    })
  }

  async function getImpact(artifactType, artifactId) {
    return _req('GET', `/artifacts/${artifactType}/${artifactId}/impact`)
  }

  async function listVersions(artifactType, artifactId) {
    return _req('GET', `/artifacts/${artifactType}/${artifactId}/versions`)
  }

  async function rollback(artifactType, artifactId, versionNumber, expectedVersion) {
    return _req(
      'POST',
      `/artifacts/${artifactType}/${artifactId}/versions/${versionNumber}/rollback`,
      { expected_version: expectedVersion },
    )
  }

  async function listOperations(params = {}) {
    const qs = new URLSearchParams()
    if (params.artifact_type) qs.set('artifact_type', params.artifact_type)
    if (params.action) qs.set('action', params.action)
    if (params.limit) qs.set('limit', params.limit)
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    return _req('GET', `/operations${suffix}`)
  }

  async function previewGenerateScope(payload) {
    // 直接 fetch：不走 creative-control 前缀的列表方法，payload 形状由调用方决定
    error.value = null
    const res = await fetch(
      `/api/v1/projects/${id()}/creative-control/generate-scope/preview`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(payload),
      },
    )
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail.detail || '预览失败')
    }
    return res.json()
  }

  async function setCreationMode(mode) {
    return _req('PUT', '/mode', { creation_mode: mode })
  }

  return {
    loading: readonly(loading),
    error: readonly(error),
    getStage,
    getArtifact,
    editArtifact,
    lock,
    unlock,
    approve,
    regenerate,
    markStale,
    getImpact,
    listVersions,
    rollback,
    listOperations,
    previewGenerateScope,
    setCreationMode,
  }
}
