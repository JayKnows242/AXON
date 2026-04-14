"""AXON Agent — smart routing between local Ollama and cloud Claude."""
from __future__ import annotations

import asyncio
import json
import socket
from typing import AsyncGenerator

import re

from loguru import logger

from src.config import config
from src.core.tools import ToolDispatcher, TOOL_SCHEMAS, get_openai_tools

# Matches tool calls the model writes as plain text instead of structured calls
# e.g.  {"name": "click", "arguments": {"x": 100, "y": 200}}
_TEXT_TOOL_RE = re.compile(
    r'\{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{[^{}]*\})\s*\}',
    re.DOTALL,
)

# ─────────────────────────────────────────────────────────────────────────────
# System prompt (shared by both backends)
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are AXON, a Jarvis-like AI assistant on this Windows PC. You control the computer directly.

RESPONSE STYLE:
- Keep all replies short — 1 sentence for simple tasks, 2-3 sentences max for complex ones.
- Do NOT explain what you are about to do at length. Just do it, then confirm briefly.
- Bad: "Sure! I'll open Notepad and type your text. Let me first open Notepad, then focus the window..."
- Good: "Opening Notepad and typing now." [then use tools]

TASK RULES:
- Complete the FULL task — never stop after one tool call if more steps are needed.
- To type in any app: open_app → take_screenshot → focus_window → click in the text area → type_text.
- Never type without first focusing the target window with focus_window.
- Before clicking UI elements, take_screenshot to confirm coordinates.
- If a tool errors, try an alternative — do not give up.
- Never ask permission for things the user already requested.
- Use list_windows/find_window to locate apps, not guessed coordinates.
- Use remember() only when the user explicitly asks to save something.
- Write complete, working code when asked. Test with run_python if asked to run it.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _has_internet() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 53))
        s.close()
        return True
    except OSError:
        return False


def _ollama_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(base_url=config.ollama.base_url, api_key="ollama")


# ─────────────────────────────────────────────────────────────────────────────
# Router — asks the small local model to classify task complexity
# ─────────────────────────────────────────────────────────────────────────────

async def _classify_task(text: str) -> str:
    """Returns 'local' or 'cloud'. Uses router_model (tiny, fast)."""
    try:
        client = _ollama_client()
        resp = await client.chat.completions.create(
            model=config.ollama.router_model,
            messages=[{
                "role": "user",
                "content": (
                    "You are a task router. Classify the task below.\n"
                    "Reply with ONE word only: LOCAL or CLOUD\n\n"
                    "LOCAL = PC control, clicking, typing, file ops, web search, "
                    "simple scripts, basic questions\n"
                    "CLOUD = complex software architecture, hard debugging, advanced "
                    "reasoning, lengthy analysis, anything you are not confident about\n\n"
                    f"Task: {text}"
                ),
            }],
            max_tokens=3,
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip().upper()
        decision = "cloud" if "CLOUD" in answer else "local"
        logger.debug(f"Router → {decision}  ({text[:60]})")
        return decision
    except Exception as e:
        logger.warning(f"Router failed ({e}), defaulting to local")
        return "local"


# ─────────────────────────────────────────────────────────────────────────────
# History conversion — OpenAI format → Anthropic format
# (shared history is kept in OpenAI format; converted when calling Claude)
# ─────────────────────────────────────────────────────────────────────────────

def _to_anthropic_messages(history: list[dict]) -> list[dict]:
    result: list[dict] = []
    i = 0
    while i < len(history):
        msg = history[i]
        role = msg["role"]

        if role == "user":
            result.append({"role": "user", "content": msg.get("content", "")})
            i += 1

        elif role == "assistant":
            anthropic_content: list[dict] = []
            text = msg.get("content") or ""
            if text:
                anthropic_content.append({"type": "text", "text": text})
            for tc in msg.get("tool_calls", []):
                try:
                    inputs = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    inputs = {}
                anthropic_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": inputs,
                })
            result.append({
                "role": "assistant",
                "content": anthropic_content if anthropic_content else text,
            })
            i += 1

        elif role == "tool":
            # Group consecutive tool results into one user message (Anthropic requirement)
            tool_results: list[dict] = []
            while i < len(history) and history[i]["role"] == "tool":
                tm = history[i]
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tm["tool_call_id"],
                    "content": str(tm.get("content", "")),
                })
                i += 1
            result.append({"role": "user", "content": tool_results})

        else:
            i += 1

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main agent — orchestrates routing and both backends
# ─────────────────────────────────────────────────────────────────────────────

class AxonAgent:
    def __init__(self, dispatcher: ToolDispatcher) -> None:
        self._dispatcher = dispatcher
        self._history: list[dict] = []   # OpenAI format, shared across backends

    def clear_history(self) -> None:
        self._history.clear()

    async def run(self, user_text: str) -> AsyncGenerator:
        from src.ui.settings_dialog import load_settings
        settings = load_settings()

        self._history.append({"role": "user", "content": user_text})
        self._trim_history()

        use_cloud = settings.get("use_cloud_for_complex", True)
        cloud_ok = use_cloud and bool(config.claude.api_key) and _has_internet()

        if cloud_ok:
            decision = await _classify_task(user_text)
        else:
            decision = "local"

        if decision == "cloud":
            logger.info("→ Cloud (Claude)")
            try:
                async for event in self._run_cloud():
                    yield event
                return
            except Exception as e:
                logger.warning(f"Cloud failed, falling back to local: {e}")
                yield ("text", "\n[Switching to local model…]\n")

        logger.info("→ Local (Ollama)")
        async for event in self._run_local():
            yield event

    # ── Local backend (Ollama via OpenAI-compatible API) ─────────────────────

    async def _run_local(self) -> AsyncGenerator:
        tools = get_openai_tools()
        client = _ollama_client()

        for _ in range(config.claude.max_tool_iterations):
            text_acc = ""
            tool_calls_acc: dict[int, dict] = {}

            try:
                stream = await client.chat.completions.create(
                    model=config.ollama.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *self._history,
                    ],
                    tools=tools,
                    tool_choice="auto",
                    stream=True,
                    temperature=config.claude.temperature,
                    max_tokens=config.claude.max_tokens,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        text_acc += delta.content
                        yield ("text", delta.content)
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                            if tc.id:
                                tool_calls_acc[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_acc[idx]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tool_calls_acc[idx]["arguments"] += tc.function.arguments

            except Exception as e:
                logger.error(f"Local model error: {e}")
                yield ("error", str(e))
                return

            # Fallback: model wrote tool calls as plain JSON text instead of
            # using structured function calling (common with qwen2.5-coder)
            if not tool_calls_acc and text_acc:
                for i, m in enumerate(_TEXT_TOOL_RE.finditer(text_acc)):
                    try:
                        json.loads(m.group(2))   # validate args
                        tool_calls_acc[i] = {
                            "id": f"txt_{i}",
                            "name": m.group(1),
                            "arguments": m.group(2),
                        }
                    except json.JSONDecodeError:
                        pass
                if tool_calls_acc:
                    # Strip the raw JSON blobs from the displayed text
                    clean = _TEXT_TOOL_RE.sub("", text_acc).strip()
                    text_acc = clean

            # Append assistant turn to shared history
            assistant_msg: dict = {"role": "assistant", "content": text_acc or ""}
            if tool_calls_acc:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for _, tc in sorted(tool_calls_acc.items())
                ]
            self._history.append(assistant_msg)

            if not tool_calls_acc:
                yield ("done", text_acc)
                return

            # Execute tools
            for _, tc in sorted(tool_calls_acc.items()):
                name = tc["name"]
                try:
                    inputs = json.loads(tc["arguments"] or "{}")
                except json.JSONDecodeError:
                    inputs = {}

                yield ("tool_start", {"name": name, "inputs": inputs})
                result = await self._dispatcher.dispatch(name, inputs)
                yield ("tool_end", {"name": name, "success": result.success})

                if result.is_image and result.output:
                    content = "[Screenshot captured. Use list_windows/find_window to navigate UI.]"
                else:
                    content = str(result.output) if result.success else f"ERROR: {result.error}"

                self._history.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": content,
                })

        yield ("error", "Max tool iterations reached")

    # ── Cloud backend (Anthropic / Claude) ────────────────────────────────────

    async def _run_cloud(self) -> AsyncGenerator:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed")

        client = anthropic.Anthropic(api_key=config.claude.api_key)
        # Build Anthropic-format message list from shared history
        anthropic_messages = _to_anthropic_messages(self._history)

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
                        model=config.claude.model,
                        max_tokens=config.claude.max_tokens,
                        system=SYSTEM_PROMPT,
                        tools=TOOL_SCHEMAS,
                        messages=anthropic_messages,
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

            # Append assistant turn to shared history (OpenAI format)
            text_content = "".join(text_chunks)
            assistant_msg: dict = {"role": "assistant", "content": text_content or ""}
            if tool_use_blocks:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tu["id"],
                        "type": "function",
                        "function": {
                            "name": tu["name"],
                            "arguments": json.dumps(tu["input"]),
                        },
                    }
                    for tu in tool_use_blocks
                ]
            self._history.append(assistant_msg)

            # Keep Anthropic-format list in sync for next iteration
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
            if anthropic_content:
                anthropic_messages.append({"role": "assistant", "content": anthropic_content})

            if not tool_use_blocks:
                yield ("done", text_content)
                return

            # Execute tools
            anthropic_tool_results: list[dict] = []
            for tu in tool_use_blocks:
                yield ("tool_start", {"name": tu["name"], "inputs": tu["input"]})
                result = await self._dispatcher.dispatch(tu["name"], tu["input"])
                yield ("tool_end", {"name": tu["name"], "success": result.success})

                if result.is_image and result.output:
                    content_str = "[Screenshot captured]"
                    anthropic_tool_results.append({
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
                    anthropic_tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": content_str,
                    })

                # Shared history (OpenAI format)
                self._history.append({
                    "role": "tool",
                    "tool_call_id": tu["id"],
                    "content": content_str,
                })

            anthropic_messages.append({"role": "user", "content": anthropic_tool_results})

        yield ("error", "Max tool iterations reached")

    # ── History management ────────────────────────────────────────────────────

    def _trim_history(self) -> None:
        """Cap history length to avoid ballooning token counts."""
        max_msgs = 40
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]
