from __future__ import annotations

import importlib.util
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


MINERU_MODULE_CANDIDATES = ("magic_pdf", "mineru")
DEFAULT_MINERU_BACKEND = "pipeline"
DEFAULT_MINERU_LANG = "ch"
DEFAULT_MINERU_TIMEOUT_SECONDS = 180


class MinerUUnavailable(RuntimeError):
    pass


def mineru_available() -> bool:
    return mineru_module_available()


def mineru_module_available() -> bool:
    return any(importlib.util.find_spec(name) is not None for name in MINERU_MODULE_CANDIDATES)


def mineru_cli_available() -> bool:
    try:
        mineru_executable()
        return True
    except MinerUUnavailable:
        return False


def mineru_readiness() -> dict[str, Any]:
    enabled = mineru_enabled()
    module_available = mineru_module_available()
    cli_available = mineru_cli_available()
    if not enabled:
        status = "disabled"
    elif not module_available:
        status = "module_missing"
    elif not cli_available:
        status = "cli_missing"
    else:
        status = "ready"
    return {
        "enabled": enabled,
        "moduleAvailable": module_available,
        "cliAvailable": cli_available,
        "ready": status == "ready",
        "status": status,
    }


def mineru_executable() -> str:
    scripts_dir = Path(sys.executable).parent
    executable = scripts_dir / ("mineru.exe" if os.name == "nt" else "mineru")
    if executable.exists():
        return str(executable)
    resolved = shutil.which("mineru")
    if resolved:
        return resolved
    raise MinerUUnavailable("MinerU CLI executable was not found.")


def mineru_enabled() -> bool:
    return os.getenv("MINERU_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def mineru_timeout_seconds() -> int:
    raw_value = os.getenv("MINERU_TIMEOUT_SECONDS", str(DEFAULT_MINERU_TIMEOUT_SECONDS))
    try:
        return max(30, int(raw_value))
    except ValueError:
        return DEFAULT_MINERU_TIMEOUT_SECONDS


def load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def text_from_content_item(item: dict[str, Any]) -> str:
    for key in ("text", "content", "html", "latex", "table_body", "image_caption"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def page_from_content_item(item: dict[str, Any]) -> int | None:
    for key in ("page", "page_idx", "page_number"):
        value = item.get(key)
        if isinstance(value, int):
            return value + 1 if key == "page_idx" else value
    return None


def pages_from_content_list(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        return []

    pages: list[dict[str, Any]] = []
    for index, item in enumerate(content, start=1):
        if not isinstance(item, dict):
            continue
        text = text_from_content_item(item)
        if not text:
            continue
        item_type = str(item.get("type") or item.get("category") or "content")
        pages.append(
            {
                "page": page_from_content_item(item),
                "section": item_type,
                "text": text,
                "mineruIndex": index,
                "mineruType": item_type,
            }
        )
    return pages


def pages_from_markdown(markdown: str) -> list[dict[str, Any]]:
    text = markdown.strip()
    if not text:
        return []

    pages: list[dict[str, Any]] = []
    current_heading = "document"
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            pages.append({"page": None, "section": current_heading, "text": body})

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            current_heading = line.lstrip("#").strip() or "section"
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    if pages:
        return pages
    return [{"page": None, "section": "document", "text": text}]


def _safe_asset_records(content: Any, output_dir: Path, assets: list[str]) -> list[dict[str, Any]]:
    raw_records: list[dict[str, Any]] = []
    if isinstance(content, list):
        raw_records = [item for item in content if isinstance(item, dict)]
    by_path: dict[str, dict[str, Any]] = {}
    for item in raw_records:
        raw_path = next(
            (
                str(item[key])
                for key in ("img_path", "image_path", "asset_path", "path")
                if isinstance(item.get(key), str) and str(item[key]).strip()
            ),
            "",
        )
        if not raw_path:
            continue
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = output_dir / candidate
        try:
            relative = candidate.resolve().relative_to(output_dir.resolve())
        except ValueError:
            continue
        page = page_from_content_item(item)
        caption = next(
            (
                str(item[key]).strip()
                for key in ("caption", "image_caption", "text")
                if isinstance(item.get(key), str) and str(item[key]).strip()
            ),
            "",
        )
        item_type = str(item.get("type") or item.get("category") or "image").lower()
        by_path[str(relative).replace("\\", "/")] = {
            "page": page,
            "caption": caption,
            "assetType": "table" if "table" in item_type else "image",
        }

    records: list[dict[str, Any]] = []
    for index, raw_path in enumerate(assets, start=1):
        path = Path(raw_path)
        try:
            relative = path.resolve().relative_to(output_dir.resolve())
        except ValueError:
            continue
        relative_text = str(relative).replace("\\", "/")
        metadata = by_path.get(relative_text, {})
        records.append(
            {
                "assetId": f"mineru-{index:04d}",
                "relativePath": relative_text,
                "page": metadata.get("page"),
                "caption": metadata.get("caption", ""),
                "assetType": metadata.get("assetType", "image"),
            }
        )
    return records


def collect_mineru_outputs(output_dir: Path) -> tuple[str, list[dict[str, Any]], list[str], dict[str, Any]]:
    markdown_files = sorted(output_dir.rglob("*.md"), key=lambda path: path.stat().st_size, reverse=True)
    json_files = sorted(output_dir.rglob("*.json"))
    asset_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
    assets = [str(path) for path in output_dir.rglob("*") if path.is_file() and path.suffix.lower() in asset_suffixes]

    markdown = markdown_files[0].read_text(encoding="utf-8", errors="ignore") if markdown_files else ""
    content_list: Any = None
    raw_json_files: list[dict[str, Any]] = []
    for json_path in json_files:
        relative_path = str(json_path.relative_to(output_dir))
        try:
            payload = load_json_file(json_path)
        except Exception as exc:  # pragma: no cover - depends on MinerU output
            raw_json_files.append({"path": relative_path, "error": str(exc)})
            continue
        raw_json_files.append({"path": relative_path, "content": payload})
        if content_list is None and isinstance(payload, list):
            content_list = payload

    pages = pages_from_content_list(content_list)
    if not pages:
        pages = pages_from_markdown(markdown)

    metadata = {
        "markdownFiles": [str(path.relative_to(output_dir)) for path in markdown_files],
        "jsonFiles": raw_json_files,
        "assetFiles": [str(Path(path).relative_to(output_dir)) for path in assets],
        "mineruAssets": _safe_asset_records(content_list, output_dir, assets),
    }
    return markdown, pages, assets, metadata


def run_mineru_command(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    log_dir = Path(tempfile.mkdtemp(prefix="mineru-log-"))
    stdout_path = log_dir / "stdout.log"
    stderr_path = log_dir / "stderr.log"
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as stderr_file:
        process = subprocess.Popen(
            command,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:  # pragma: no cover - Windows is the active dev target here
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.kill()
                process.wait(timeout=5)
            raise MinerUUnavailable(f"MinerU timed out after {timeout_seconds} seconds.") from exc

    try:
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        stdout = ""
    try:
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        stderr = ""
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def parse_with_mineru(
    file_path: Path,
    suffix: str,
    *,
    timeout_seconds: int,
    backend: str | None = None,
    lang: str | None = None,
    api_url: str | None = None,
) -> dict[str, Any]:
    if not mineru_enabled():
        raise MinerUUnavailable("MinerU is disabled by MINERU_ENABLED.")
    if not mineru_available():
        raise MinerUUnavailable("MinerU is not installed.")

    output_root = Path(tempfile.mkdtemp(prefix="mineru-parse-"))
    command = [
        mineru_executable(),
        "-p",
        str(file_path),
        "-o",
        str(output_root),
        "-b",
        backend or os.getenv("MINERU_BACKEND", DEFAULT_MINERU_BACKEND),
        "-l",
        lang or os.getenv("MINERU_LANG", DEFAULT_MINERU_LANG),
    ]
    effective_api_url = api_url if api_url is not None else os.getenv("MINERU_API_URL", "").strip()
    if effective_api_url:
        command.extend(["--api-url", effective_api_url])

    try:
        completed = run_mineru_command(command, timeout_seconds)
    except OSError as exc:
        raise MinerUUnavailable(f"MinerU failed to start: {exc}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise MinerUUnavailable(f"MinerU exited with code {completed.returncode}: {stderr[:1000]}")

    markdown, pages, assets, metadata = collect_mineru_outputs(output_root)
    if not markdown and not pages:
        raise MinerUUnavailable("MinerU produced no usable markdown or content list.")

    return {
        "parser": "mineru",
        "status": "parsed" if pages else "empty",
        "pages": pages,
        "markdown": markdown,
        "assets": assets,
        "mineruAssets": metadata.get("mineruAssets", []),
        "fallback": False,
        "fallbackReason": "",
        "mineru": {
            "version": "3.2.3",
            "backend": os.getenv("MINERU_BACKEND", DEFAULT_MINERU_BACKEND),
            "lang": os.getenv("MINERU_LANG", DEFAULT_MINERU_LANG),
            "outputDir": str(output_root),
            "command": command,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            **metadata,
        },
    }
