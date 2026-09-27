import asyncio
import json
import sys

from app.config import Settings


class ResumeParseError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ResumePDFParser:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def parse(self, content: bytes) -> dict:
        settings = self.settings
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.tools.pdf_worker",
            str(settings.resume_max_bytes),
            str(settings.resume_max_pages),
            str(settings.resume_max_characters),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(settings.resume_parse_timeout_seconds):
                output, _ = await process.communicate(content)
        except BaseException:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()
            raise
        if process.returncode != 0:
            raise ResumeParseError("RESUME_PARSE_FAILED")
        try:
            result = json.loads(output)
        except (ValueError, UnicodeError) as exc:
            raise ResumeParseError("RESUME_PARSE_FAILED") from exc
        if result.get("error"):
            raise ResumeParseError(result["error"])
        return result
