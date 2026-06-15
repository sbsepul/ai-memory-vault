export function SourceBadge({ source }: { source: 'claude' | 'codex' }) {
  const styles =
    source === 'claude'
      ? 'bg-vault-blue-dim text-[#79c0ff]'
      : 'bg-vault-green-dim text-[#56d364]'
  const label = source === 'claude' ? 'Claude' : 'Codex'
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-px rounded-full shrink-0 ${styles}`}>
      {label}
    </span>
  )
}
