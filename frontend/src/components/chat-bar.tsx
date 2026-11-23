import { useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUpIcon, SquareIcon } from "lucide-react";

import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextArea,
} from "@/components/ui/input-group";

type ChatBarProps = {
  onSubmit: (query: string) => void;
  /** While true, the submit button becomes a stop button and submitting is blocked. */
  streaming?: boolean;
  onStop?: () => void;
  disabled?: boolean;
  placeholder?: string;
};

export function ChatBar({
  onSubmit,
  streaming = false,
  onStop,
  disabled = false,
  placeholder = "Search for your animal by entering its features, e.g. striped, long neck, lives in the savanna…",
}: ChatBarProps) {
  const [query, setQuery] = useState("");
  const canSubmit = !disabled && !streaming && query.trim().length > 0;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit(query.trim());
    setQuery("");
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    submit();
  };

  // Enter submits; Shift+Enter inserts a newline. Ignore Enter while an IME is composing.
  // While a reply streams, Enter does nothing so the draft is kept for the next turn.
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <InputGroup data-disabled={disabled}>
        <InputGroupTextArea
          aria-label="Describe the animal you're looking for"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={2}
          className="max-h-48"
        />
        <InputGroupAddon align="block-end">
          {streaming ? (
            <InputGroupButton
              type="button"
              variant="default"
              size="icon-sm"
              className="ml-auto rounded-full"
              onClick={onStop}
              aria-label="Stop"
            >
              <SquareIcon className="fill-current" />
            </InputGroupButton>
          ) : (
            <InputGroupButton
              type="submit"
              variant="default"
              size="icon-sm"
              className="ml-auto rounded-full"
              disabled={!canSubmit}
              aria-label="Search"
            >
              <ArrowUpIcon />
            </InputGroupButton>
          )}
        </InputGroupAddon>
      </InputGroup>
    </form>
  );
}
