import { ref } from 'vue'

export function useApi() {
  const error = ref(null)

  async function _request(url, options = {}) {
    const res = await fetch(url, options)
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
