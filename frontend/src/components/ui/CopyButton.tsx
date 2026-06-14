import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

export function CopyButton({ text, className = '' }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard not available (non-https); silently ignore
    }
  }

  return (
    <button
      onClick={handleCopy}
      title={copied ? 'Copied!' : 'Copy'}
      className={`flex items-center gap-1 text-[11px] text-vault-muted hover:text-vault-text transition-colors cursor-pointer ${className}`}
    >
      {copied ? <Check size={12} className="text-vault-green" /> : <Copy size={12} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}
