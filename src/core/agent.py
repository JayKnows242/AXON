"""AXON Agent — routes between fast (Haiku) and smart (Sonnet) Claude models."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from loguru import logger

from src.config import config
from src.core.tools import ToolDispatcher, TOOL_SCHEMAS

# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are AXON, a Jarvis-like AI assistant on this Windows PC. You control the computer directly.

RESPONSE STYLE:
- Keep all replies short — 1 sentence for simple tasks, 2-3 sentences max for complex ones.
- Do NOT explain what you are about to do at length. Just do it, then confirm briefly.

TASK RULES:
- Complete the FULL task — never stop after one tool call if more steps are needed.
- To type in any app: open_app → focus_window(exact title from open_app result) → take_screenshot → click text area → type_text.
- open_app returns the exact window title in quotes — copy it exactly into focus_window.
- Never type without first focusing the target window with focus_window.
- Before clicking UI elements, take_screenshot to confirm coordinates.
- If a tool errors, try an alternative — do not give up.
- Never ask permission for things the user already requested.
- Use list_windows/find_window to locate apps, not guessed coordinates.
- Use remember() only when the user explicitly asks to save something.
- Write complete, working code when asked. Test with run_python if asked to run it.

EXAMPLES (study these — match this exact pattern):

Example 1 — "open notepad and type hello world"
Assistant: Opening Notepad and typing now.
[tool: open_app("notepad")]
→ result: "Opened: 'Untitled - Notepad' — use focus_window('Untitled - Notepad') to activate"
[tool: focus_window("Untitled - Notepad")]
→ result: "Focused: Untitled - Notepad"
[tool: take_screenshot()]
→ result: <image>
[tool: click(x=640, y=400)]   ← click centre of the text area visible in screenshot
→ result: "Clicked (640, 400)"
[tool: type_text("hello world")]
→ result: "Typed: hello world"
Done — typed "hello world" in Notepad.

Example 2 — "what is on my screen?"
Assistant: Let me look.
[tool: take_screenshot()]
→ result: <image>
I can see [describe what is visible].

Example 3 — "open chrome and go to youtube"
Assistant: Opening Chrome and navigating to YouTube.
[tool: open_app("chrome")]
→ result: "Opened: 'New Tab - Google Chrome' — use focus_window('New Tab - Google Chrome') to activate"
[tool: focus_window("New Tab - Google Chrome")]
→ result: "Focused: New Tab - Google Chrome"
[tool: take_screenshot()]
→ result: <image>
[tool: click(x=640, y=52)]   ← click the address bar
[tool: type_text("youtube.com\n")]
Done — Chrome is navigating to YouTube.

Example 4 — "list my open windows"
Assistant: Checking now.
[tool: list_windows()]
→ result: ["Untitled - Notepad", "Task Manager", ...]
Open windows: Notepad, Task Manager, ...
"""

# Keywords that warrant routing to the smarter model
_SMART_KEYWORDS = {
    "architecture", "design", "refactor", "explain", "analyze", "analyse",
    "debug", "why is", "how does", "write a", "build a", "create a",
    "implement", "algorithm", "optimize", "review", "compare", "difference",
    "complex", "advanced", "research", "summarize", "summarise",
}


def _needs_smart_model(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _SMART_KEYWORDS)


# ─────────────────────────────────────────────────────────────────────────────
# Main agent
# ─────────────────────────────────────────────────────────────────────────────

class AxonAgent:
    def __init__(self, dispatcher: ToolDispatcher) -> None:
        self._dispatcher = dispatcher
        self._history: list[dict] = []   # Anthropic message format

    def clear_history(self) -> None:
        self._history.clear()

    async def run(self, user_text: str) -> AsyncGenerator:
        from src.ui.settings_dialog import load_settings
        settings = load_settings()

        if not config.claude.api_key:
            yield ("error", "No Anthropic API key set. Open Settings and add your key.")
            return

        use_smart = settings.get("use_smart_for_complex", True) and _needs_smart_model(user_text)
        model = config.claude.smart_model if use_smart else config.claude.fast_model
        logger.info(f"→ {'Smart' if use_smart else 'Fast'} model ({model})")

        self._history.append({"role": "user", "content": user_text})
        self._trim_history()

        async for event in self._run_claude(model):
            yield event

    # ── Claude backend ────────────────────────────────────────────────────────

    async def _run_claude(self, model: str) -> AsyncGenerator:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed — run: pip install anthropic")

        client = anthropic.Anthropic(api_key=config.claude.api_key)

        for _ in range(config.claude.max_tool_iterations):
            text_chunks: list[str] = []
            tool_use_blocks: list[dict] = []
            current_tool: dict = {}
            current_block_type: str | None = None

            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def _stream_sync():
                try:
                    with client.messages.stream(
                        model=model,
                        max_tokens=config.claude.max_tokens,
                        system=SYSTEM_PROMPT,
                        tools=TOOL_SCHEMAS,
                        messages=self._history,
                    ) as stream:
                        for event in stream:
                            loop.call_soon_threadsafe(queue.put_nowait, event)
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, ("__error__", str(exc)))
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            loop.run_in_executor(None, _stream_sync)

            while True:
                event = await queue.get()
                if event is None:
                    break
                if isinstance(event, tuple) and event[0] == "__error__":
                    raise RuntimeError(event[1])

                etype = getattr(event, "type", None)
                if etype == "content_block_start":
                    block = event.content_block
                    current_block_type = block.type
                    if block.type == "tool_use":
                        current_tool = {"id": block.id, "name": block.name, "_json": ""}
                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        text_chunks.append(delta.text)
                        yield ("text", delta.text)
                    elif delta.type == "input_json_delta":
                        current_tool["_json"] = current_tool.get("_json", "") + delta.partial_json
                elif etype == "content_block_stop":
                    if current_block_type == "tool_use":
                        try:
                            current_tool["input"] = json.loads(current_tool.pop("_json", "{}"))
                        except json.JSONDecodeError:
                            current_tool["input"] = {}
                        tool_use_blocks.append(dict(current_tool))
                    current_block_type = None
                    current_tool = {}

            # Append assistant turn to history
            text_content = "".join(text_chunks)
            anthropic_content: list[dict] = []
            if text_content:
                anthropic_content.append({"type": "text", "text": text_content})
            for tu in tool_use_blocks:
                anthropic_content.append({
                    "type": "tool_use",
                    "id": tu["id"],
                    "name": tu["name"],
                    "input": tu["input"],
                })
            self._history.append({
                "role": "assistant",
                "content": anthropic_content if anthropic_content else text_content,
            })

            if not tool_use_blocks:
                yield ("done", text_content)
                return

            # Execute tools
            tool_results: list[dict] = []
            for tu in tool_use_blocks:
                yield ("tool_start", {"name": tu["name"], "inputs": tu["input"]})
                result = await self._dispatcher.dispatch(tu["name"], tu["input"])
                yield ("tool_end", {"name": tu["name"], "success": result.success})

                if result.is_image and result.output:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": [{
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": result.output,
                            },
                        }],
                    })
                else:
                    content_str = str(result.output) if result.success else f"ERROR: {result.error}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": content_str,
                    })

            self._history.append({"role": "user", "content": tool_results})

        yield ("error", "Max tool iterations reached")

    # ── History management ────────────────────────────────────────────────────

    def _trim_history(self) -> None:
        max_msgs = 40
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]
