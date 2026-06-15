import { useEffect, useRef } from 'react'
import { useSession } from '../../api/sessions'
import { openLocalPath } from '../../api/open'
import { LoadingPane, EmptyPane } from '../ui/Spinner'
import { SourceBadge } from '../ui/SourceBadge'
import { Message } from './Message'
import { FolderOpen, MessageSquare, Calendar } from 'lucide-react'

interface Props {
  sessionId: string | null
  projectPath: string | null
}

export function SessionViewer({ sessionId, projectPath }: Props) {
  const { data: session, isLoading } = useSession(sessionId)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'instant' })
  }, [session?.id])

  if (!sessionId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-vault-muted">
        <MessageSquare size={32} strokeWidth={1} />
        <div className="text-center">
          <p className="text-vault-text font-medium mb-1">AI Memory Vault</p>
          <p className="text-sm">Select a project, then a session</p>
        </div>
        <a href="/api/docs" target="_blank" className="text-xs text-vault-accent hover:underline mt-2">
          API docs →
        </a>
      </div>
    )
  }

  if (isLoading) return <div className="flex-1"><LoadingPane label="Loading session…" /></div>
  if (!session) return <div className="flex-1"><EmptyPane label="Session not found" /></div>

  const messages = (session.messages ?? []).filter(
    (m) => m.role === 'user' || m.role === 'assistant',
  )
  const date = session.started_at
    ? new Date(session.started_at).toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : null

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Session header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-vault-border shrink-0 bg-vault-surface">
        <SourceBadge source={session.source} />
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-[14px] truncate">
            {session.name || session.id.slice(0, 12)}
          </div>
          <div className="flex items-center gap-3 text-[11px] text-vault-muted mt-0.5">
            <span className="flex items-center gap-1">
              <MessageSquare size={10} />
              {messages.length} messages
            </span>
            {date && (
              <span className="flex items-center gap-1">
                <Calendar size={10} />
                {date}
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        {projectPath && (
          <button
            onClick={() => openLocalPath(projectPath).catch(() => {})}
            title={`Open ~/` + projectPath}
            className="flex items-center gap-1.5 text-[12px] text-vault-muted hover:text-vault-text border border-vault-border rounded-md px-2.5 py-1 transition-colors cursor-pointer hover:bg-vault-surface2"
          >
            <FolderOpen size={13} />
            Open folder
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-4">
        {messages.length === 0 ? (
          <EmptyPane label="No messages in this session" />
        ) : (
          messages.map((msg, i) => <Message key={i} message={msg} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
