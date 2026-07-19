import { ref } from 'vue'

export function useWebSocket(taskId, { onMessage, reconnect: shouldReconnect = true, pingInterval = 30000, maxBackoff = 30000 } = {}) {
  const ws = ref(null)
  const connected = ref(false)
  const reconnectAttempts = ref(0)
  const readyState = ref('CLOSED')

  let intentionalClose = false
  let pingTimer = null
  let reconnectTimer = null
  let backoffMs = 0

  function clearTimers() {
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = null
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function startPing() {
    if (pingInterval <= 0) return
    clearInterval(pingTimer)
    pingTimer = setInterval(() => {
      if (ws.value && ws.value.readyState === WebSocket.OPEN) {
        try {
          ws.value.send(JSON.stringify({ type: 'ping' }))
        } catch {
          // ignore ping failures; onclose will handle reconnect
        }
      }
    }, pingInterval)
  }

  function scheduleReconnect() {
    if (!shouldReconnect || intentionalClose) return
    if (reconnectTimer) return
    backoffMs = backoffMs ? Math.min(backoffMs * 2, maxBackoff) : 1000
    reconnectAttempts.value += 1
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, backoffMs)
  }

  function connect() {
    if (ws.value && (ws.value.readyState === WebSocket.OPEN || ws.value.readyState === WebSocket.CONNECTING)) {
      return
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws/tasks/${taskId}`

    // 通过 Sec-WebSocket-Protocol 子协议传 session token（浏览器 WS 无法发自定义 Header）
    const token = localStorage.getItem('session_token')
    const socket = token
      ? new WebSocket(url, ['xiaoshuo', token])
      : new WebSocket(url)
    ws.value = socket
    readyState.value = 'CONNECTING'

    socket.onopen = () => {
      connected.value = true
      readyState.value = 'OPEN'
      backoffMs = 0
      reconnectAttempts.value = 0
      startPing()
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch {
        // ignore parse errors
      }
    }

    socket.onclose = () => {
      connected.value = false
      readyState.value = 'CLOSED'
      clearInterval(pingTimer)
      pingTimer = null
      scheduleReconnect()
    }

    socket.onerror = () => {
      readyState.value = 'CLOSED'
      connected.value = false
    }
  }

  function disconnect() {
    intentionalClose = true
    clearTimers()
    if (ws.value) {
      try {
        ws.value.close()
      } catch {
        // ignore close errors
      }
      ws.value = null
    }
    connected.value = false
    readyState.value = 'CLOSED'
    reconnectAttempts.value = 0
    backoffMs = 0
  }

  return { connect, disconnect, connected, readyState, reconnectAttempts }
}
