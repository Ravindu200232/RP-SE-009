import { Slot } from '@radix-ui/react-slot';
import { cva } from 'class-variance-authority';
import { cn } from '@/lib/utils.js';

const styles = cva('inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50', {
  variants: { variant: {
    default: 'bg-primary text-primary-foreground hover:opacity-90',
    outline: 'border border-border bg-card text-foreground hover:bg-muted',
    ghost: 'text-foreground hover:bg-muted',
  } }, defaultVariants: { variant: 'default' },
});

export function Button({ className, variant, asChild = false, ...props }) {
  const Component = asChild ? Slot : 'button';
  return <Component className={cn(styles({ variant }), className)} {...props} />;
}
