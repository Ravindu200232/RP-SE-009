import { cn } from '../../lib/utils.js';
export function Input({ className, ...props }) { return <input className={cn('min-h-11 w-full rounded-xl border border-border bg-card px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary', className)} {...props} />; }
