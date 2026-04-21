import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-blue-600/20 text-blue-400 border-blue-500/30",
        secondary: "border-transparent bg-gray-800 text-gray-400 border-gray-700",
        destructive: "border-transparent bg-red-900/50 text-red-400 border-red-800/50",
        outline: "border-gray-700 text-gray-400",
        critical: "border-transparent bg-red-900/50 text-red-400 border-red-800/50",
        high: "border-transparent bg-orange-900/50 text-orange-400 border-orange-800/50",
        medium: "border-transparent bg-yellow-900/50 text-yellow-400 border-yellow-800/50",
        low: "border-transparent bg-green-900/50 text-green-400 border-green-800/50",
        info: "border-transparent bg-blue-900/50 text-blue-400 border-blue-800/50",
        pass: "border-transparent bg-green-900/50 text-green-400 border-green-800/50",
        fail: "border-transparent bg-red-900/50 text-red-400 border-red-800/50",
        running: "border-transparent bg-blue-900/50 text-blue-400 border-blue-500/30 animate-pulse",
        pending: "border-transparent bg-gray-800 text-gray-500 border-gray-700",
        completed: "border-transparent bg-green-900/50 text-green-400 border-green-800/50",
        failed: "border-transparent bg-red-900/50 text-red-400 border-red-800/50",
        skipped: "border-transparent bg-gray-800 text-gray-500 border-gray-700",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
