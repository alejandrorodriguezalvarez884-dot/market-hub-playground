// The chat: the reader says what they want to see, and the board changes. The conversation lives
// in the page, like the board: a reload starts both again.
import { chat, type ChatOut, type Turn, type Widget } from "./api";
import { add, h, mark } from "./dom";

export type Chat = { send(text: string): void };

export function createChat(host: HTMLElement, opts: { board: () => Widget[]; apply: (out: ChatOut) => void; limit: number }): Chat {
  const turns: Turn[] = [];
  let busy = false;

  const log = h("ol", "chat-log");
  log.setAttribute("aria-live", "polite");
  const input = h("textarea", "field resize-none !border-0 !bg-transparent !px-0 !py-1.5 leading-snug");
  input.rows = 1;
  input.maxLength = opts.limit;
  input.placeholder = "A chart, a comparison, a table…";
  input.setAttribute("aria-label", "What do you want to see?");
  const go = h("button", "btn btn-primary h-8 flex-none px-3 text-[13px]", "Show");
  go.type = "submit";
  const form = add(h("form", "flex items-end gap-2 rounded-[3px] border border-line-strong px-3 py-1.5 focus-within:border-ink-strong"), input, go);
  host.replaceChildren(log, add(h("div", "flex-none p-3 xl:p-4"), form));

  // The box grows with what is written, up to a few lines.
  const fit = () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  };

  function line(role: Turn["role"] | "error" | "wait", text: string, notes: string[] = []): HTMLElement {
    let el: HTMLElement;
    if (role === "user") el = add(h("li", "flex justify-end"), h("p", "max-w-[85%] whitespace-pre-wrap rounded-[3px] bg-raised px-3 py-2 text-ink-strong", text));
    else {
      const said = add(h("div", "min-w-0"),
        role === "wait" ? add(h("p", "flex h-[1.5em] items-center gap-1"), h("span", "chat-dot"), h("span", "chat-dot"), h("span", "chat-dot"))
          : h("p", role === "error" ? "text-warn" : "text-ink", text),
        ...notes.map((n) => h("p", "mt-1 text-[12.5px] text-muted", n)));
      el = add(h("li", "flex gap-2.5"), mark("mt-[3px] h-4 w-4 flex-none text-muted"), said);
      if (role === "wait") el.setAttribute("aria-label", "Working on it");
    }
    log.append(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  async function send(text: string) {
    text = text.trim().slice(0, opts.limit);
    if (!text || busy) return;
    busy = go.disabled = true;
    input.value = "";
    fit();
    line("user", text);
    const wait = line("wait", "");
    try {
      // The turns before this one go along, so "make it two years" has something to point at.
      const out = await chat(text, opts.board(), turns.slice(-16));
      wait.remove();
      line("assistant", out.reply, out.problems);
      turns.push({ role: "user", text }, { role: "assistant", text: out.reply });
      opts.apply(out);
    } catch (e) {
      wait.remove();
      line("error", e instanceof Error ? e.message : "Something failed. Try again in a moment.");
      if (!input.value) input.value = text, fit(); // so it can be sent again without typing it
    } finally {
      busy = go.disabled = false;
      if (matchMedia("(pointer: fine)").matches) input.focus();
    }
  }

  form.addEventListener("submit", (e) => (e.preventDefault(), void send(input.value)));
  input.addEventListener("input", fit);
  input.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
    e.preventDefault();
    void send(input.value);
  });
  return { send: (text) => void send(text) };
}
