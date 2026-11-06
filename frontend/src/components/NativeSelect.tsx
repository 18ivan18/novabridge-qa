import type { ComponentProps } from "react";

/** A styled native select: it matches the design and works well on phones and with screen readers. */
export function NativeSelect(props: ComponentProps<"select">) {
  return (
    <select
      className="min-h-11 rounded-lg border border-input bg-card px-3 text-sm text-foreground"
      {...props}
    />
  );
}
