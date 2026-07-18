"""Locode's pinned, offline shadcn-compatible component registry.

The registry is source code, not an npm runtime package.  Locode owns the complete
catalog index and resolves the audited primitives used by a generated application
without asking the model to install or invent dependencies.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


REGISTRY_NAME = "locode-shadcn"
REGISTRY_VERSION = "2026.07.18-2"

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
      default: "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
      secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
      outline: "border border-border bg-background text-foreground hover:bg-muted",
      ghost: "text-foreground hover:bg-muted",
      destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
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
export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("rounded-[var(--radius)] border border-border bg-card text-card-foreground shadow-[var(--shadow)]",className)} {...props}/>)
Card.displayName="Card"
export const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("flex flex-col space-y-1.5 p-6",className)} {...props}/>)
CardHeader.displayName="CardHeader"
export const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(({className,...props},ref)=><h3 ref={ref} className={cn("text-lg font-semibold tracking-tight",className)} {...props}/>)
CardTitle.displayName="CardTitle"
export const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(({className,...props},ref)=><p ref={ref} className={cn("text-sm text-muted-foreground",className)} {...props}/>)
CardDescription.displayName="CardDescription"
export const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("p-6 pt-0",className)} {...props}/>)
CardContent.displayName="CardContent"
export const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({className,...props},ref)=><div ref={ref} className={cn("flex items-center p-6 pt-0",className)} {...props}/>)
CardFooter.displayName="CardFooter"
'''

INPUT = '''import * as React from "react"
import { cn } from "@/lib/utils"
export type InputProps = React.InputHTMLAttributes<HTMLInputElement>
export const Input = React.forwardRef<HTMLInputElement, InputProps>(({className,type,...props},ref)=><input type={type} className={cn("flex h-11 w-full rounded-[var(--radius)] border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",className)} ref={ref} {...props}/>)
Input.displayName="Input"
'''

LABEL = '''import * as React from "react"
import { cn } from "@/lib/utils"
export const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(({className,...props},ref)=><label ref={ref} className={cn("text-sm font-medium text-foreground",className)} {...props}/>)
Label.displayName="Label"
'''

BADGE = '''import * as React from "react"
import { cn } from "@/lib/utils"
const badgeStyles = {
  default: "border-accent/30 bg-accent/10 text-accent",
  secondary: "border-border bg-secondary text-secondary-foreground",
  destructive: "border-destructive/30 bg-destructive/10 text-destructive",
  outline: "border-border text-foreground",
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
}
export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> { variant?: keyof typeof badgeStyles }
export function Badge({className,variant="default",...props}:BadgeProps){return <div className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",badgeStyles[variant]||badgeStyles.default,className)} {...props}/>}
'''

TABLE = '''import * as React from "react"
import { cn } from "@/lib/utils"
export const Table=React.forwardRef<HTMLTableElement,React.HTMLAttributes<HTMLTableElement>>(({className,...props},ref)=><div className="relative w-full overflow-auto"><table ref={ref} className={cn("w-full caption-bottom text-sm",className)} {...props}/></div>);Table.displayName="Table"
export const TableHeader=React.forwardRef<HTMLTableSectionElement,React.HTMLAttributes<HTMLTableSectionElement>>(({className,...props},ref)=><thead ref={ref} className={cn("border-b border-border",className)} {...props}/>);TableHeader.displayName="TableHeader"
export const TableBody=React.forwardRef<HTMLTableSectionElement,React.HTMLAttributes<HTMLTableSectionElement>>(({className,...props},ref)=><tbody ref={ref} className={cn("[&_tr:last-child]:border-0",className)} {...props}/>);TableBody.displayName="TableBody"
export const TableRow=React.forwardRef<HTMLTableRowElement,React.HTMLAttributes<HTMLTableRowElement>>(({className,...props},ref)=><tr ref={ref} className={cn("border-b border-border transition-colors hover:bg-muted/60",className)} {...props}/>);TableRow.displayName="TableRow"
export const TableHead=React.forwardRef<HTMLTableCellElement,React.ThHTMLAttributes<HTMLTableCellElement>>(({className,...props},ref)=><th ref={ref} className={cn("h-11 px-4 text-left align-middle text-xs font-semibold uppercase tracking-wider text-muted-foreground",className)} {...props}/>);TableHead.displayName="TableHead"
export const TableCell=React.forwardRef<HTMLTableCellElement,React.TdHTMLAttributes<HTMLTableCellElement>>(({className,...props},ref)=><td ref={ref} className={cn("p-4 align-middle text-foreground",className)} {...props}/>);TableCell.displayName="TableCell"
'''

TEXTAREA = '''import * as React from "react"
import { cn } from "@/lib/utils"
export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>
export const Textarea=React.forwardRef<HTMLTextAreaElement,TextareaProps>(({className,...props},ref)=><textarea ref={ref} className={cn("min-h-24 w-full rounded-[var(--radius)] border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",className)} {...props}/>);Textarea.displayName="Textarea"
'''

SELECT = '''"use client"
import * as React from "react"
import * as SelectPrimitive from "@radix-ui/react-select"
import { Check, ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@/lib/utils"

export const Select = SelectPrimitive.Root
export const SelectGroup = SelectPrimitive.Group
export const SelectValue = SelectPrimitive.Value

export const SelectTrigger = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger ref={ref} className={cn("flex h-11 w-full items-center justify-between rounded-[var(--radius)] border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1", className)} {...props}>
    {children}<SelectPrimitive.Icon asChild><ChevronDown className="h-4 w-4 opacity-60" /></SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
))
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName

export const SelectScrollUpButton = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.ScrollUpButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollUpButton>
>(({ className, ...props }, ref) => <SelectPrimitive.ScrollUpButton ref={ref} className={cn("flex cursor-default items-center justify-center py-1", className)} {...props}><ChevronUp className="h-4 w-4" /></SelectPrimitive.ScrollUpButton>)
SelectScrollUpButton.displayName = SelectPrimitive.ScrollUpButton.displayName

export const SelectScrollDownButton = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.ScrollDownButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollDownButton>
>(({ className, ...props }, ref) => <SelectPrimitive.ScrollDownButton ref={ref} className={cn("flex cursor-default items-center justify-center py-1", className)} {...props}><ChevronDown className="h-4 w-4" /></SelectPrimitive.ScrollDownButton>)
SelectScrollDownButton.displayName = SelectPrimitive.ScrollDownButton.displayName

export const SelectContent = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = "popper", ...props }, ref) => (
  <SelectPrimitive.Portal><SelectPrimitive.Content ref={ref} className={cn("relative z-50 max-h-96 min-w-32 overflow-hidden rounded-[var(--radius)] border border-border bg-popover text-popover-foreground shadow-[var(--shadow)]", position === "popper" && "data-[side=bottom]:translate-y-1 data-[side=top]:-translate-y-1", className)} position={position} {...props}>
    <SelectScrollUpButton /><SelectPrimitive.Viewport className={cn("p-1", position === "popper" && "h-[var(--radix-select-trigger-height)] min-w-[var(--radix-select-trigger-width)]")}>{children}</SelectPrimitive.Viewport><SelectScrollDownButton />
  </SelectPrimitive.Content></SelectPrimitive.Portal>
))
SelectContent.displayName = SelectPrimitive.Content.displayName

export const SelectLabel = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Label>
>(({ className, ...props }, ref) => <SelectPrimitive.Label ref={ref} className={cn("py-1.5 pl-8 pr-2 text-sm font-semibold", className)} {...props} />)
SelectLabel.displayName = SelectPrimitive.Label.displayName

export const SelectItem = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item ref={ref} className={cn("relative flex w-full cursor-default select-none items-center rounded-md py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50", className)} {...props}>
    <span className="absolute left-2 flex h-4 w-4 items-center justify-center"><SelectPrimitive.ItemIndicator><Check className="h-4 w-4" /></SelectPrimitive.ItemIndicator></span><SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
))
SelectItem.displayName = SelectPrimitive.Item.displayName

export const SelectSeparator = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Separator>
>(({ className, ...props }, ref) => <SelectPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-muted", className)} {...props} />)
SelectSeparator.displayName = SelectPrimitive.Separator.displayName
'''

CHECKBOX = '''import * as React from "react"
import { cn } from "@/lib/utils"
// `onCheckedChange` is accepted alongside the native `onChange`: LLM components reach for the
// shadcn-style callback constantly, so supporting it here avoids a prop-type error in every form.
export type CheckboxProps = Omit<React.InputHTMLAttributes<HTMLInputElement>,"type"> & {
  onCheckedChange?: (checked: boolean) => void
}
export const Checkbox=React.forwardRef<HTMLInputElement,CheckboxProps>(({className,onCheckedChange,onChange,...props},ref)=><input type="checkbox" ref={ref} className={cn("h-4 w-4 rounded border-border bg-background accent-primary",className)} onChange={(e)=>{onChange?.(e);onCheckedChange?.(e.target.checked)}} {...props}/>);Checkbox.displayName="Checkbox"
'''

SKELETON = '''import { cn } from "@/lib/utils"
export function Skeleton({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn("animate-pulse rounded-[var(--radius)] bg-muted",className)} {...props}/>}
'''

SEPARATOR = '''import * as React from "react"
import { cn } from "@/lib/utils"
export type SeparatorProps = React.HTMLAttributes<HTMLDivElement> & { orientation?: "horizontal" | "vertical"; decorative?: boolean }
export function Separator({className,orientation="horizontal",decorative=false,...props}:SeparatorProps){return <div role={decorative?"none":"separator"} aria-orientation={decorative?undefined:orientation} className={cn("shrink-0 bg-border",orientation==="horizontal"?"h-px w-full":"h-full w-px",className)} {...props}/>}
'''

ALERT = '''import * as React from "react"
import { cn } from "@/lib/utils"
const alertStyles = { default: "border-border bg-card text-card-foreground", destructive: "border-destructive/40 bg-destructive/10 text-destructive", success: "border-success/40 bg-success/10 text-success", warning: "border-warning/40 bg-warning/10 text-warning" }
export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> { variant?: keyof typeof alertStyles }
export function Alert({className,variant="default",...props}:AlertProps){return <div role="alert" className={cn("rounded-xl border p-4 text-sm",alertStyles[variant]||alertStyles.default,className)} {...props}/>}
export function AlertTitle({className,...props}:React.HTMLAttributes<HTMLHeadingElement>){return <h5 className={cn("mb-1 font-semibold",className)} {...props}/>}
export function AlertDescription({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn("text-muted-foreground",className)} {...props}/>} 
'''

DIALOG = '''"use client"
import * as React from "react"
import { cn } from "@/lib/utils"

type DialogState = { open: boolean; setOpen: (open: boolean) => void }
const DialogContext = React.createContext<DialogState | null>(null)
export function Dialog({open,onOpenChange,children}:{open?:boolean;onOpenChange?:(open:boolean)=>void;children:React.ReactNode}){
  const [internal,setInternal]=React.useState(false)
  const value=open ?? internal
  const setOpen=(next:boolean)=>{setInternal(next);onOpenChange?.(next)}
  return <DialogContext.Provider value={{open:value,setOpen}}>{children}</DialogContext.Provider>
}
export function DialogTrigger({children}:{children:React.ReactElement;asChild?:boolean}){
  const ctx=React.useContext(DialogContext)
  return React.cloneElement(children as React.ReactElement<{onClick?:()=>void}>,{onClick:()=>ctx?.setOpen(true)})
}
export function DialogContent({className,children,...props}:React.HTMLAttributes<HTMLDivElement>){
  const ctx=React.useContext(DialogContext)
  if(!ctx?.open)return null
  return <div className="fixed inset-0 z-50 grid place-items-center bg-background/80 p-4 backdrop-blur-sm" onMouseDown={()=>ctx.setOpen(false)}><div role="dialog" aria-modal="true" className={cn("w-full max-w-lg rounded-[var(--radius)] border border-border bg-card p-6 text-card-foreground shadow-[var(--shadow)]",className)} onMouseDown={e=>e.stopPropagation()} {...props}>{children}</div></div>
}
export function DialogHeader({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn("mb-4 space-y-1.5",className)} {...props}/>}
export function DialogTitle({className,...props}:React.HTMLAttributes<HTMLHeadingElement>){return <h2 className={cn("text-xl font-semibold",className)} {...props}/>}
export function DialogDescription({className,...props}:React.HTMLAttributes<HTMLParagraphElement>){return <p className={cn("text-sm text-muted-foreground",className)} {...props}/>}
export function DialogFooter({className,...props}:React.HTMLAttributes<HTMLDivElement>){return <div className={cn("mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",className)} {...props}/>}
export function DialogClose({children}:{children:React.ReactElement;asChild?:boolean}){const ctx=React.useContext(DialogContext);return React.cloneElement(children as React.ReactElement<{onClick?:()=>void}>,{onClick:()=>ctx?.setOpen(false)})}
'''

PROGRESS = '''import * as React from "react"
import { cn } from "@/lib/utils"
export function Progress({value=0,className,...props}:{value?:number}&React.HTMLAttributes<HTMLDivElement>){const pct=Math.max(0,Math.min(100,value));return <div role="progressbar" aria-valuenow={pct} className={cn("h-2 w-full overflow-hidden rounded-full bg-muted",className)} {...props}><div className="h-full bg-primary transition-all" style={{width:`${pct}%`}} /></div>}
'''

SWITCH = '''import * as React from "react"
import { cn } from "@/lib/utils"
export type SwitchProps=Omit<React.InputHTMLAttributes<HTMLInputElement>,"type"|"onChange">&{onCheckedChange?:(checked:boolean)=>void;onChange?:React.ChangeEventHandler<HTMLInputElement>}
export const Switch=React.forwardRef<HTMLInputElement,SwitchProps>(({className,onCheckedChange,onChange,...props},ref)=><input ref={ref} type="checkbox" role="switch" className={cn("h-6 w-11 cursor-pointer appearance-none rounded-full bg-muted p-0.5 transition before:block before:h-5 before:w-5 before:rounded-full before:bg-background before:shadow before:transition checked:bg-primary checked:before:translate-x-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",className)} onChange={e=>{onChange?.(e);onCheckedChange?.(e.target.checked)}} {...props}/>);Switch.displayName="Switch"
'''

PRIMITIVES = {
    "alert": ALERT,
    "badge": BADGE,
    "button": BUTTON,
    "card": CARD,
    "checkbox": CHECKBOX,
    "dialog": DIALOG,
    "input": INPUT,
    "label": LABEL,
    "progress": PROGRESS,
    "select": SELECT,
    "separator": SEPARATOR,
    "skeleton": SKELETON,
    "switch": SWITCH,
    "table": TABLE,
    "textarea": TEXTAREA,
}

# Prop-level contracts for the APIs Gemma most often composes. Export names alone do not prevent
# valid-looking but impossible props (`Separator orientation`, `Select onValueChange`, dialog
# `asChild`). These concise declarations are injected beside the exact export list in every prompt.
EXACT_SIGNATURES: dict[str, dict[str, str]] = {
    "button": {
        "Button": "React.forwardRef<HTMLButtonElement, ButtonProps>; ButtonProps extends button attributes and accepts variant, size, asChild?",
    },
    "checkbox": {
        "Checkbox": "React.forwardRef<HTMLInputElement, CheckboxProps>; checked? boolean; onCheckedChange?(checked:boolean); native input props",
    },
    "dialog": {
        "Dialog": "(props:{open?:boolean; onOpenChange?(open:boolean):void; children:React.ReactNode}) => JSX.Element",
        "DialogTrigger": "(props:{children:React.ReactElement; asChild?:boolean}) => JSX.Element",
        "DialogContent": "(props:React.HTMLAttributes<HTMLDivElement>) => JSX.Element | null",
        "DialogClose": "(props:{children:React.ReactElement; asChild?:boolean}) => JSX.Element",
    },
    "progress": {
        "Progress": "(props:{value?:number} & React.HTMLAttributes<HTMLDivElement>) => JSX.Element",
    },
    "select": {
        "Select": "Radix Select root; props include value?, defaultValue?, onValueChange?(value:string), open?, onOpenChange?",
        "SelectTrigger": "React.forwardRef<HTMLButtonElement, Radix SelectTrigger props>",
        "SelectValue": "Radix SelectValue; props include placeholder?",
        "SelectContent": "React.forwardRef<HTMLDivElement, Radix SelectContent props>",
        "SelectItem": "React.forwardRef<HTMLDivElement, Radix SelectItem props>; value:string is required",
    },
    "separator": {
        "Separator": "(props:React.HTMLAttributes<HTMLDivElement> & {orientation?:'horizontal'|'vertical'; decorative?:boolean}) => JSX.Element",
    },
    "switch": {
        "Switch": "React.forwardRef<HTMLInputElement, SwitchProps>; checked? boolean; onCheckedChange?(checked:boolean); native input props",
    },
}


def installed_components() -> list[str]:
    """Exact shadcn primitive names available to generation prompts."""
    return sorted(PRIMITIVES)


def component_export_map() -> dict[str, dict[str, Any]]:
    """Exact public value/type exports for every installed UI module.

    Supplying module names alone still let models invent exports. This map is derived from the
    audited source itself, so prompts and generated files cannot drift from the registry.
    """
    result: dict[str, dict[str, list[str]]] = {}
    for name, source in sorted(PRIMITIVES.items()):
        values = set(re.findall(r"export\s+(?:const|function|class)\s+([A-Za-z_$][\w$]*)", source))
        types = set(re.findall(r"export\s+(?:type|interface)\s+([A-Za-z_$][\w$]*)", source))
        for block in re.findall(r"export\s*\{([^}]+)\}", source):
            for raw in block.split(","):
                token = raw.strip().split(" as ")[-1].strip()
                if re.fullmatch(r"[A-Za-z_$][\w$]*", token):
                    values.add(token)
        result[f"@/components/ui/{name}"] = {
            "values": sorted(values),
            "types": sorted(types),
            "signatures": EXACT_SIGNATURES.get(name, {}),
        }
    return result


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
