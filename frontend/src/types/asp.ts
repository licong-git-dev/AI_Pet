// ASP v0.1 - 跨终端的统一事件协议
// 与 backend/app/services/avatar_render/protocol.py 对齐

export type AvatarEventType =
  | 'speech'
  | 'emotion'
  | 'animation'
  | 'gaze'
  | 'idle'
  | 'wake'
  | 'sleep'
  | 'system'

export type AvatarEmotion =
  | 'happy' | 'sleepy' | 'curious' | 'loving' | 'sad'
  | 'angry' | 'surprised' | 'neutral' | 'confused' | 'proud'

export interface SpeechPayload {
  text: string
  audio_url?: string
  duration_ms?: number
  voice_style?: string
}

export interface AnimationPayload {
  name: string
  loop?: boolean
  duration_ms?: number
}

export interface AvatarStateEvent {
  event_id: string
  avatar_id: number
  user_id: number
  ts: string
  type: AvatarEventType
  emotion?: AvatarEmotion
  intensity?: number
  speech?: SpeechPayload
  animation?: AnimationPayload
  ttl_ms?: number
  asp_version?: string
}

export interface WireMessage {
  channel: 'avatar_render'
  asp_version: string
  event: AvatarStateEvent
}
