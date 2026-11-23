export type ChatRole = "user" | "assistant";

export type ChatMessageStatus = "streaming" | "done" | "error";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  status?: ChatMessageStatus;
  /** User-facing explanation shown when `status` is "error"; a generic message otherwise. */
  error?: string;
  /** True when the user stopped the reply before it finished. */
  stopped?: boolean;
};

export type ChatStatus = "idle" | "streaming";

export const createMessageId = () => crypto.randomUUID();
