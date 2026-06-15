import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { CopyButton } from '../ui/CopyButton'
import type { ChatMessage } from '../../types'

const COLLAPSE_THRESHOLD = 1200 // chars

interface Props {
  message: ChatMessage
}

export function Message({ message: m }: Props) {
  const isUser = m.role === 'user'
  const isLong = m.content.length > COLLAPSE_THRESHOLD
  const [expanded, setExpanded] = useState(!isLong)

  const time = m.timestamp
    ? new Date(m.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    : ''

  const displayContent = expanded || !isLong
    ? m.content
    : m.content.slice(0, COLLAPSE_THRESHOLD) + '…'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`relative max-w-[85%] rounded-xl px-4 py-3 text-[13px] leading-relaxed
          ${isUser
            ? 'bg-vault-blue-dim rounded-br-sm text-[#c9d1d9]'
            : 'bg-vault-surface border border-vault-border rounded-bl-sm text-vault-text'
          }`}
      >
        {/* Role + time + copy header */}
        <div className="flex items-center justify-between gap-3 mb-2">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-vault-muted">
            {isUser ? 'You' : 'Assistant'}{time ? ` · ${time}` : ''}
          </span>
          <CopyButton text={m.content} />
        </div>

        {/* Content */}
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Code blocks
            code({ className, children }) {
              const match = /language-(\w+)/.exec(className || '')
              const lang = match?.[1] ?? ''
              const raw = String(children).replace(/\n$/, '')
              const isBlock = raw.includes('\n') || !!lang

              if (!isBlock) {
                return (
                  <code className="bg-[#0d1117] text-[#e6edf3] px-1.5 py-0.5 rounded text-[12px] font-mono border border-vault-border">
                    {raw}
                  </code>
                )
              }
              return (
                <div className="my-3 rounded-lg overflow-hidden border border-vault-border">
                  {/* Code block header */}
                  <div className="flex items-center justify-between px-3 py-1.5 bg-[#010409] border-b border-vault-border">
                    <span className="text-[11px] text-vault-muted font-mono">
                      {lang || 'code'}
                    </span>
                    <CopyButton text={raw} />
                  </div>
                  <SyntaxHighlighter
                    style={vscDarkPlus as Record<string, React.CSSProperties>}
                    language={lang || 'text'}
                    PreTag="div"
                    customStyle={{
                      margin: 0,
                      borderRadius: 0,
                      fontSize: '12px',
                      background: '#0d1117',
                      padding: '12px',
                    }}
                    codeTagProps={{ style: { fontFamily: '"SF Mono", "Fira Code", Consolas, monospace' } }}
                  >
                    {raw}
                  </SyntaxHighlighter>
                </div>
              )
            },
            // Paragraphs
            p({ children }) {
              return <p className="mb-2 last:mb-0">{children}</p>
            },
            // Lists
            ul({ children }) {
              return <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>
            },
            ol({ children }) {
              return <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>
            },
            li({ children }) {
              return <li className="leading-relaxed">{children}</li>
            },
            // Headings
            h1({ children }) { return <h1 className="text-base font-semibold mt-3 mb-1">{children}</h1> },
            h2({ children }) { return <h2 className="text-[13px] font-semibold mt-3 mb-1">{children}</h2> },
            h3({ children }) { return <h3 className="text-[13px] font-medium mt-2 mb-1 text-vault-muted">{children}</h3> },
            // Blockquote
            blockquote({ children }) {
              return (
                <blockquote className="border-l-2 border-vault-muted pl-3 text-vault-muted italic my-2">
                  {children}
                </blockquote>
              )
            },
            // Table
            table({ children }) {
              return (
                <div className="overflow-x-auto my-3">
                  <table className="text-[12px] border-collapse w-full">{children}</table>
                </div>
              )
            },
            th({ children }) {
              return <th className="border border-vault-border px-3 py-1.5 text-left bg-vault-surface2 font-semibold">{children}</th>
            },
            td({ children }) {
              return <td className="border border-vault-border px-3 py-1.5">{children}</td>
            },
            // Strong / em
            strong({ children }) { return <strong className="font-semibold text-vault-text">{children}</strong> },
            // Horizontal rule
            hr() { return <hr className="border-vault-border my-3" /> },
            // Link — open in new tab, prevent navigation
            a({ href, children }) {
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-vault-accent underline underline-offset-2 hover:opacity-80"
                >
                  {children}
                </a>
              )
            },
          }}
        >
          {displayContent}
        </ReactMarkdown>

        {/* Collapse toggle */}
        {isLong && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="flex items-center gap-1 mt-2 text-[11px] text-vault-accent hover:opacity-80 cursor-pointer"
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? 'Show less' : `Show ${Math.round((m.content.length - COLLAPSE_THRESHOLD) / 100) * 100}+ more chars`}
          </button>
        )}
      </div>
    </div>
  )
}
