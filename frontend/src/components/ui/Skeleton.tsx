'use client'

interface SkeletonProps {
  variant?: 'line' | 'card' | 'circle'
  className?: string
  width?: string
  height?: string
}

export function Skeleton({
  variant = 'line',
  className = '',
  width,
  height,
}: SkeletonProps) {
  const baseClasses = 'animate-pulse bg-surface-800 rounded'

  const variantClasses: Record<string, string> = {
    line: 'h-4 w-full rounded',
    card: 'h-24 w-full rounded-lg',
    circle: 'h-10 w-10 rounded-full',
  }

  return (
    <div
      className={`${baseClasses} ${variantClasses[variant]} ${className}`}
      style={{ width, height }}
    />
  )
}

export function SkeletonConversationList() {
  return (
    <div className="p-2 space-y-1">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-2 px-3 py-2.5">
          <Skeleton variant="circle" className="h-4 w-4" />
          <div className="flex-1 space-y-1.5">
            <Skeleton variant="line" className="h-3.5 w-3/4" />
            <Skeleton variant="line" className="h-2.5 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function SkeletonWorkflowList() {
  return (
    <div className="p-2 space-y-1">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-2 px-3 py-2.5">
          <Skeleton variant="circle" className="h-4 w-4" />
          <div className="flex-1 space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Skeleton variant="line" className="h-3.5 w-2/3" />
              <Skeleton variant="line" className="h-4 w-12 rounded-full" />
            </div>
            <Skeleton variant="line" className="h-2.5 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  )
}
