export type Source = '' | 'claude' | 'codex'

export interface Project {
  path: string
  name: string
  has_git: boolean
  sources: Record<string, number>
  total_sessions: number
  total_messages: number
  last_active: string | null
}

export interface SessionSummary {
  id: string
  source: 'claude' | 'codex'
  project: string
  name: string
  started_at: string | null
  updated_at: string | null
  message_count: number
  has_git: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string | null
}

export interface SessionDetail extends SessionSummary {
  messages: ChatMessage[]
}
