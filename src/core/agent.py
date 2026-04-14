"""AXON Agent Loop — Claude tool-use orchestration."""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator
from loguru import logger

from src.config import config
from src.core.tools import TOOL_SCHEMAS, ToolDispatcher

SYSTEM_PROMPT = """\
You are AXON, a Jarvis-like AI assistant running locally on this Windows PC.
You have full control of the computer and can see the screen, click, type, run code, manage files, search the web, and remember things long-term.

BEHAVIOR:
- Before clicking anything, call take_screenshot to see the current screen and confirm coordinates.
- Narrate what you're doing in first person as you act: "I'll open Chrome now...", "Clicking the Save button..."
- Keep narration concise — it's spoken aloud. Don't pad with filler.
- When writing code, show a brief plan then write it.
- If a tool returns an error, diagnose and retry before giving up.
- Never ask for permission for actions the user has already requested — just do them.
- Use remember() for anything the user explicitly asks you to remember.
- You can write complete programs, scripts, and applications from scratch.

CAPABILITIES REMINDER:
- take_screenshot → see current screen
- click/double_click/right_click/drag_to/scroll → mouse control
- type_text/press_key → keyboard control
- find_window/focus_window/move_window/open_app/close_window → window management
- read_file/write_file/list_directory/move_file/delete_file/create_directory → file system
- run_python → execute Python code (full access, can import any library)
- run_command → run shell/PowerShell commands
- search_web → DuckDuckGo search
- remember/recall → long-term memory
"""


class AxonAgent:
    def __init__(self, dispatcher: ToolDispatcher) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=config.claude.api_key)
        self._dispatcher = dispatcher
        self._messages: list[dict] = []

    def clear_history(self) -> None:
        self._messages = []

    async def run(
        self,
        user_text: str,
        screenshot_b64: str | None = None,
    ) -> AsyncGenerator[tuple[str, str | dict], None]:
        """
        Async generator yielding (event_type, data):
          ("text", str)            — streaming text from Claude
          ("tool_start", dict)     — {name, inputs}
          ("tool_end", dict)       — {name, success, output_preview}
          ("done", str)            — final full response text
          ("error", str)           — error occurred
        """
        # Build user message
        content = []
        if screenshot_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": screenshot_b64},
            })
        content.append({"type": "text", "text": user_text})
        self._messages.append({"role": "user", "content": content})
        self._trim_history()

        accumulated_response = []

        for iteration in range(config.claude.max_tool_iterations):
            text_chunks = []
            tool_use_blocks = []
            current_tool: dict = {}
            current_block_type: str | None = None

            # ── Stream from Claude ───────────────────────────────────────────
            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def _stream():
                try:
                    with self._client.messages.stream(
                        model=config.claude.model,
                        max_tokens=config.claude.max_tokens,
                        system=SYSTEM_PROMPT,
                        tools=TOOL_SCHEMAS,
                        messages=self._messages,
                    ) as stream:
                        for event in stream:
                            loop.call_soon_threadsafe(queue.put_nowait, event)
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, ("__error__", str(exc)))
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            loop.run_in_executor(None, _stream)

            while True:
                event = await queue.get()
                if event is None:
                    break
                if isinstance(event, tuple) and event[0] == "__error__":
                    yield ("error", event[1])
                    return

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
                        accumulated_response.append(delta.text)
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

            # ── Build assistant content ──────────────────────────────────────
            assistant_content = []
            if text_chunks:
                assistant_content.append({"type": "text", "text": "".join(text_chunks)})
            for tu in tool_use_blocks:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tu["id"],
                    "name": tu["name"],
                    "input": tu["input"],
                })
            if assistant_content:
                self._messages.append({"role": "assistant", "content": assistant_content})

            if not tool_use_blocks:
                # No tools → end_turn, we're done
                yield ("done", "".join(accumulated_response))
                return

            # ── Execute tools ────────────────────────────────────────────────
            tool_results = []
            for tu in tool_use_blocks:
                yield ("tool_start", {"name": tu["name"], "inputs": tu["input"]})
                result = await self._dispatcher.dispatch(tu["name"], tu["input"])
                preview = str(result.output)[:80] if result.output else result.error[:80]
                yield ("tool_end", {"name": tu["name"], "success": result.success, "preview": preview})

                if result.is_image:
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
                    out_str = str(result.output) if result.success else f"ERROR: {result.error}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": out_str,
                    })

            self._messages.append({"role": "user", "content": tool_results})

        yield ("error", "Max tool iterations reached")

    def _trim_history(self) -> None:
        """Strip images from older messages and cap length."""
        max_msgs = 40
        # Remove images from old messages to save tokens
        for msg in self._messages[:-6]:
            if isinstance(msg.get("content"), list):
                msg["content"] = [
                    b for b in msg["content"]
                    if not (isinstance(b, dict) and b.get("type") == "image")
                ]
        if len(self._messages) > max_msgs:
            # Keep the first message (user context) and last N
            self._messages = self._messages[-max_msgs:]
