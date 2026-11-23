/** Ends the server-side session: clears cached search filters and the `session_id` cookie. */
export async function resetSession(): Promise<void> {
  const response = await fetch("/api/session/reset", { method: "POST" });
  if (!response.ok) {
    throw new Error(`Session reset failed with status ${response.status}`);
  }
}

/** Thrown when the backend rejects a chat request with 429 Too Many Requests. */
export class RateLimitError extends Error {
  constructor() {
    super(
      "You've sent too many requests in a short time. Please try again later.",
    );
    this.name = "RateLimitError";
  }
}

type SseEvent = { event: string; data: string };

/** Parses one SSE event block (the lines between blank-line separators). */
function parseEvent(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split(/\r\n|\n|\r/)) {
    if (line === "" || line.startsWith(":")) continue; // comments, e.g. keep-alive `: ping`
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  // per the SSE spec, events without a data field are not dispatched
  return data.length > 0 ? { event, data: data.join("\n") } : null;
}

/**
 * Streams the agent's reply to `prompt` from `POST /chat/stream`, calling `onText` with the
 * full reply text so far (the backend sends cumulative text, not deltas).
 *
 * Resolves when the backend sends `done`. Rejects on HTTP errors, an `error` event, or a
 * stream that closes without `done`. Aborting `signal` rejects with an `AbortError`.
 */
export async function streamChat(
  prompt: string,
  onText: (text: string) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ prompt }),
  });
  if (response.status === 429) {
    throw new RateLimitError();
  }
  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  /** Handles one event; returns true once the stream is finished. */
  const handle = (block: string): boolean => {
    const parsed = parseEvent(block);
    if (!parsed) return false;
    switch (parsed.event) {
      case "message":
        onText(JSON.parse(parsed.data) as string);
        return false;
      case "error":
        throw new Error(JSON.parse(parsed.data) as string);
      case "done":
        return true;
      default:
        return false;
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      const blocks = buffer.split(/\r\n\r\n|\n\n|\r\r/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        if (handle(block)) return;
      }
    }
    if (buffer && handle(buffer)) return;
  } finally {
    reader.cancel().catch(() => {});
  }

  throw new Error("Stream ended unexpectedly");
}
