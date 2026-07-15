import { ref } from 'vue'

/**
 * useApi — 统一的 API 调用封装。
 *
 * 自动从 localStorage 注入 x-session-token 认证头（若已登录），
 * 避免每个需要认证的端点手动传头（修复导出/审核等 401 问题）。
 */

const TOKEN_KEY = 'session_token'

function _readToken() {
  // 容错：SSR / 测试环境可能无 localStorage
  try {
    return typeof localStorage !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null
  } catch (_) {
    return null
  }
}

function _clearToken() {
  try {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(TOKEN_KEY)
  } catch (_) { /* ignore */ }
}

function _readAuthHeaders() {
  const token = _readToken()
  return token ? { 'x-session-token': token } : {}
}

export function useApi() {
  const error = ref(null)

  async function _request(url, options = {}) {
    const headers = { ..._readAuthHeaders(), ...(options.headers || {}) }
    const res = await fetch(url, { ...options, headers })
    if (res.status === 401) {
      // token 失效/缺失：清除并跳登录（与 main.js 的路由守卫一致）
      _clearToken()
    }
    if (!res.ok) {
      let detail = '请求失败'
      try {
        const body = await res.json()
        detail = body.detail || detail
      } catch (_) {}
      throw new Error(detail)
    }
    const text = await res.text()
    return text ? JSON.parse(text) : null
  }

  async function apiGet(url) {
    return _request(url)
  }

  async function apiPost(url, body) {
    return _request(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  async function apiPut(url, body) {
    return _request(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  async function apiDelete(url) {
    return _request(url, { method: 'DELETE' })
  }

  return { error, apiGet, apiPost, apiPut, apiDelete }
}

/**
 * 给直接使用 fetch（不走 useApi）的组件提供认证头。
 * 用法：fetch(url, { headers: { 'Content-Type':'application/json', ...authHeaders() }, ... })
 */
export function authHeaders() {
  return _readAuthHeaders()
}
