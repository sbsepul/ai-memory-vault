export function Spinner({ className = '' }: { className?: string }) {
  return (
    <div
      className={`inline-block size-4 rounded-full border-2 border-vault-border border-t-vault-accent animate-spin ${className}`}
    />
  )
}

export function LoadingPane({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 p-8 text-vault-muted text-sm">
      <Spinner />
      {label}
    </div>
  )
}

export function EmptyPane({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center p-8 text-vault-muted text-sm">
      {label}
    </div>
  )
}
