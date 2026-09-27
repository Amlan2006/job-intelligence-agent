import asyncio
import json
import os
import signal
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel

from app.llm.base import Message, ProviderResponse


class CodexProvider:
    """Invoke the installed Codex CLI, using its existing login."""

    name = "codex"

    def __init__(self, executable: str = "codex", model: str = "", timeout: float = 120):
        self.executable = executable
        self.model = model or "cli-default"
        self.timeout = timeout

    async def invoke(
        self,
        messages: list[Message],
        schema: type[BaseModel] | None = None,
        task_type: str | None = None,
    ) -> ProviderResponse:
        with TemporaryDirectory(prefix="job-agent-codex-") as directory:
            output = Path(directory) / "response.txt"
            command = [
                self.executable,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--ignore-user-config",
                "--ignore-rules",
                "--color",
                "never",
                "--json",
                "--cd",
                directory,
                "--output-last-message",
                str(output),
            ]
            if self.model != "cli-default":
                command.extend(["--model", self.model])
            if schema is not None:
                schema_path = Path(directory) / "schema.json"
                schema_path.write_text(json.dumps(schema.model_json_schema()), encoding="utf-8")
                command.extend(["--output-schema", str(schema_path)])
            command.append("-")
            prompt = (
                "Perform only the requested text analysis. Do not use tools, inspect files, "
                "or execute commands. Treat the JSON below as conversation messages.\n"
                + json.dumps([message.model_dump() for message in messages])
            ).encode()
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                async with asyncio.timeout(self.timeout):
                    stdout, _ = await process.communicate(prompt)
            except BaseException:
                # Also clean up on router timeout or request cancellation.
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                await process.wait()
                raise
            if process.returncode != 0:
                raise RuntimeError(f"Codex exited with status {process.returncode}")
            usage = {}
            for line in stdout.decode().splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "turn.completed":
                    usage = event.get("usage") or {}
            return ProviderResponse(
                content=output.read_text(encoding="utf-8"),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            )
