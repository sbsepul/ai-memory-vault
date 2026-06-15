import type { Source } from '../../types'
import type { Project } from '../../types'

interface Props {
  source: Source
  onSource: (s: Source) => void
  projects: Project[]
}

const TABS: { label: string; value: Source }[] = [
  { label: 'All', value: '' },
  { label: 'Claude Code', value: 'claude' },
  { label: 'Codex CLI', value: 'codex' },
]

export function Header({ source, onSource, projects }: Props) {
  const totalSessions = projects.reduce((a, p) => a + p.total_sessions, 0)
  const totalMsgs = projects.reduce((a, p) => a + p.total_messages, 0)

  return (
    <header className="flex items-center gap-4 px-4 h-12 bg-vault-surface border-b border-vault-border shrink-0">
      <span className="font-semibold text-[15px] tracking-tight">
        ⬡ <span className="text-vault-accent">AI Memory Vault</span>
      </span>

      <nav className="flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => onSource(t.value)}
            className={`px-3 py-1 rounded-md text-[13px] transition-colors cursor-pointer border border-transparent
              ${source === t.value
                ? 'bg-vault-border text-vault-text'
                : 'text-vault-muted hover:text-vault-text hover:bg-vault-surface2'
              }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {projects.length > 0 && (
        <span className="ml-auto text-[12px] text-vault-muted">
          {projects.length} projects · {totalSessions} sessions · {totalMsgs.toLocaleString()} msgs
        </span>
      )}
    </header>
  )
}
