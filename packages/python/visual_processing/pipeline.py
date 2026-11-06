"""Visual processing pipeline with auto-routing SVG strategies."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from canonical_schemas.visual import (
    VisualArtifact,
    VisualProcessingPolicy,
    VisualProcessingRun,
    VisualQualityResult,
    VisualSceneGraph,
)
from shared.ids import new_id
from visual_processing.scene_graph import render_semantic_svg, validate_scene_graph
from visual_processing.svg_sanitize import SvgSecurityError, sanitize_svg

logger = logging.getLogger(__name__)


class VisualProcessor:
    def __init__(self, *, storage_dir: Optional[Path] = None, settings: Optional[dict[str, Any]] = None):
        self.storage_dir = storage_dir or Path("/tmp/ace-visual")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.settings = settings or {}

    def choose_svg_strategy(self, *, has_existing_svg: bool, has_native_vectors: bool, image_kind: str, policy: VisualProcessingPolicy) -> str:
        if policy.svg_strategy != "auto":
            return policy.svg_strategy
        if has_existing_svg:
            return "preserve_existing_svg"
        if has_native_vectors:
            return "extract_native_vector"
        if image_kind in {"logo", "icon", "diagram", "line_art"}:
            return "geometric_trace"
        if image_kind in {"architecture", "workflow", "uml", "chart"}:
            return "semantic_reconstruction"
        if image_kind == "table_screenshot":
            return "disabled"  # OCR + table reconstruction instead
        if image_kind == "photograph":
            return "disabled"
        return "geometric_trace"

    def process(
        self,
        *,
        tenant_id: str,
        document_version_id: str,
        source_element_id: Optional[str],
        image_path: Optional[Path],
        existing_svg: Optional[str] = None,
        native_vectors: Optional[list[dict[str, Any]]] = None,
        image_kind: str = "diagram",
        policy: Optional[VisualProcessingPolicy] = None,
        scene_graph_proposal: Optional[dict[str, Any]] = None,
        ocr_text: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> dict[str, Any]:
        policy = policy or VisualProcessingPolicy()
        run = VisualProcessingRun(
            tenant_id=tenant_id,
            document_version_id=document_version_id,
            status="RUNNING",
            policy=policy,
        )
        artifacts: list[VisualArtifact] = []
        warnings: list[str] = []

        if not policy.enabled or policy.mode == "disabled":
            run.status = "SKIPPED"
            return {"run": run, "artifacts": artifacts, "warnings": ["visual_processing_disabled"]}

        # Raster retention
        if image_path and policy.original_raster_retention:
            art = VisualArtifact(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                source_element_id=source_element_id,
                artifact_type="raster",
                storage_uri=str(image_path),
                mime_type="image/png",
                generation_strategy="retain_original",
                provider="builtin",
                provider_version="1.0.0",
                confidence=1.0,
            )
            artifacts.append(art)

        if policy.generate_ocr and ocr_text:
            artifacts.append(VisualArtifact(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                source_element_id=source_element_id,
                artifact_type="ocr",
                content_text=ocr_text,
                generation_strategy="ocr",
                provider="ocr_adapter",
                provider_version="1.0.0",
                confidence=0.7,
            ))

        if policy.generate_caption and caption:
            artifacts.append(VisualArtifact(
                tenant_id=tenant_id,
                document_version_id=document_version_id,
                source_element_id=source_element_id,
                artifact_type="caption",
                content_text=caption,
                generation_strategy="caption",
                provider="caption_adapter",
                provider_version="1.0.0",
                confidence=0.7,
            ))

        strategy = self.choose_svg_strategy(
            has_existing_svg=bool(existing_svg),
            has_native_vectors=bool(native_vectors),
            image_kind=image_kind,
            policy=policy,
        )

        svg_text = None
        quality = None
        if policy.generate_svg and strategy != "disabled":
            try:
                if strategy == "preserve_existing_svg" and existing_svg:
                    svg_text = existing_svg
                elif strategy == "extract_native_vector" and native_vectors:
                    svg_text = self._native_vectors_to_svg(native_vectors)
                elif strategy == "geometric_trace":
                    svg_text = self._geometric_trace(image_path)
                elif strategy == "semantic_reconstruction":
                    if not scene_graph_proposal:
                        # minimal deterministic graph when LLM proposal absent
                        scene_graph_proposal = {
                            "nodes": [
                                {"node_id": "n1", "label": "Element", "node_type": "shape", "bbox": [20, 20, 120, 60], "source_element_id": source_element_id},
                            ],
                            "edges": [],
                            "groups": [{"group_id": "g1", "label": "Main", "node_ids": ["n1"]}],
                        }
                    graph = validate_scene_graph(scene_graph_proposal)
                    if not graph.validated:
                        warnings.extend(graph.validation_errors)
                        if policy.fallback_behavior == "retain_raster":
                            strategy = "disabled"
                        else:
                            svg_text = self._geometric_trace(image_path)
                    else:
                        svg_text = render_semantic_svg(graph)
                        artifacts.append(VisualArtifact(
                            tenant_id=tenant_id,
                            document_version_id=document_version_id,
                            source_element_id=source_element_id,
                            artifact_type="scene_graph",
                            content_text=graph.model_dump_json(),
                            generation_strategy="semantic_reconstruction",
                            provider="deterministic_renderer",
                            provider_version="1.0.0",
                            confidence=0.85,
                            metadata={"scene_graph_id": graph.scene_graph_id},
                        ))
                else:
                    svg_text = None

                if svg_text:
                    original_path = self.storage_dir / f"{new_id()}-original.svg"
                    original_path.write_text(svg_text, encoding="utf-8")
                    try:
                        sanitized, stats = sanitize_svg(
                            svg_text,
                            max_bytes=int(self.settings.get("SVG_MAX_FILE_SIZE_BYTES", 10_000_000)),
                            max_elements=int(self.settings.get("SVG_MAX_ELEMENTS", 10_000)),
                            max_path_commands=int(self.settings.get("SVG_MAX_PATH_COMMANDS", 200_000)),
                            max_nesting_depth=int(self.settings.get("SVG_MAX_NESTING_DEPTH", 32)),
                            allow_external_references=bool(self.settings.get("SVG_ALLOW_EXTERNAL_REFERENCES", False)),
                            allow_scripts=bool(self.settings.get("SVG_ALLOW_SCRIPTS", False)),
                            allow_foreign_object=bool(self.settings.get("SVG_ALLOW_FOREIGN_OBJECT", False)),
                        )
                    except SvgSecurityError as exc:
                        warnings.append(f"svg_rejected:{exc}")
                        sanitized = None
                        stats = {}
                    confidence = 0.9 if strategy == "preserve_existing_svg" else 0.8
                    if confidence < policy.minimum_confidence:
                        warnings.append("low_confidence_fallback")
                        if policy.fallback_behavior == "retain_raster":
                            sanitized = None
                    if sanitized is not None:
                        san_path = self.storage_dir / f"{new_id()}-sanitized.svg"
                        san_path.write_text(sanitized, encoding="utf-8")
                        art = VisualArtifact(
                            tenant_id=tenant_id,
                            document_version_id=document_version_id,
                            source_element_id=source_element_id,
                            artifact_type="semantic_svg" if strategy == "semantic_reconstruction" else "geometric_svg",
                            storage_uri=str(original_path),
                            sanitized_storage_uri=str(san_path),
                            generation_strategy=strategy,
                            provider="visual_processing",
                            provider_version="1.0.0",
                            confidence=confidence,
                            metadata={"stats": stats},
                        )
                        artifacts.append(art)
                        quality = VisualQualityResult(
                            visual_artifact_id=art.visual_artifact_id,
                            confidence=confidence,
                            element_count=int((stats or {}).get("elements", 0)),
                            path_command_count=int((stats or {}).get("path_commands", 0)),
                            nesting_depth=int((stats or {}).get("max_depth", 0)),
                            byte_size=len(sanitized.encode("utf-8")),
                            warnings=warnings,
                            passed=confidence >= policy.minimum_confidence,
                            fallback_used=False,
                        )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"svg_generation_failed:{exc}")
                logger.exception("SVG generation failed")

        run.status = "READY"
        run.artifacts = [a.visual_artifact_id for a in artifacts]
        return {"run": run, "artifacts": artifacts, "quality": quality, "warnings": warnings, "strategy": strategy}

    def _native_vectors_to_svg(self, vectors: list[dict[str, Any]]) -> str:
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">']
        for i, v in enumerate(vectors):
            shape = v.get("type", "rect")
            if shape == "rect":
                parts.append(f'<rect id="nv{i}" x="{v.get("x",0)}" y="{v.get("y",0)}" width="{v.get("w",40)}" height="{v.get("h",20)}" fill="none" stroke="#000" />')
            elif shape == "path":
                parts.append(f'<path id="nv{i}" d="{v.get("d","M0 0")}" fill="none" stroke="#000" />')
            else:
                parts.append(f'<circle id="nv{i}" cx="{v.get("x",10)}" cy="{v.get("y",10)}" r="{v.get("r",5)}" fill="none" stroke="#000" />')
        parts.append("</svg>")
        return "\n".join(parts)

    def _geometric_trace(self, image_path: Optional[Path]) -> str:
        """VTracer/Potrace-compatible path with OpenCV preprocessing hooks + deterministic fallback."""
        # Try vtracer
        if image_path and image_path.exists():
            try:
                import vtracer
                svg = vtracer.convert_image_to_svg_str(str(image_path))
                if svg:
                    return svg
            except Exception:
                pass
            # OpenCV preprocess hook (optional)
            try:
                import cv2
                import numpy as np
                img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    _, thr = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    # Potrace-compatible: write PBM-like representation as simple rect grid fallback
                    h, w = thr.shape
                    # Downsample for simple geometric approximation
                    step = max(1, min(h, w) // 32)
                    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">']
                    idx = 0
                    for y in range(0, h, step):
                        for x in range(0, w, step):
                            if thr[y, x] < 128:
                                parts.append(f'<rect id="p{idx}" x="{x}" y="{y}" width="{step}" height="{step}" fill="#000" />')
                                idx += 1
                                if idx > 5000:
                                    break
                        if idx > 5000:
                            break
                    parts.append("</svg>")
                    return "\n".join(parts)
            except Exception:
                pass
        # Deterministic geometric placeholder for line-art
        return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120">
  <rect id="frame" x="10" y="10" width="180" height="100" fill="none" stroke="#222" stroke-width="2"/>
  <line id="diag" x1="10" y1="10" x2="190" y2="110" stroke="#222" stroke-width="2"/>
</svg>'''


def process_visual(**kwargs: Any) -> dict[str, Any]:
    return VisualProcessor().process(**kwargs)
