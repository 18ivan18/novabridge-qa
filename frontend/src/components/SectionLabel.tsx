import type { ComponentProps } from "react";

import { cn } from "cn";

/** The small uppercase heading above a list, such as "Sources" or "Document library". */
export function SectionLabel({ className, ...props }: ComponentProps<"h2">) {
  return (
    <h2
      className={cn("text-xs font-semibold tracking-[0.06em] text-muted-foreground uppercase", className)}
      {...props}
    />
  );
}
