import { useState } from "react"

import { ChatBar } from "@/components/chat-bar"
import { ChatLog } from "@/components/chat-log"
import { NewSessionButton } from "@/components/new-session-button"
import { ThemeToggle } from "@/components/theme-toggle"
import { useChat } from "@/hooks/use-chat"

function App() {
  const { messages, status, send, retry, stop, reset } = useChat()
  const hasMessages = messages.length > 0
  // Bumped on each new session to remount ChatBar, clearing any unsent draft.
  const [sessionKey, setSessionKey] = useState(0)

  const startNewSession = () => {
    setSessionKey((k) => k + 1)
    reset()
  }

  return (
    <main className="flex h-svh flex-col bg-background">
      {hasMessages ? (
        <ChatLog messages={messages} status={status} onRetry={retry} />
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            Animal Finder
          </h1>
          <p className="text-muted-foreground">
            Describe an animal and we'll help you find it.
          </p>
        </div>
      )}
      <div className="mx-auto w-full max-w-2xl px-4 pb-6">
        <ChatBar
          key={sessionKey}
          onSubmit={send}
          streaming={status === "streaming"}
          onStop={stop}
        />
        <div className="mt-2 flex items-center justify-center gap-1">
          <NewSessionButton onConfirm={startNewSession} />
          <ThemeToggle />
        </div>
      </div>
    </main>
  )
}

export default App
