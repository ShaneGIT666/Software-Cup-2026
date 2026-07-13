from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from typing import Any


class RendererUnavailable(RuntimeError):
    pass


class RenderExecutionError(RuntimeError):
    def __init__(self, message: str, failure_category: str = "smoke_render_failed") -> None:
        super().__init__(message)
        self.failure_category = failure_category


def _configured_renderer() -> str:
    value = (os.getenv("PDF_RENDERER") or "auto").strip().lower()
    return value if value in {"auto", "pdftoppm", "pymupdf"} else "auto"


def _pdftoppm_available() -> bool:
    executable = shutil.which("pdftoppm")
    if not executable:
        return False
    try:
        result = subprocess.run(
            [executable, "-v"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def renderer_readiness() -> dict[str, Any]:
    configured = _configured_renderer()
    pdftoppm_ready = _pdftoppm_available()
    pymupdf_ready = importlib.util.find_spec("fitz") is not None
    if configured in {"auto", "pdftoppm"} and pdftoppm_ready:
        renderer = "pdftoppm"
    elif configured in {"auto", "pymupdf"} and pymupdf_ready:
        renderer = "pymupdf"
    else:
        renderer = "unavailable"
    return {
        "ready": renderer != "unavailable",
        "renderer": renderer,
        "status": "ready" if renderer != "unavailable" else "unavailable",
        "pdftoppmAvailable": pdftoppm_ready,
        "pymupdfAvailable": pymupdf_ready,
    }


def _smoke_pdf(path: Path) -> None:
    from pypdf import PdfWriter  # type: ignore[import-not-found]

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as output:
        writer.write(output)


def _failure_category(exc: Exception) -> str:
    if isinstance(exc, RenderExecutionError):
        return exc.failure_category
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "missing_runtime_dependency"
    return "smoke_render_failed"


def renderer_operational_readiness() -> dict[str, Any]:
    configured = _configured_renderer()
    executable = shutil.which("pdftoppm")
    command_found = executable is not None
    version_probe_ok = _pdftoppm_available() if command_found else False
    pymupdf_available = importlib.util.find_spec("fitz") is not None
    last_failure = "not_found" if not command_found and not pymupdf_available else "unavailable"

    try:
        with tempfile.TemporaryDirectory(prefix="pdf-renderer-smoke-") as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "smoke.pdf"
            output_path = root / "smoke.jpg"
            _smoke_pdf(pdf_path)

            if configured in {"auto", "pdftoppm"} and command_found:
                try:
                    _render_with_pdftoppm(pdf_path, 1, output_path, 72, 10)
                    smoke_ok = output_path.is_file() and output_path.stat().st_size > 0
                    if smoke_ok:
                        return {
                            "ready": True,
                            "renderer": "pdftoppm",
                            "status": "ready",
                            "commandFound": True,
                            "versionProbeOk": version_probe_ok,
                            "smokeRenderOk": True,
                            "failureCategory": "none",
                        }
                    last_failure = "smoke_render_failed"
                except Exception as exc:
                    last_failure = _failure_category(exc)
                finally:
                    output_path.unlink(missing_ok=True)

            if configured in {"auto", "pymupdf"} and pymupdf_available:
                try:
                    _render_with_pymupdf(pdf_path, 1, output_path, 72)
                    smoke_ok = output_path.is_file() and output_path.stat().st_size > 0
                    if smoke_ok:
                        return {
                            "ready": True,
                            "renderer": "pymupdf",
                            "status": "ready",
                            "commandFound": command_found,
                            "versionProbeOk": version_probe_ok,
                            "smokeRenderOk": True,
                            "failureCategory": "none",
                        }
                    last_failure = "smoke_render_failed"
                except Exception as exc:
                    last_failure = _failure_category(exc)
    except Exception as exc:
        last_failure = _failure_category(exc)

    return {
        "ready": False,
        "renderer": "unavailable",
        "status": "unavailable",
        "commandFound": command_found,
        "versionProbeOk": version_probe_ok,
        "smokeRenderOk": False,
        "failureCategory": last_failure,
    }


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
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


def _render_with_pdftoppm(
    pdf_path: Path,
    page_number: int,
    output_path: Path,
    dpi: int,
    timeout_seconds: int,
) -> None:
    executable = shutil.which("pdftoppm")
    if not executable:
        raise RenderExecutionError("PDF renderer command was not found", failure_category="not_found")
    prefix = output_path.with_suffix("")
    command = [
        executable,
        "-f",
        str(page_number),
        "-l",
        str(page_number),
        "-singlefile",
        "-jpeg",
        "-r",
        str(dpi),
        str(pdf_path),
        str(prefix),
    ]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
    except FileNotFoundError as exc:
        raise RenderExecutionError("PDF renderer command was not found", failure_category="not_found") from exc
    except PermissionError as exc:
        raise RenderExecutionError("PDF renderer permission was denied", failure_category="permission_denied") from exc
    try:
        _, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        raise RenderExecutionError(
            f"PDF page {page_number} rendering timed out",
            failure_category="timeout",
        ) from exc
    if process.returncode != 0:
        safe_stderr = stderr.decode("utf-8", errors="replace").lower() if stderr else ""
        if "permission denied" in safe_stderr or "access is denied" in safe_stderr:
            category = "permission_denied"
        elif any(
            marker in safe_stderr
            for marker in ("dll", "shared library", "cannot open shared object", "missing dependency", "failed to load")
        ):
            category = "missing_runtime_dependency"
        else:
            category = "smoke_render_failed"
        raise RenderExecutionError("pdftoppm page rendering failed", failure_category=category)
    generated = prefix.with_suffix(".jpg")
    if generated != output_path and generated.exists():
        generated.replace(output_path)


def _render_with_pymupdf(pdf_path: Path, page_number: int, output_path: Path, dpi: int) -> None:
    import fitz  # type: ignore[import-not-found]

    document = fitz.open(str(pdf_path))
    try:
        if page_number > document.page_count:
            raise ValueError("page_number exceeds PDF page count")
        page = document.load_page(page_number - 1)
        scale = dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pixmap.save(str(output_path))
    finally:
        document.close()


def render_pdf_page(
    pdf_path: Path,
    page_number: int,
    output_path: Path,
    dpi: int,
    timeout_seconds: int = 60,
    *,
    selected_renderer: str | None = None,
) -> dict[str, Any]:
    if page_number < 1:
        raise ValueError("page_number must be 1-based")
    if selected_renderer not in {None, "pdftoppm", "pymupdf"}:
        raise ValueError("selected_renderer must be pdftoppm, pymupdf, or None")
    if selected_renderer is None:
        readiness = renderer_operational_readiness()
        if not readiness["ready"]:
            raise RendererUnavailable("PDF renderer is unavailable")
        renderer = str(readiness["renderer"])
    else:
        renderer = selected_renderer
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)
    if renderer == "pdftoppm":
        _render_with_pdftoppm(pdf_path, page_number, output_path, dpi, timeout_seconds)
    else:
        _render_with_pymupdf(pdf_path, page_number, output_path, dpi)
    if not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise RenderExecutionError("PDF renderer produced no JPEG output")
    return {"renderer": renderer, "page": page_number, "dpi": dpi, "format": "jpeg"}
