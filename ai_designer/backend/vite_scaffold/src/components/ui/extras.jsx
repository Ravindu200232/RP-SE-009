import * as React from 'react';
import { cva } from 'class-variance-authority';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

/* ------------------------------ Badge ----------------------------------- */
const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground shadow',
        secondary: 'border-transparent bg-secondary text-secondary-foreground',
        destructive: 'border-transparent bg-destructive text-destructive-foreground shadow',
        success: 'border-transparent bg-emerald-100 text-emerald-700',
        warning: 'border-transparent bg-amber-100 text-amber-700',
        outline: 'text-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  }
);
function Badge({ className, variant, ...props }) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

/* ----------------------------- Separator -------------------------------- */
const Separator = ({ className, orientation = 'horizontal', ...props }) => (
  <div className={cn('shrink-0 bg-border', orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px', className)} {...props} />
);

/* ------------------------------ Avatar ---------------------------------- */
function Avatar({ name = '?', src, className }) {
  const initial = String(name || '?').trim().charAt(0).toUpperCase() || '?';
  return (
    <div className={cn('relative flex h-9 w-9 shrink-0 overflow-hidden rounded-full bg-primary text-primary-foreground items-center justify-center text-sm font-semibold', className)}>
      {src ? <img src={src} alt="" className="aspect-square h-full w-full object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} /> : initial}
    </div>
  );
}

/* ------------------------------- Tabs ------------------------------------ */
const TabsCtx = React.createContext(null);
function Tabs({ defaultValue, value, onValueChange, children, className }) {
  const [internal, setInternal] = React.useState(defaultValue);
  const current = value !== undefined ? value : internal;
  const set = (v) => { setInternal(v); onValueChange && onValueChange(v); };
  return <TabsCtx.Provider value={{ current, set }}><div className={className}>{children}</div></TabsCtx.Provider>;
}
function TabsList({ className, ...props }) {
  return <div className={cn('inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground', className)} {...props} />;
}
function TabsTrigger({ value, className, ...props }) {
  const ctx = React.useContext(TabsCtx) || {};
  const active = ctx.current === value;
  return (
    <button
      type="button"
      onClick={() => ctx.set && ctx.set(value)}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50',
        active ? 'bg-background text-foreground shadow' : 'hover:text-foreground/80',
        className
      )}
      {...props}
    />
  );
}
function TabsContent({ value, className, ...props }) {
  const ctx = React.useContext(TabsCtx) || {};
  if (ctx.current !== value) return null;
  return <div className={cn('mt-2', className)} {...props} />;
}

/* ----------------------------- Accordion --------------------------------- */
function Accordion({ children, className }) {
  return <div className={cn('divide-y divide-border rounded-lg border', className)}>{children}</div>;
}
function AccordionItem({ title, children, defaultOpen = false }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div>
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-4 py-4 text-left text-sm font-medium hover:underline">
        {title}
        <svg className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200', open && 'rotate-180')} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
      </button>
      {open && <div className="px-4 pb-4 text-sm text-muted-foreground">{children}</div>}
    </div>
  );
}

/* ------------------------------- Dialog ---------------------------------- */
function Dialog({ open, onOpenChange, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={() => onOpenChange && onOpenChange(false)}>
      <div className="relative w-full max-w-lg rounded-xl border bg-background p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <button type="button" aria-label="Close" onClick={() => onOpenChange && onOpenChange(false)} className="absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100">
          <X className="h-4 w-4" />
        </button>
        {children}
      </div>
    </div>
  );
}
const DialogTitle = ({ className, ...props }) => <h2 className={cn('text-lg font-semibold leading-none tracking-tight', className)} {...props} />;
const DialogDescription = ({ className, ...props }) => <p className={cn('text-sm text-muted-foreground mt-1.5', className)} {...props} />;
const DialogFooter = ({ className, ...props }) => <div className={cn('mt-6 flex justify-end gap-2', className)} {...props} />;

/* -------------------------------- Table ---------------------------------- */
const Table = ({ className, ...props }) => (
  <div className="relative w-full overflow-x-auto"><table className={cn('w-full caption-bottom text-sm', className)} {...props} /></div>
);
const TableHeader = ({ className, ...props }) => <thead className={cn('[&_tr]:border-b', className)} {...props} />;
const TableBody = ({ className, ...props }) => <tbody className={cn('[&_tr:last-child]:border-0', className)} {...props} />;
const TableRow = ({ className, ...props }) => <tr className={cn('border-b transition-colors hover:bg-muted/50', className)} {...props} />;
const TableHead = ({ className, ...props }) => <th className={cn('h-10 px-3 text-left align-middle font-medium text-muted-foreground', className)} {...props} />;
const TableCell = ({ className, ...props }) => <td className={cn('p-3 align-middle', className)} {...props} />;

export {
  Badge, badgeVariants, Separator, Avatar,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Accordion, AccordionItem,
  Dialog, DialogTitle, DialogDescription, DialogFooter,
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
};
