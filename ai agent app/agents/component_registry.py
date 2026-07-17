"""Locode's pinned, offline shadcn-compatible component registry.

The registry is source code, not an npm runtime package.  Locode owns the complete
catalog index and resolves the audited primitives used by a generated application
without asking the model to install or invent dependencies.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


REGISTRY_NAME = "locode-shadcn"
REGISTRY_VERSION = "2026.07.13-1"

# Full catalog index.  Complex items can be introduced as higher-level Locode blocks;
# generated apps currently copy the audited primitive subset below plus dependencies.
OFFICIAL_CATALOG = [
    "accordion", "alert", "alert-dialog", "aspect-ratio", "avatar", "badge",
    "breadcrumb", "button", "button-group", "calendar", "card", "carousel", "chart",
    "checkbox", "collapsible", "combobox", "command", "context-menu", "data-table",
    "date-picker", "dialog", "drawer", "dropdown-menu", "empty", "field", "form",
    "hover-card", "input", "input-group", "input-otp", "item", "kbd", "label",
    "menubar", "native-select", "navigation-menu", "pagination", "popover", "progress",
    "radio-group", "resizable", "scroll-area", "select", "separator", "sheet",
    "sidebar", "skeleton", "slider", "sonner", "spinner", "switch", "table", "tabs",
    "textarea", "toggle", "toggle-group", "tooltip", "typography",
]


UTILS = '''import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
'''

BUTTON = '''import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-xl text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50",
  { variants: { variant: {
      default: "bg-accent text-white shadow-lg shadow-black/25 hover:brightness-110",
      secondary: "bg-slate-800 text-slate-100 hover:bg-slate-700",
      outline: "border border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800",
      ghost: "text-slate-300 hover:bg-slate-800 hover:text-white",
      destructive: "bg-rose-600 text-white hover:bg-rose-500",
    }, size: { default: "h-10 px-4 py-2", sm: "h-9 px-3", lg: "h-11 px-6", icon: "h-10 w-10" } },
    defaultVariants: { variant: "default", size: "default" } }
)
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> { asChild?: boolean }
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild=false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
})
Button.displayName = "Button"
export { Button, buttonVariants }
'''

CARD = '''import * as React from "react"
import { cn } from "@/lib/utils"
export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("rounded-2xl border border-slate-800 bg-slate-900/80 text-slate-100 shadow-xl shadow-black/10",className)} {...props}/>)
Card.displayName="Card"
export const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("flex flex-col space-y-1.5 p-6",className)} {...props}/>)
CardHeader.displayName="CardHeader"
export const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(({className,...props},ref)=><h3 ref={ref} className={cn("text-lg font-semibold tracking-tight",className)} {...props}/>)
CardTitle.displayName="CardTitle"
export const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(({className,...props},ref)=><p ref={ref} className={cn("text-sm text-slate-400",className)} {...props}/>)
CardDescription.displayName="CardDescription"
export const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("p-6 pt-0",className)} {...props}/>)
CardContent.displayName="CardContent"
export const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("flex items-center p-6 pt-0",className)} {...props}/>)
CardFooter.displayName="CardFooter"
'''

INPUT = '''import * as React from "react"
import { cn } from "@/lib/utils"
export type InputProps = React.InputHTMLAttributes<HTMLInputElement>
export const Input = React.forwardRef<HTMLInputElement, InputProps>(({className,type,...props},ref)=><input type={type} className={cn("flex h-10 w-full rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50",className)} ref={ref} {...props}/>)
Input.displayName="Input"
'''

LABEL = '''import * as React from "react"
import { cn } from "@/lib/utils"
export const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(({className,...props},ref)=><label ref={ref} className={cn("text-sm font-medium text-slate-300",className)} {...props}/>)
Label.displayName="Label"
'''

BADGE = '''import * as React from "react"
import { cn } from "@/lib/utils"
const badgeStyles = {
  default: "border-accent/30 bg-accent/10 text-accent",
  secondary: "border-slate-700 bg-slate-800 text-slate-200",
  destructive: "border-rose-500/30 bg-rose-500/10 text-rose-300",
  outline: "border-slate-700 text-slate-300",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-300",
}
export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> { variant?: keyof typeof badgeStyles }
export function Badge({className,variant="default",...props}:BadgeProps){return <div className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",badgeStyles[variant]||badgeStyles.default,className)} {...props}/>}
'''

TABLE = '''import * as React from "react"
import { cn } from "@/lib/utils"
export const Table=React.forwardRef<HTMLTableElement,React.HTMLAttributes<HTMLTableElement>>(({className,...props},ref)=><div className="relative w-full overflow-auto"><table ref={ref} className={cn("w-full caption-bottom text-sm",className)} {...props}/></div>);Table.displayName="Table"
export const TableHeader=React.forwardRef<HTMLTableSectionElement,React.HTMLAttributes<HTMLTableSectionElement>>(({className,...props},ref)=><thead ref={ref} className={cn("border-b border-slate-800",className)} {...props}/>);TableHeader.displayName="TableHeader"
export const TableBody=React.forwardRef<HTMLTableSectionElement,React.HTMLAttributes<HTMLTableSectionElement>>(({className,...props},ref)=><tbody ref={ref} className={cn("[&_tr:last-child]:border-0",className)} {...props}/>);TableBody.displayName="TableBody"
export const TableRow=React.forwardRef<HTMLTableRowElement,React.HTMLAttributes<HTMLTableRowElement>>(({className,...props},ref)=><tr ref={ref} className={cn("border-b border-slate-800 transition-colors hover:bg-slate-800/40",className)} {...props}/>);TableRow.displayName="TableRow"
export const TableHead=React.forwardRef<HTMLTableCellElement,React.ThHTMLAttributes<HTMLTableCellElement>>(({className,...props},ref)=><th ref={ref} className={cn("h-11 px-4 text-left align-middle text-xs font-semibold uppercase tracking-wider text-slate-400",className)} {...props}/>);TableHead.displayName="TableHead"
export const TableCell=React.forwardRef<HTMLTableCellElement,React.TdHTMLAttributes<HTMLTableCellElement>>(({className,...props},ref)=><td ref={ref} className={cn("p-4 align-middle text-slate-300",className)} {...props}/>);TableCell.displayName="TableCell"
'''

TEXTAREA = '''import * as React from "react"
import { cn } from "@/lib/utils"
export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>
export const Textarea=React.forwardRef<HTMLTextAreaElement,TextareaProps>(({className,...props},ref)=><textarea ref={ref} className={cn("min-h-24 w-full rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",className)} {...props}/>);Textarea.displayName="Textarea"
'''

SELECT = '''import * as React from "react"
import { cn } from "@/lib/utils"
export type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement>
export const Select=React.forwardRef<HTMLSelectElement,SelectProps>(({className,...props},ref)=><select ref={ref} className={cn("flex h-10 w-full rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",className)} {...props}/>);Select.displayName="Select"
'''

CHECKBOX = '''import * as React from "react"
import { cn } from "@/lib/utils"
// `onCheckedChange` is accepted alongside the native `onChange`: LLM components reach for the
// shadcn-style callback constantly, so supporting it here avoids a prop-type error in every form.
export type CheckboxProps = Omit<React.InputHTMLAttributes<HTMLInputElement>,"type"> & {
  onCheckedChange?: (checked: boolean) => void
}
export const Checkbox=React.forwardRef<HTMLInputElement,CheckboxProps>(({className,onCheckedChange,onChange,...props},ref)=><input type="checkbox" ref={ref} className={cn("h-4 w-4 rounded border-slate-600 bg-slate-900 accent-accent",className)} onChange={(e)=>{onChange?.(e);onCheckedChange?.(e.target.checked)}} {...props}/>);Checkbox.displayName="Checkbox"
'''

SKELETON = '''import { cn } from "@/lib/utils"
export function Skeleton({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn("animate-pulse rounded-xl bg-slate-800",className)} {...props}/>}
'''

SEPARATOR = '''import { cn } from "@/lib/utils"
export function Separator({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div role="separator" className={cn("h-px w-full bg-slate-800",className)} {...props}/>}
'''

ALERT = '''import * as React from "react"
import { cn } from "@/lib/utils"
const alertStyles = { default: "border-slate-700 bg-slate-900 text-slate-200", destructive: "border-rose-500/40 bg-rose-500/10 text-rose-200", success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200", warning: "border-amber-500/40 bg-amber-500/10 text-amber-200" }
export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> { variant?: keyof typeof alertStyles }
export function Alert({className,variant="default",...props}:AlertProps){return <div role="alert" className={cn("rounded-xl border p-4 text-sm",alertStyles[variant]||alertStyles.default,className)} {...props}/>}
export function AlertTitle({className,...props}:React.HTMLAttributes<HTMLHeadingElement>){return <h5 className={cn("mb-1 font-semibold",className)} {...props}/>}
export function AlertDescription({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn("text-slate-400",className)} {...props}/>}
'''

PRIMITIVES = {
    "alert": ALERT,
    "badge": BADGE,
    "button": BUTTON,
    "card": CARD,
    "checkbox": CHECKBOX,
    "input": INPUT,
    "label": LABEL,
    "select": SELECT,
    "separator": SEPARATOR,
    "skeleton": SKELETON,
    "table": TABLE,
    "textarea": TEXTAREA,
}


def registry_files(spec: dict) -> dict[str, str]:
    files = {f"components/ui/{name}.tsx": source for name, source in PRIMITIVES.items()}
    files["lib/utils.ts"] = UTILS
    files["components.json"] = json.dumps({
        "$schema": "https://ui.shadcn.com/schema.json",
        "style": "new-york",
        "rsc": True,
        "tsx": True,
        "tailwind": {"config": "tailwind.config.ts", "css": "app/globals.css", "cssVariables": True},
        "aliases": {"components": "@/components", "ui": "@/components/ui", "lib": "@/lib", "hooks": "@/hooks", "utils": "@/lib/utils"},
        "iconLibrary": "lucide",
    }, indent=2) + "\n"
    manifest: dict[str, Any] = {
        "$schema": "https://ui.shadcn.com/schema/registry.json",
        "name": REGISTRY_NAME,
        "version": REGISTRY_VERSION,
        "mode": "offline-pinned",
        "catalog": OFFICIAL_CATALOG,
        "installed": sorted(PRIMITIVES),
        "items": [
            {
                "name": name,
                "type": "registry:ui",
                "files": [f"components/ui/{name}.tsx"],
                "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            }
            for name, source in sorted(PRIMITIVES.items())
        ],
    }
    files[".locode/shadcn-registry.json"] = json.dumps(manifest, indent=2) + "\n"
    return files


def validate_registry_files(files: dict[str, str]) -> list[str]:
    errors = []
    for name in PRIMITIVES:
        path = f"components/ui/{name}.tsx"
        if path not in files or not files[path].strip():
            errors.append(f"missing-registry-item:{name}")
    for required in ("lib/utils.ts", "components.json", ".locode/shadcn-registry.json"):
        if required not in files:
            errors.append(f"missing-registry-file:{required}")
    return errors
