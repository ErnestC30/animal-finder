import { memo, useEffect, useState, type ReactNode } from "react";
import { CheckIcon, CopyIcon, RotateCcwIcon } from "lucide-react";

import { Bubble, BubbleContent } from "@/components/ui/bubble";
import { Button } from "@/components/ui/button";
import {
  Message,
  MessageContent,
  MessageFooter,
} from "@/components/ui/message";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { MarkdownContent } from "@/components/markdown";
import type { ChatMessage as ChatMessageType } from "@/lib/chat";

type ChatMessageProps = {
  message: ChatMessageType;
  onRetry?: (id: string) => void;
};

// Memoized so a streamed token only re-renders the message it updates: unchanged
// messages keep their object identity, and onRetry is undefined while streaming.
export const ChatMessage = memo(function ChatMessage({
  message,
  onRetry,
}: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <Message align="end">
        <MessageContent>
          <Bubble align="end" variant="muted">
            <BubbleContent className="whitespace-pre-wrap">
              {message.content}
            </BubbleContent>
          </Bubble>
        </MessageContent>
      </Message>
    );
  }

  const isStreaming = message.status === "streaming";
  const isError = message.status === "error";

  return (
    <Message>
      <MessageContent>
        {isError ? (
          <Bubble variant="destructive">
            <BubbleContent>
              {message.error ??
                "Something went wrong while generating a response."}
            </BubbleContent>
          </Bubble>
        ) : message.content ? (
          <Bubble variant="ghost">
            <BubbleContent>
              <MarkdownContent>{message.content}</MarkdownContent>
            </BubbleContent>
          </Bubble>
        ) : isStreaming ? (
          <ThinkingIndicator />
        ) : null}
        {message.stopped && (
          <p className="text-xs text-muted-foreground">Response stopped</p>
        )}
        {!isStreaming && (
          <MessageFooter className="gap-0.5 px-0">
            {!isError && message.content && (
              <CopyAction text={message.content} />
            )}
            {onRetry && (
              <MessageAction label="Retry" onClick={() => onRetry(message.id)}>
                <RotateCcwIcon />
              </MessageAction>
            )}
          </MessageFooter>
        )}
      </MessageContent>
    </Message>
  );
});

function ThinkingIndicator() {
  return (
    <div
      role="status"
      aria-label="Agent is thinking"
      className="flex h-5 items-center gap-1"
    >
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="size-1.5 animate-thinking rounded-full bg-muted-foreground"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  );
}

function MessageAction({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={label}
          onClick={onClick}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function CopyAction({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timeout = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timeout);
  }, [copied]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch (error) {
      console.error("Failed to copy message", error);
    }
  };

  return (
    <MessageAction label={copied ? "Copied" : "Copy"} onClick={copy}>
      {copied ? <CheckIcon /> : <CopyIcon />}
    </MessageAction>
  );
}
