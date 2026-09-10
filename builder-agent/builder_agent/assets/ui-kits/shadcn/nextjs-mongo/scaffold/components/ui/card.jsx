import { cn } from '@/lib/utils.js';

export function Card({ className, ...props }) {
  return <section className={cn('rounded-xl border border-border bg-card text-foreground', className)} {...props} />;
}
export function CardHeader({ className, ...props }) {
  return <header className={cn('space-y-2 p-6', className)} {...props} />;
}
export function CardContent({ className, ...props }) {
  return <div className={cn('p-6 pt-0', className)} {...props} />;
}
