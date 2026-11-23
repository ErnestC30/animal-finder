import { useCallback, useEffect, useRef, useState } from "react";

import { createMessageId, type ChatMessage, type ChatStatus } from "@/lib/chat";
import { RateLimitError, resetSession, streamChat } from "@/lib/stream-chat";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const abortRef = useRef<AbortController | null>(null);
  // Pending session reset; chat requests wait on it so they never go out with the old cookie.
  const resetRef = useRef<Promise<void>>(Promise.resolve());

  // The history lives only in memory, so a page load starts a fresh server session too
  // (otherwise the session_id cookie would outlive the conversation it belongs to).
  useEffect(() => {
    resetRef.current = resetSession().catch((error) => console.error(error));
  }, []);

  const updateMessage = useCallback(
    (id: string, patch: Partial<ChatMessage>) =>
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...patch } : m)),
      ),
    [],
  );

  /** Streams a reply to `prompt` into a new assistant message. */
  const runAssistantTurn = useCallback(
    async (prompt: string) => {
      const assistantId = createMessageId();
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          status: "streaming",
        },
      ]);
      setStatus("streaming");

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await resetRef.current;
        await streamChat(
          prompt,
          (text) => updateMessage(assistantId, { content: text }),
          controller.signal,
        );
        updateMessage(assistantId, { status: "done" });
      } catch (error) {
        if (controller.signal.aborted) {
          // stopped by the user: keep the partial reply
          updateMessage(assistantId, { status: "done", stopped: true });
        } else {
          console.error(error);
          updateMessage(assistantId, {
            status: "error",
            error: error instanceof RateLimitError ? error.message : undefined,
          });
        }
      } finally {
        // a newer turn may have started since (e.g. after a reset); leave its state alone
        if (abortRef.current === controller) {
          abortRef.current = null;
          setStatus("idle");
        }
      }
    },
    [updateMessage],
  );

  const send = useCallback(
    (prompt: string) => {
      if (status === "streaming") return;
      setMessages((prev) => [
        ...prev,
        { id: createMessageId(), role: "user", content: prompt },
      ]);
      void runAssistantTurn(prompt);
    },
    [runAssistantTurn, status],
  );

  /**
   * Removes the assistant message `id` and asks again with the user prompt before it.
   * Only the most recent message can be retried; older replies are ignored.
   */
  const retry = useCallback(
    (id: string) => {
      if (status === "streaming") return;
      const last = messages.at(-1);
      if (last?.id !== id || last.role !== "assistant") return;
      const prompt = messages.findLast((m) => m.role === "user")?.content;
      if (!prompt) return;
      setMessages((prev) => prev.filter((m) => m.id !== id));
      void runAssistantTurn(prompt);
    },
    [messages, runAssistantTurn, status],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  /** Stops any in-flight reply, ends the server session, and clears the history. */
  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    // clear before the request: a message sent while it is pending belongs to the new
    // session, and runAssistantTurn waits on resetRef so it still gets the new cookie
    setMessages([]);
    setStatus("idle");
    resetRef.current = resetSession().catch((error) => console.error(error));
  }, []);

  return { messages, status, send, retry, stop, reset };
}
