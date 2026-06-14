import { useState } from 'react'
import { FolderOpen, Search } from 'lucide-react'
import { openLocalPath } from '../../api/open'
import { LoadingPane, EmptyPane } from '../ui/Spinner'
import type { Project } from '../../types'

interface Props {
  projects: Project[]
  loading: boolean
  selected: string | null
  onSelect: (path: string) => void
}

export function ProjectList({ projects, loading, selected, onSelect }: Props) {
  const [query, setQuery] = useState('')

  if (loading) return <LoadingPane label="Loading projects…" />

  const filtered = query
    ? projects.filter(
        (p) =>
          p.name.toLowerCase().includes(query.toLowerCase()) ||
          p.path.toLowerCase().includes(query.toLowerCase()),
      )
    : projects

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Search */}
      <div className="px-2 py-2 border-b border-vault-border shrink-0">
        <div className="flex items-center gap-2 bg-vault-surface2 rounded-md px-2.5 py-1.5 border border-vault-border focus-within:border-vault-accent transition-colors">
          <Search size={12} className="text-vault-muted shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter projects…"
            className="flex-1 bg-transparent text-[12px] text-vault-text placeholder:text-vault-muted outline-none"
          />
        </div>
      </div>

      {/* List */}
      <div className="overflow-y-auto flex-1">
        {!filtered.length ? (
          <EmptyPane label={query ? 'No matches' : 'No projects found'} />
        ) : (
          filtered.map((p) => (
            <ProjectItem
              key={p.path}
              project={p}
              active={selected === p.path}
              onClick={() => onSelect(p.path)}
            />
          ))
        )}
      </div>
    </div>
  )
}

function ProjectItem({
  project: p,
  active,
  onClick,
}: {
  project: Project
  active: boolean
  onClick: () => void
}) {
  const git = p.has_git ? '✅' : '📂'

  async function handleOpen(e: React.MouseEvent) {
    e.stopPropagation()
    try {
      await openLocalPath(p.path)
    } catch {
      // path might not exist on disk; ignore silently
    }
  }

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      className={`group flex items-center gap-2 px-3 py-2 border-l-2 cursor-pointer transition-colors
        ${active
          ? 'bg-vault-surface border-l-vault-accent'
          : 'border-l-transparent hover:bg-vault-surface'
        }`}
    >
      <span className="text-[13px] shrink-0">{git}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-medium truncate text-vault-text">{p.name}</div>
        <div className="text-[11px] text-vault-muted truncate">{p.path}</div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {/* Source dots */}
        {Object.keys(p.sources).map((src) => (
          <span
            key={src}
            className={`size-1.5 rounded-full ${src === 'claude' ? 'bg-[#79c0ff]' : 'bg-[#56d364]'}`}
            title={src}
          />
        ))}
        <span className="text-[11px] text-vault-muted">{p.total_sessions}</span>
        {/* Open folder button — only visible on hover */}
        <button
          onClick={handleOpen}
          title={`Open ~/` + p.path}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-vault-muted hover:text-vault-text ml-1 cursor-pointer"
        >
          <FolderOpen size={12} />
        </button>
      </div>
    </div>
  )
}
