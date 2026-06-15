import { useState, useMemo, useEffect } from 'react'
import { FolderOpen, ChevronRight, Search } from 'lucide-react'
import { openLocalPath } from '../../api/open'
import { LoadingPane, EmptyPane } from '../ui/Spinner'
import type { Project } from '../../types'

interface Props {
  projects: Project[]
  loading: boolean
  selected: string | null
  onSelect: (path: string) => void
}

interface TreeNode {
  name: string
  path: string
  project: Project | null   // null = pure directory node
  children: Map<string, TreeNode>
}

function buildTree(projects: Project[]): Map<string, TreeNode> {
  const root = new Map<string, TreeNode>()

  for (const p of projects) {
    const segments = p.path.split('/')
    let level = root

    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i]
      const nodePath = segments.slice(0, i + 1).join('/')

      if (!level.has(seg)) {
        level.set(seg, { name: seg, path: nodePath, project: null, children: new Map() })
      }

      const node = level.get(seg)!
      if (i === segments.length - 1) node.project = p
      level = node.children
    }
  }

  return root
}

function sorted(children: Map<string, TreeNode>): TreeNode[] {
  return [...children.values()].sort((a, b) => {
    // directories before leaf projects
    const ad = a.children.size > 0 ? 0 : 1
    const bd = b.children.size > 0 ? 0 : 1
    if (ad !== bd) return ad - bd
    return a.name.localeCompare(b.name)
  })
}

function ancestorPaths(path: string): string[] {
  const parts = path.split('/')
  return parts.slice(0, -1).map((_, i) => parts.slice(0, i + 1).join('/'))
}

export function ProjectList({ projects, loading, selected, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  // Auto-expand all ancestors of the selected project
  useEffect(() => {
    if (!selected) return
    setExpanded((prev) => new Set([...prev, ...ancestorPaths(selected)]))
  }, [selected])

  const filteredProjects = useMemo(() => {
    if (!query) return projects
    const q = query.toLowerCase()
    return projects.filter(
      (p) => p.name.toLowerCase().includes(q) || p.path.toLowerCase().includes(q),
    )
  }, [projects, query])

  const tree = useMemo(() => buildTree(filteredProjects), [filteredProjects])

  function toggle(path: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  if (loading) return <LoadingPane label="Loading projects…" />

  const roots = sorted(tree)

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

      {/* Tree */}
      <div className="overflow-y-auto flex-1 py-1">
        {!roots.length ? (
          <EmptyPane label={query ? 'No matches' : 'No projects found'} />
        ) : (
          roots.map((node) => (
            <TreeRow
              key={node.path}
              node={node}
              depth={0}
              expanded={expanded}
              selected={selected}
              forceExpand={!!query}
              onToggle={toggle}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </div>
  )
}

function TreeRow({
  node,
  depth,
  expanded,
  selected,
  forceExpand,
  onToggle,
  onSelect,
}: {
  node: TreeNode
  depth: number
  expanded: Set<string>
  selected: string | null
  forceExpand: boolean
  onToggle: (path: string) => void
  onSelect: (path: string) => void
}) {
  const hasChildren = node.children.size > 0
  const isOpen = forceExpand || expanded.has(node.path)
  const isActive = selected === node.path
  const isProject = node.project !== null
  const isDir = hasChildren && !isProject  // pure directory, no session data

  function handleClick() {
    if (hasChildren) onToggle(node.path)
    if (isProject) onSelect(node.path)
  }

  async function handleOpen(e: React.MouseEvent) {
    e.stopPropagation()
    try { await openLocalPath(node.path) } catch { /* ignore */ }
  }

  const pl = depth * 14 + 8

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={handleClick}
        onKeyDown={(e) => e.key === 'Enter' && handleClick()}
        style={{ paddingLeft: `${pl}px` }}
        className={`group flex items-center gap-1.5 py-[5px] pr-2 border-l-2 cursor-pointer select-none transition-colors
          ${isActive
            ? 'bg-vault-surface border-l-vault-accent'
            : 'border-l-transparent hover:bg-vault-surface'
          }`}
      >
        {/* Chevron (expand/collapse) or spacer */}
        <span
          className={`shrink-0 transition-transform duration-100 text-vault-muted
            ${hasChildren ? '' : 'invisible'} ${isOpen && hasChildren ? 'rotate-90' : ''}`}
        >
          <ChevronRight size={11} />
        </span>

        {/* Icon */}
        <span className="text-[12px] shrink-0 leading-none">
          {isDir
            ? (isOpen ? '📂' : '📁')
            : isProject
              ? (node.project!.has_git ? '✅' : '📂')
              : (isOpen ? '📂' : '📁')
          }
        </span>

        {/* Label */}
        <span
          className={`flex-1 min-w-0 truncate text-[12px] leading-snug
            ${isProject ? 'font-medium text-vault-text' : 'text-vault-muted'}`}
        >
          {node.name}
        </span>

        {/* Right-side metadata (only for project nodes) */}
        {isProject && (
          <div className="flex items-center gap-1 shrink-0 ml-1">
            {Object.keys(node.project!.sources).map((src) => (
              <span
                key={src}
                className={`size-1.5 rounded-full ${src === 'claude' ? 'bg-[#79c0ff]' : 'bg-[#56d364]'}`}
                title={src}
              />
            ))}
            <span className="text-[11px] text-vault-muted tabular-nums">
              {node.project!.total_sessions}
            </span>
            <button
              onClick={handleOpen}
              title={`Open ~/${node.path}`}
              className="opacity-0 group-hover:opacity-100 transition-opacity text-vault-muted hover:text-vault-text cursor-pointer"
            >
              <FolderOpen size={11} />
            </button>
          </div>
        )}
      </div>

      {/* Recursive children */}
      {hasChildren && isOpen &&
        sorted(node.children).map((child) => (
          <TreeRow
            key={child.path}
            node={child}
            depth={depth + 1}
            expanded={expanded}
            selected={selected}
            forceExpand={forceExpand}
            onToggle={onToggle}
            onSelect={onSelect}
          />
        ))
      }
    </div>
  )
}
