import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useWebSocket } from '../composables/useWebSocket.js'

class MockWebSocket {
  static instances = []
  constructor(url, protocols) {
    this.url = url
    this.protocols = protocols
    this.readyState = 0
    this.sent = []
    this.onopen = null
    this.onmessage = null
    this.onclose = null
    this.onerror = null
    MockWebSocket.instances.push(this)
  }
  send(data) { this.sent.push(data) }
  close() {
    this.readyState = 3
    this.onclose?.()
  }
  triggerOpen() { this.readyState = 1; this.onopen?.() }
  triggerClose() { this.readyState = 3; this.onclose?.() }
}

beforeEach(() => {
  vi.useFakeTimers()
  MockWebSocket.instances = []
  globalThis.WebSocket = MockWebSocket
  globalThis.location = { protocol: 'http:', host: 'localhost' }
  const store = {}
  globalThis.localStorage = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v) },
    removeItem: (k) => { delete store[k] },
  }
})

afterEach(() => {
  vi.useRealTimers()
  delete globalThis.WebSocket
  delete globalThis.localStorage
})

describe('useWebSocket', () => {
  it('connects and exposes readyState', () => {
    const { connect, connected, readyState } = useWebSocket('t1', { onMessage: () => {} })
    connect()
    MockWebSocket.instances[0].triggerOpen()
    expect(connected.value).toBe(true)
    expect(readyState.value).toBe('OPEN')
  })

  it('schedules reconnect with exponential backoff after close', () => {
    const { connect, reconnectAttempts } = useWebSocket('t1', { onMessage: () => {}, pingInterval: 0 })
    connect()
    MockWebSocket.instances[0].triggerOpen()
    MockWebSocket.instances[0].triggerClose()
    // After close, reconnectAttempts becomes 1 immediately (incremented before timer fires)
    expect(reconnectAttempts.value).toBe(1)
    vi.advanceTimersByTime(1000)
    expect(MockWebSocket.instances).toHaveLength(2)
    expect(reconnectAttempts.value).toBe(1)
    MockWebSocket.instances[1].triggerClose()
    expect(reconnectAttempts.value).toBe(2)
    vi.advanceTimersByTime(2000)
    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('does not reconnect after intentional disconnect', () => {
    const { connect, disconnect } = useWebSocket('t1', { onMessage: () => {}, pingInterval: 0 })
    connect()
    MockWebSocket.instances[0].triggerOpen()
    disconnect()
    vi.advanceTimersByTime(5000)
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('sends session token as xiaoshuo subprotocol when present', () => {
    localStorage.setItem('session_token', 'valid-session')
    const { connect } = useWebSocket('t1', { onMessage: () => {} })
    connect()
    expect(MockWebSocket.instances[0].url).toContain('/ws/tasks/t1')
    expect(MockWebSocket.instances[0].protocols).toEqual(['xiaoshuo', 'valid-session'])
  })

  it('omits subprotocol when no session token', () => {
    const { connect } = useWebSocket('t1', { onMessage: () => {} })
    connect()
    expect(MockWebSocket.instances[0].protocols).toBeUndefined()
  })
})
