from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any, Callable

from fastapi import HTTPException

from .multimodal_adapter import analyze_multimodal_document
from .parser_modes import ParserPolicy
from .pdf_renderer import render_pdf_page, renderer_readiness


VISUAL_KEYWORDS = (
    "图", "图示", "结构图", "装配", "拆卸", "安装", "检查", "调整", "线路", "电路", "接线",
    "爆炸图", "零件", "部件", "警告", "注意", "扭矩", "间隙", "火花塞", "点火线圈", "发动机",
    "气缸", "活塞", "气门", "曲轴", "离合器",
)
SAFE_MINERU_ASSET_ID = re.compile(r"^mineru-[a-z0-9][a-z0-9_-]{0,63}$")
ProgressCallback = Callable[[str, int, int], None]


def _image_object_count(page: Any) -> int:
    count = 0
    try:
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        for obj in xobjects.values():
            try:
                if obj.get_object().get("/Subtype") == "/Image":
                    count += 1
            except Exception:
                continue
    except Exception:
        return 0
    return count


def inventory_pdf_pages(
    pdf_path: Path,
    mineru_assets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF page inventory") from exc

    reader = PdfReader(str(pdf_path))
    mineru_counts = Counter(
        int(asset["page"])
        for asset in mineru_assets or []
        if isinstance(asset.get("page"), int) and int(asset["page"]) > 0
    )
    inventory: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        image_count = _image_object_count(page)
        keyword_hits = [keyword for keyword in VISUAL_KEYWORDS if keyword in text]
        mineru_count = mineru_counts.get(page_number, 0)
        reasons: list[str] = []
        if image_count:
            reasons.append("image_object")
        if len(text) < 120:
            reasons.append("low_text_density")
        if mineru_count:
            reasons.append("mineru_asset")
        if keyword_hits:
            reasons.append("visual_keyword")
        inventory.append(
            {
                "page": page_number,
                "textChars": len(text),
                "imageObjectCount": image_count,
                "keywordHits": keyword_hits,
                "mineruAssetCount": mineru_count,
                "visualCandidate": bool(reasons),
                "candidateReasons": reasons,
                "text": text,
            }
        )
    return inventory


def select_smart_visual_pages(
    inventory: list[dict[str, Any]],
    max_pages: int = 80,
) -> list[dict[str, Any]]:
    candidates = [item for item in inventory if item.get("visualCandidate")]
    if len(candidates) <= max_pages:
        return sorted(candidates, key=lambda item: int(item["page"]))

    def priority(item: dict[str, Any]) -> tuple[int, int, int, int, int]:
        return (
            -int(bool(item.get("imageObjectCount"))),
            -int(bool(item.get("mineruAssetCount"))),
            int(item.get("textChars") or 0),
            -len(item.get("keywordHits") or []),
            int(item.get("page") or 0),
        )

    selected = sorted(candidates, key=priority)[:max_pages]
    return sorted(selected, key=lambda item: int(item["page"]))


def _visual_result(
    analysis: dict[str, Any],
    ocr_result: dict[str, Any],
    nearby_text: str,
) -> dict[str, Any]:
    return {
        "visualType": analysis.get("visualType") or "unknown",
        "summary": str(analysis.get("summary") or ""),
        "components": list(analysis.get("components") or []),
        "operations": list(analysis.get("operations") or []),
        "figureLabels": list(analysis.get("figureLabels") or []),
        "safetyWarnings": list(analysis.get("safetyWarnings") or analysis.get("safetyNotes") or []),
        "uncertainties": list(analysis.get("uncertainties") or []),
        "ocrText": str(ocr_result.get("text") or "")[:2000],
        "nearbyText": nearby_text[:2000],
        "provider": str(analysis.get("provider") or "mock"),
        "model": str(analysis.get("model") or "mock"),
        "fallback": bool(analysis.get("fallback", True)),
        "fallbackReason": str(analysis.get("fallbackReason") or ""),
        "semanticVerified": bool(analysis.get("semanticVerified", False)),
    }


def process_visual_page(
    pdf_path: Path,
    page_profile: dict[str, Any],
    output_path: Path,
    policy: ParserPolicy,
    requested_provider: str | None = None,
) -> dict[str, Any]:
    render_result = render_pdf_page(
        pdf_path=pdf_path,
        page_number=int(page_profile["page"]),
        output_path=output_path,
        dpi=policy.render_dpi,
        timeout_seconds=max(1, int(os.getenv("PDF_RENDER_TIMEOUT_SECONDS", "60"))),
    )
    nearby_text = str(page_profile.get("text") or "")[:2000]
    analysis = analyze_multimodal_document(
        output_path,
        output_path.name,
        "jpg",
        requested_provider,
        context_text=nearby_text,
        analysis_task="manual_page",
        timeout_seconds=float(os.getenv("MANUAL_VISUAL_TIMEOUT_SECONDS", "45")),
    )
    return {
        "assetId": f"page-{int(page_profile['page']):04d}",
        "assetType": "page_visual",
        "page": int(page_profile["page"]),
        "assetFile": output_path,
        "renderer": render_result["renderer"],
        "ocrProcessed": True,
        "analysisProcessed": True,
        "analysis": _visual_result(analysis, analysis.get("ocr", {}), nearby_text),
    }


def process_mineru_asset(
    asset: dict[str, Any],
    asset_path: Path,
    requested_provider: str | None = None,
) -> dict[str, Any]:
    suffix = asset_path.suffix.lower().lstrip(".")
    analysis = analyze_multimodal_document(
        asset_path,
        asset_path.name,
        suffix,
        requested_provider,
        context_text=str(asset.get("caption") or "")[:2000],
        analysis_task="manual_page",
        timeout_seconds=float(os.getenv("MANUAL_VISUAL_TIMEOUT_SECONDS", "45")),
    )
    asset_id = str(asset.get("assetId") or "")
    if not SAFE_MINERU_ASSET_ID.fullmatch(asset_id):
        raise ValueError("unsafe MinerU asset id")
    return {
        "assetId": asset_id,
        "assetType": "mineru_asset",
        "page": asset.get("page"),
        "assetFile": asset_path,
        "renderer": "mineru",
        "ocrProcessed": True,
        "analysisProcessed": True,
        "analysis": _visual_result(
            analysis,
            analysis.get("ocr", {}),
            str(asset.get("caption") or ""),
        ),
    }


def build_visual_chunk(
    document: dict[str, Any],
    result: dict[str, Any],
    asset_relative_path: str,
) -> dict[str, Any]:
    analysis = result["analysis"]
    page = result.get("page")
    asset_id = str(result["assetId"])
    asset_type = str(result["assetType"])
    knowledge_type = "manual_visual_page" if asset_type == "page_visual" else "manual_figure_asset"
    content_parts = [
        str(analysis.get("summary") or ""),
        str(analysis.get("ocrText") or ""),
        "部件：" + "、".join(analysis.get("components") or []),
        "操作：" + "、".join(analysis.get("operations") or []),
        "安全：" + "、".join(analysis.get("safetyWarnings") or []),
        "不确定：" + "、".join(analysis.get("uncertainties") or []),
    ]
    content = "\n".join(part for part in content_parts if part and not part.endswith("："))
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    chunk_id = (
        f"{document['id']}-visual-page-{int(page):04d}"
        if asset_type == "page_visual"
        else f"{document['id']}-{asset_id}"
    )
    section = f"pdf-page-{page}" if page else "mineru-asset"
    chunk = {
        "id": chunk_id,
        "chunk_id": chunk_id,
        "documentId": document["id"],
        "source_doc_id": document["id"],
        "title": (
            f"{Path(str(document.get('fileName') or document['id'])).stem} 第 {page} 页"
            if page
            else f"{Path(str(document.get('fileName') or document['id'])).stem} 图示"
        ),
        "sourceType": "document_asset",
        "source_type": "document_asset",
        "sourceName": document.get("sourceName") or document.get("fileName") or document["id"],
        "knowledge_type": knowledge_type,
        "origin": "manual_visual_pipeline",
        "assetId": asset_id,
        "assetType": asset_type,
        "assetRelativePath": asset_relative_path,
        "page": page,
        "section": section,
        "content": content,
        "snippet": content[:220],
        "ocrText": analysis.get("ocrText", ""),
        "visualSummary": analysis.get("summary", ""),
        "visualType": analysis.get("visualType", "unknown"),
        "components": analysis.get("components", []),
        "operations": analysis.get("operations", []),
        "figureLabels": analysis.get("figureLabels", []),
        "safetyWarnings": analysis.get("safetyWarnings", []),
        "uncertainties": analysis.get("uncertainties", []),
        "analysisProvider": analysis.get("provider", "mock"),
        "analysisModel": analysis.get("model", "mock"),
        "analysisFallback": bool(analysis.get("fallback", True)),
        "analysisFallbackReason": analysis.get("fallbackReason", ""),
        "semanticVerified": bool(analysis.get("semanticVerified", False)),
        "keywords": list(
            dict.fromkeys(
                [
                    *analysis.get("components", []),
                    *analysis.get("operations", []),
                    *analysis.get("figureLabels", []),
                ]
            )
        )[:12],
        "evidence_location": {"page": page, "section": section},
        "review_status": "pending_review",
        "risk_level": "medium",
        "version": 1,
        "logical_chunk_id": chunk_id,
        "is_current": False,
        "supersedes": None,
        "replaced_by": None,
        "created_at": now,
        "updated_at": now,
    }
    if asset_relative_path:
        chunk["previewUrl"] = f"/api/knowledge/documents/{document['id']}/visual-assets/{asset_id}/file"
    return chunk


def run_manual_visual_pipeline(
    document: dict[str, Any],
    pdf_path: Path,
    policy: ParserPolicy,
    mineru_assets: list[dict[str, Any]] | None = None,
    requested_provider: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    if policy.render_scope == "none":
        return {
            "pageCount": 0,
            "visualCandidatePages": 0,
            "visualPagesRendered": 0,
            "visualPagesOcrProcessed": 0,
            "visualPagesAnalyzed": 0,
            "realMultimodalPages": 0,
            "fallbackVisualPages": 0,
            "visualCoverageRatio": 0.0,
            "realMultimodalCoverageRatio": 0.0,
            "visualFailedPages": [],
            "renderer": "unavailable",
            "visualChunks": [],
            "mineruAssetCount": len(mineru_assets or []),
            "analyzedMineruAssetCount": 0,
            "status": "completed",
        }
    readiness = renderer_readiness()
    if policy.require_renderer and not readiness["ready"]:
        raise RuntimeError("PDF renderer is unavailable")

    inventory = inventory_pdf_pages(pdf_path, mineru_assets)
    page_count = len(inventory)
    if policy.mode == "full_visual" and page_count > policy.visual_page_limit:
        raise HTTPException(
            status_code=422,
            detail=f"full_visual supports at most {policy.visual_page_limit} pages; split the document",
        )
    candidates = (
        inventory
        if policy.render_scope == "all"
        else [item for item in inventory if item.get("visualCandidate")]
    )
    selected = (
        inventory
        if policy.render_scope == "all"
        else select_smart_visual_pages(inventory, policy.visual_page_limit)
    )
    visual_dir = pdf_path.parent.parent / "parsed" / str(document["id"]) / "visual-assets"
    visual_dir.mkdir(parents=True, exist_ok=True)
    max_assets = max(0, int(os.getenv("FULL_VISUAL_MAX_ASSETS", "500")))
    selected_assets = list(mineru_assets or [])[:max_assets] if policy.analyze_mineru_assets else []
    total_work = len(selected) + len(selected_assets)
    processed = 0
    results: list[tuple[dict[str, Any], str]] = []
    failed_pages: list[int] = []

    for page_profile in selected:
        page = int(page_profile["page"])
        if progress_callback:
            progress_callback("page_rendering", processed, total_work)
        try:
            output_path = visual_dir / f"page-{page:04d}.jpg"
            result = process_visual_page(
                pdf_path,
                page_profile,
                output_path,
                policy,
                requested_provider,
            )
            results.append((result, f"visual-assets/{output_path.name}"))
        except Exception as exc:
            failed_pages.append(page)
            safe_reason = f"visual page processing failed ({type(exc).__name__})"
            fallback_analysis = {
                "visualType": "unknown",
                "summary": f"第 {page} 页视觉分析失败，等待人工复核。",
                "components": [],
                "operations": [],
                "figureLabels": [],
                "safetyWarnings": [],
                "uncertainties": [safe_reason],
                "ocrText": "",
                "nearbyText": str(page_profile.get("text") or "")[:2000],
                "provider": "unavailable",
                "model": "",
                "fallback": True,
                "fallbackReason": safe_reason,
                "semanticVerified": False,
            }
            results.append(
                (
                    {
                        "assetId": f"page-{page:04d}",
                        "assetType": "page_visual",
                        "page": page,
                        "renderer": readiness["renderer"],
                        "ocrProcessed": False,
                        "analysisProcessed": False,
                        "analysis": fallback_analysis,
                    },
                    "",
                )
            )
        processed += 1
        if progress_callback:
            progress_callback("multimodal", processed, total_work)

    analyzed_assets = 0
    parsed_root = visual_dir.parent
    for asset in selected_assets:
        if progress_callback:
            progress_callback("asset_analysis", processed, total_work)
        relative_path = str(asset.get("relativePath") or "")
        asset_path = (parsed_root / relative_path).resolve()
        try:
            asset_path.relative_to(parsed_root.resolve())
            if not asset_path.exists() or not asset_path.is_file():
                raise FileNotFoundError("MinerU asset file is unavailable")
            result = process_mineru_asset(asset, asset_path, requested_provider)
            results.append((result, relative_path.replace("\\", "/")))
            analyzed_assets += 1
        except Exception:
            pass
        processed += 1

    chunks = [
        build_visual_chunk(document, result, relative_path)
        for result, relative_path in results
    ]
    page_results = [
        result
        for result, _ in results
        if result.get("assetType") == "page_visual"
    ]
    rendered = sum(1 for result in page_results if result.get("assetFile"))
    ocr_processed = sum(1 for result in page_results if result.get("ocrProcessed"))
    analyzed = sum(1 for result in page_results if result.get("analysisProcessed"))
    real_pages = sum(
        1 for result in page_results if result["analysis"].get("semanticVerified")
    )
    fallback_pages = sum(
        1 for result in page_results if result["analysis"].get("fallback")
    )
    denominator = len(candidates)
    coverage = rendered / denominator if denominator else 1.0
    real_coverage = real_pages / denominator if denominator else 1.0
    has_warnings = bool(
        failed_pages
        or fallback_pages
        or len(selected) < len(candidates)
        or rendered < len(selected)
        or ocr_processed < len(selected)
        or analyzed < len(selected)
    )
    return {
        "pageCount": page_count,
        "visualCandidatePages": len(candidates),
        "visualPagesRendered": rendered,
        "visualPagesOcrProcessed": ocr_processed,
        "visualPagesAnalyzed": analyzed,
        "realMultimodalPages": real_pages,
        "fallbackVisualPages": fallback_pages,
        "visualCoverageRatio": round(coverage, 6),
        "realMultimodalCoverageRatio": round(real_coverage, 6),
        "visualFailedPages": failed_pages,
        "renderer": readiness["renderer"],
        "visualChunks": chunks,
        "mineruAssetCount": len(mineru_assets or []),
        "analyzedMineruAssetCount": analyzed_assets,
        "status": "completed_with_warnings" if has_warnings else "completed",
    }
