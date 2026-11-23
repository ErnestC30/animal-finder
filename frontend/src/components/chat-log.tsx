import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import { ChatMessage } from "@/components/chat-message"
import type { ChatMessage as ChatMessageType, ChatStatus } from "@/lib/chat"
import { cn } from "@/lib/utils"

type ChatLogProps = {
  messages: ChatMessageType[]
  status: ChatStatus
  onRetry?: (id: string) => void
  className?: string
}

/**
 * Scrollable conversation. Fills its parent, so render it inside a height-constrained container.
 * User turns are scroll anchors: a new question settles near the top and the reply streams below it.
 */
export function ChatLog({ messages, status, onRetry, className }: ChatLogProps) {
  return (
    <MessageScrollerProvider autoScroll defaultScrollPosition="last-anchor">
      <MessageScroller className={cn("min-h-0 flex-1", className)}>
        <MessageScrollerViewport>
          <MessageScrollerContent
            aria-busy={status === "streaming"}
            className="mx-auto w-full max-w-2xl px-4 py-6"
          >
            {messages.map((message, index) => (
              <MessageScrollerItem
                key={message.id}
                messageId={message.id}
                scrollAnchor={message.role === "user"}
              >
                <ChatMessage
                  message={message}
                  // only the latest reply can be retried
                  onRetry={
                    status === "idle" && index === messages.length - 1
                      ? onRetry
                      : undefined
                  }
                />
              </MessageScrollerItem>
            ))}
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <MessageScrollerButton />
      </MessageScroller>
    </MessageScrollerProvider>
  )
}
