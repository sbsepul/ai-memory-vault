import { useEffect, useRef, useCallback } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { formatDistanceToNow } from 'date-fns'
import type { SessionSummary } from '../../types'
import { LoadingPane, EmptyPane } from '../ui/Spinner'
import { SourceBadge } from '../ui/SourceBadge'

interface Props {
  sessions: SessionSummary[]
  loading: boolean
  selected: string | null
  projectName: string
  onSelect: (id: string) => void
}

export function SessionList({ sessions, loading, selected, projectName, onSelect }: Props) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: sessions.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 62,
    overscan: 5,
  })

  // Keyboard navigation (j/k or ↑/↓)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      const idx = sessions.findIndex((s) => s.id === selected)
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault()
        const next = sessions[idx + 1]
        if (next) onSelect(next.id)
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault()
        const prev = sessions[idx - 1]
        if (prev) onSelect(prev.id)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sessions, selected, onSelect])

  // Scroll selected item into view
  const scrollToSelected = useCallback(() => {
    if (!selected) return
    const idx = sessions.findIndex((s) => s.id === selected)
    if (idx >= 0) virtualizer.scrollToIndex(idx, { align: 'auto' })
  }, [selected, sessions, virtualizer])

  useEffect(() => { scrollToSelected() }, [selected]) // eslint-disable-line

  return (
    <div className="w-[300px] border-r border-vault-border flex flex-col shrink-0 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-vault-border shrink-0">
        <span className="font-semibold text-[14px] flex-1 truncate">{projectName}</span>
        {!loading && (
          <span className="text-[12px] text-vault-muted shrink-0 bg-vault-surface2 px-1.5 py-0.5 rounded">
            {sessions.length}
          </span>
        )}
      </div>

      {loading ? (
        <LoadingPane label="Loading sessions…" />
      ) : !sessions.length ? (
        <EmptyPane label="No sessions" />
      ) : (
        <div
          ref={parentRef}
          className="overflow-y-auto flex-1"
          style={{ contain: 'strict' }}
        >
          <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
            {virtualizer.getVirtualItems().map((vItem) => {
              const s = sessions[vItem.index]
              return (
                <div
                  key={s.id}
                  style={{
                    position: 'absolute',
                    top: 0,
                    transform: `translateY(${vItem.start}px)`,
                    width: '100%',
                  }}
                >
                  <SessionItem
                    session={s}
                    active={selected === s.id}
                    onClick={() => onSelect(s.id)}
                  />
                </div>
              )
            })}
          </div>
        </div>
      )}

      {!loading && sessions.length > 0 && (
        <div className="px-4 py-1.5 border-t border-vault-border text-[10px] text-vault-muted">
          ↑↓ / j·k to navigate
        </div>
      )}
    </div>
  )
}

function sessionLabel(s: SessionSummary): string {
  if (s.name && s.name !== s.project && s.name.length > 2) return s.name
  const date = s.started_at || s.updated_at
  if (date) {
    return new Date(date).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  }
  return s.id.slice(0, 8)
}

function SessionItem({
  session: s,
  active,
  onClick,
}: {
  session: SessionSummary
  active: boolean
  onClick: () => void
}) {
  const ago = s.updated_at || s.started_at
    ? formatDistanceToNow(new Date((s.updated_at || s.started_at)!), { addSuffix: true })
    : ''

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-2.5 border-b border-vault-border border-l-2 transition-colors cursor-pointer
        ${active
          ? 'bg-vault-surface border-l-vault-accent'
          : 'border-l-transparent hover:bg-vault-surface'
        }`}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-[13px] font-medium truncate flex-1 text-vault-text">
          {sessionLabel(s)}
        </span>
        <SourceBadge source={s.source} />
      </div>
      <div className="flex gap-2 text-[11px] text-vault-muted">
        <span>{s.message_count} msgs</span>
        {ago && <span className="truncate">{ago}</span>}
      </div>
    </button>
  )
}
