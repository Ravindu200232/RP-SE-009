import { cn } from '@/lib/utils.js';

export function Badge({ className, ...props }) {
  return <span className={cn('inline-flex rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-foreground', className)} {...props} />;
}
