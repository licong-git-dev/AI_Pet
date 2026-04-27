import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { AvatarStateEvent, WireMessage } from '@/types/asp'

export type AvatarEventHandler = (event: AvatarStateEvent) => void

interface Options {
  onEvent?: AvatarEventHandler
  /** 自动重连间隔上限（毫秒），指数退避到此为止 */
  maxBackoffMs?: number
}

/**
 * 订阅后端 /ws，分发 channel == 'avatar_render' 的 ASP 事件。
 *
 * 自带：心跳、指数退避重连、token 失效自动停止。
 * 你也可以手动调用 send() 走应用层心跳/输入态。
 */
export function useAvatarSocket(opts: Options = {}) {
  const auth = useAuthStore()
  const maxBackoffMs = opts.maxBackoffMs ?? 30_000

  const status = ref<'idle' | 'connecting' | 'open' | 'closed' | 'error'>('idle')
  const lastEvent = shallowRef<AvatarStateEvent | null>(null)
  const lastError = ref<string | null>(null)

  let socket: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let pingTimer: ReturnType<typeof setInterval> | null = null
  let stopped = false

  function buildUrl(): string {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = location.host
    const token = encodeURIComponent(auth.token)
    return `${proto}//${host}/api/v1/ws?token=${token}`
  }

  function connect() {
    if (stopped || !auth.token) return
    status.value = 'connecting'
    try {
      socket = new WebSocket(buildUrl())
    } catch (e: any) {
      status.value = 'error'
      lastError.value = e?.message ?? String(e)
      scheduleReconnect()
      return
    }

    socket.onopen = () => {
      status.value = 'open'
      reconnectAttempts = 0
      // 应用层心跳，与后端 manager 心跳互不干扰
      pingTimer = setInterval(() => {
        try { socket?.send(JSON.stringify({ type: 'ping' })) } catch {}
      }, 25_000)
    }

    socket.onmessage = (msg) => {
      let payload: any
      try { payload = JSON.parse(msg.data) } catch { return }
      // 后端 manager 会在连接建立时下发 welcome / ping 等其它消息，过滤掉
      if (payload?.channel === 'avatar_render' && payload?.event) {
        const event = payload.event as AvatarStateEvent
        lastEvent.value = event
        opts.onEvent?.(event)
      }
    }

    socket.onerror = (e) => {
      status.value = 'error'
      lastError.value = (e as any)?.message ?? 'ws error'
    }

    socket.onclose = (e) => {
      status.value = 'closed'
      cleanupTimers()
      if (e.code === 4001) {
        // token 无效，停止重连
        stopped = true
        return
      }
      scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (stopped) return
    reconnectAttempts++
    const delay = Math.min(maxBackoffMs, 1000 * Math.pow(2, reconnectAttempts - 1))
    reconnectTimer = setTimeout(connect, delay)
  }

  function cleanupTimers() {
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null }
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  }

  function close() {
    stopped = true
    cleanupTimers()
    try { socket?.close() } catch {}
    socket = null
  }

  function send(payload: any): boolean {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload))
      return true
    }
    return false
  }

  onMounted(connect)
  onBeforeUnmount(close)

  return {
    status,
    lastEvent,
    lastError,
    send,
    close,
  }
}

/** 模拟一个 ASP 事件（用于本地预览/调试时不连后端也能看见动画）。 */
export function makeMockEvent(partial: Partial<AvatarStateEvent> = {}): AvatarStateEvent {
  return {
    event_id: crypto.randomUUID(),
    avatar_id: 0,
    user_id: 0,
    ts: new Date().toISOString(),
    type: 'speech',
    emotion: 'happy',
    intensity: 0.7,
    speech: { text: '主人～我在这里啦！' },
    ttl_ms: 4000,
    asp_version: '0.1',
    ...partial,
  }
}
