from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
from typing import Any


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
        raise RuntimeError("pdftoppm is unavailable")
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
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )
    try:
        _, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        raise TimeoutError(f"PDF page {page_number} rendering timed out") from exc
    if process.returncode != 0:
        message = (stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"pdftoppm failed: {message[:300]}")
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
) -> dict[str, Any]:
    if page_number < 1:
        raise ValueError("page_number must be 1-based")
    readiness = renderer_readiness()
    renderer = str(readiness["renderer"])
    if renderer == "unavailable":
        raise RuntimeError("PDF renderer is unavailable")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)
    if renderer == "pdftoppm":
        _render_with_pdftoppm(pdf_path, page_number, output_path, dpi, timeout_seconds)
    else:
        _render_with_pymupdf(pdf_path, page_number, output_path, dpi)
    if not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise RuntimeError("PDF renderer produced no JPEG output")
    return {"renderer": renderer, "page": page_number, "dpi": dpi, "format": "jpeg"}
