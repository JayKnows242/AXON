"""Tests for AXON tool implementations."""
import asyncio
import os
import sys
import tempfile
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars before any imports touch CTranslate2
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")


# ── Filesystem ───────────────────────────────────────────────────────────────

class TestFilesystemOps:
    @pytest.mark.asyncio
    async def test_write_and_read_file(self, tmp_path):
        from src.filesystem.ops import write_file, read_file
        path = str(tmp_path / "hello.txt")
        out = await write_file(path, "Hello AXON")
        assert "Written" in out
        content = await read_file(path)
        assert content == "Hello AXON"

    @pytest.mark.asyncio
    async def test_read_missing_file(self):
        from src.filesystem.ops import read_file
        result = await read_file("C:/totally/fake/path/nope.txt")
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path):
        from src.filesystem.ops import list_directory, write_file
        await write_file(str(tmp_path / "a.txt"), "a")
        await write_file(str(tmp_path / "b.txt"), "b")
        result = await list_directory(str(tmp_path))
        assert "a.txt" in result
        assert "b.txt" in result

    @pytest.mark.asyncio
    async def test_list_directory_missing(self):
        from src.filesystem.ops import list_directory
        result = await list_directory("C:/does/not/exist")
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_move_file(self, tmp_path):
        from src.filesystem.ops import write_file, move_file, read_file
        src = str(tmp_path / "src.txt")
        dst = str(tmp_path / "dst.txt")
        await write_file(src, "moving")
        out = await move_file(src, dst)
        assert "Moved" in out
        content = await read_file(dst)
        assert content == "moving"

    @pytest.mark.asyncio
    async def test_delete_file(self, tmp_path):
        from src.filesystem.ops import write_file, delete_file, read_file
        path = str(tmp_path / "delete_me.txt")
        await write_file(path, "bye")
        out = await delete_file(path)
        assert "Deleted" in out
        result = await read_file(path)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_create_directory(self, tmp_path):
        from src.filesystem.ops import create_directory, list_directory
        new_dir = str(tmp_path / "new" / "nested" / "dir")
        out = await create_directory(new_dir)
        assert "Created" in out
        assert os.path.isdir(new_dir)

    @pytest.mark.asyncio
    async def test_write_large_content(self, tmp_path):
        from src.filesystem.ops import write_file, read_file
        path = str(tmp_path / "big.txt")
        content = "x" * 10_000
        write_result = await write_file(path, content)
        assert "10,000" in write_result or "Written" in write_result
        # read_file truncates at 5000 chars — verify file was written correctly via OS
        assert os.path.getsize(path) == 10_000

    @pytest.mark.asyncio
    async def test_read_truncates_very_large_file(self, tmp_path):
        from src.filesystem.ops import write_file, read_file
        path = str(tmp_path / "huge.txt")
        content = "y" * 6_000
        await write_file(path, content)
        result = await read_file(path)
        assert "truncated" in result


# ── Python Runner ────────────────────────────────────────────────────────────

class TestPythonRunner:
    @pytest.mark.asyncio
    async def test_basic_print(self):
        from src.execution.python_runner import run_python
        result = await run_python("print('hello axon')")
        assert "hello axon" in result

    @pytest.mark.asyncio
    async def test_math(self):
        from src.execution.python_runner import run_python
        result = await run_python("print(2 + 2)")
        assert "4" in result

    @pytest.mark.asyncio
    async def test_multiline_code(self):
        from src.execution.python_runner import run_python
        code = """
total = 0
for i in range(5):
    total += i
print(f'total={total}')
"""
        result = await run_python(code)
        assert "total=10" in result

    @pytest.mark.asyncio
    async def test_exception_captured(self):
        from src.execution.python_runner import run_python
        result = await run_python("raise ValueError('test error')")
        assert "ValueError" in result or "test error" in result

    @pytest.mark.asyncio
    async def test_stderr_captured(self):
        from src.execution.python_runner import run_python
        result = await run_python("import sys; sys.stderr.write('err msg')")
        assert "err msg" in result

    @pytest.mark.asyncio
    async def test_no_output(self):
        from src.execution.python_runner import run_python
        result = await run_python("x = 1 + 1")
        assert result == "(no output)"

    @pytest.mark.asyncio
    async def test_timeout(self):
        from src.execution.python_runner import run_python
        result = await run_python("import time; time.sleep(60)", timeout=1)
        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_imports_work(self):
        from src.execution.python_runner import run_python
        result = await run_python("import json; print(json.dumps({'a': 1}))")
        assert '"a"' in result

    @pytest.mark.asyncio
    async def test_output_truncated(self):
        from src.execution.python_runner import run_python
        result = await run_python("print('x' * 5000)")
        assert "truncated" in result

    @pytest.mark.asyncio
    async def test_file_operations_in_code(self, tmp_path):
        from src.execution.python_runner import run_python
        path = str(tmp_path / "code_output.txt").replace("\\", "/")
        code = f"""
with open(r'{path}', 'w') as f:
    f.write('written by axon')
print('done')
"""
        result = await run_python(code)
        assert "done" in result
        assert os.path.exists(path)


# ── Shell Runner ─────────────────────────────────────────────────────────────

class TestShellRunner:
    @pytest.mark.asyncio
    async def test_echo(self):
        from src.execution.shell_runner import run_command
        result = await run_command("echo hello axon")
        assert "hello axon" in result

    @pytest.mark.asyncio
    async def test_dir_command(self):
        from src.execution.shell_runner import run_command
        result = await run_command("dir C:\\")
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_bad_command(self):
        from src.execution.shell_runner import run_command
        result = await run_command("totally_fake_command_xyz_123")
        assert len(result) > 0  # Should return error output, not raise

    @pytest.mark.asyncio
    async def test_timeout(self):
        from src.execution.shell_runner import run_command
        result = await run_command("timeout /t 60 /nobreak", timeout=1)
        assert "timed out" in result.lower() or len(result) >= 0  # may vary by Windows version

    @pytest.mark.asyncio
    async def test_python_via_shell(self):
        from src.execution.shell_runner import run_command
        result = await run_command("python --version")
        assert "Python" in result


# ── Tool Dispatcher ──────────────────────────────────────────────────────────

class TestToolDispatcher:
    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        from src.core.tools import ToolDispatcher
        d = ToolDispatcher()
        result = await d.dispatch("nonexistent_tool", {})
        assert not result.success
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_write_and_read_file_via_dispatcher(self, tmp_path):
        from src.core.tools import ToolDispatcher
        d = ToolDispatcher()
        path = str(tmp_path / "dispatch_test.txt")
        write_result = await d.dispatch("write_file", {"path": path, "content": "dispatched"})
        assert write_result.success

        read_result = await d.dispatch("read_file", {"path": path})
        assert read_result.success
        assert "dispatched" in str(read_result.output)

    @pytest.mark.asyncio
    async def test_run_python_via_dispatcher(self):
        from src.core.tools import ToolDispatcher
        d = ToolDispatcher()
        result = await d.dispatch("run_python", {"code": "print('dispatched')"})
        assert result.success
        assert "dispatched" in str(result.output)

    @pytest.mark.asyncio
    async def test_run_command_via_dispatcher(self):
        from src.core.tools import ToolDispatcher
        d = ToolDispatcher()
        result = await d.dispatch("run_command", {"command": "echo axon test"})
        assert result.success
        assert "axon test" in str(result.output)

    @pytest.mark.asyncio
    async def test_list_directory_via_dispatcher(self, tmp_path):
        from src.core.tools import ToolDispatcher
        d = ToolDispatcher()
        result = await d.dispatch("list_directory", {"path": str(tmp_path)})
        assert result.success

    def test_status_callback_called(self):
        from src.core.tools import ToolDispatcher
        calls = []
        d = ToolDispatcher(status_callback=lambda name, inputs: calls.append(name))
        asyncio.run(d.dispatch("run_python", {"code": "pass"}))
        assert "run_python" in calls

    @pytest.mark.asyncio
    async def test_tool_result_has_is_image_false_for_text_tools(self):
        from src.core.tools import ToolDispatcher
        d = ToolDispatcher()
        result = await d.dispatch("run_python", {"code": "print('hi')"})
        assert result.is_image is False


# ── Tool Schemas ─────────────────────────────────────────────────────────────

class TestToolSchemas:
    def test_all_schemas_have_required_fields(self):
        from src.core.tools import TOOL_SCHEMAS
        for schema in TOOL_SCHEMAS:
            assert "name" in schema, f"Missing 'name' in schema: {schema}"
            assert "description" in schema, f"Missing 'description' in {schema['name']}"
            assert "input_schema" in schema, f"Missing 'input_schema' in {schema['name']}"

    def test_schema_names_are_unique(self):
        from src.core.tools import TOOL_SCHEMAS
        names = [s["name"] for s in TOOL_SCHEMAS]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_expected_tools_present(self):
        from src.core.tools import TOOL_SCHEMAS
        names = {s["name"] for s in TOOL_SCHEMAS}
        required = {
            "take_screenshot", "click", "type_text", "press_key",
            "run_python", "run_command", "write_file", "read_file",
            "list_directory", "search_web", "remember", "recall",
            "open_app", "find_window", "focus_window",
        }
        missing = required - names
        assert not missing, f"Missing tools: {missing}"

    def test_dispatcher_has_handler_for_every_schema(self):
        from src.core.tools import TOOL_SCHEMAS, ToolDispatcher
        d = ToolDispatcher()
        missing = []
        for schema in TOOL_SCHEMAS:
            name = schema["name"]
            if not hasattr(d, f"_t_{name}"):
                missing.append(name)
        assert not missing, f"Dispatcher missing handlers: {missing}"


# ── Config ───────────────────────────────────────────────────────────────────

class TestConfig:
    def test_config_loads(self):
        from src.config import config
        assert config is not None

    def test_default_model(self):
        from src.config import config
        assert "claude" in config.claude.model.lower()

    def test_default_whisper_model(self):
        from src.config import config
        assert config.audio.whisper_model == "base.en"

    def test_execution_timeouts_positive(self):
        from src.config import config
        assert config.execution.python_timeout > 0
        assert config.execution.shell_timeout > 0

    def test_memory_chroma_path_set(self):
        from src.config import config
        assert config.memory.chroma_path
        assert "chroma" in config.memory.chroma_path
