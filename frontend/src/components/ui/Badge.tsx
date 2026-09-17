import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "error" | "info" | "outline";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-pill border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-brand-sage focus:ring-offset-2",
        {
          "border-transparent bg-foreground text-background": variant === "default",
          "border-transparent bg-status-success text-white": variant === "success",
          "border-transparent bg-status-warning text-white": variant === "warning",
          "border-transparent bg-status-error text-white": variant === "error",
          "border-transparent bg-status-info text-white": variant === "info",
          "text-foreground": variant === "outline",
        },
        className
      )}
      {...props}
    />
  )
}

export { Badge }
