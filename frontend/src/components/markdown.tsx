import Markdown, { type Components } from "react-markdown"

import { cn } from "@/lib/utils"

// react-markdown renders unstyled HTML. These overrides style it with theme tokens.
const components: Components = {
  p: ({ className, ...props }) => (
    <p className={cn("leading-relaxed", className)} {...props} />
  ),
  h1: ({ className, ...props }) => (
    <h1 className={cn("text-lg font-semibold", className)} {...props} />
  ),
  h2: ({ className, ...props }) => (
    <h2 className={cn("text-base font-semibold", className)} {...props} />
  ),
  h3: ({ className, ...props }) => (
    <h3 className={cn("text-sm font-semibold", className)} {...props} />
  ),
  ul: ({ className, ...props }) => (
    <ul className={cn("list-disc space-y-1 pl-5", className)} {...props} />
  ),
  ol: ({ className, ...props }) => (
    <ol className={cn("list-decimal space-y-1 pl-5", className)} {...props} />
  ),
  a: ({ className, ...props }) => (
    <a
      className={cn("font-medium underline underline-offset-4", className)}
      target="_blank"
      rel="noreferrer"
      {...props}
    />
  ),
  blockquote: ({ className, ...props }) => (
    <blockquote
      className={cn("border-l-2 pl-3 text-muted-foreground italic", className)}
      {...props}
    />
  ),
  code: ({ className, ...props }) => (
    <code
      className={cn(
        "rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]",
        className
      )}
      {...props}
    />
  ),
  pre: ({ className, ...props }) => (
    <pre
      className={cn(
        "overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs [&>code]:bg-transparent [&>code]:p-0",
        className
      )}
      {...props}
    />
  ),
  hr: ({ className, ...props }) => (
    <hr className={cn("border-border", className)} {...props} />
  ),
}

export function MarkdownContent({
  children,
  className,
}: {
  children: string
  className?: string
}) {
  return (
    <div className={cn("flex flex-col gap-3 text-sm", className)}>
      <Markdown components={components}>{children}</Markdown>
    </div>
  )
}
