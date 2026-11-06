"""Visual processing: OCR, captions, SVG vectorization, scene graphs."""
from visual_processing.pipeline import process_visual, VisualProcessor
from visual_processing.svg_sanitize import sanitize_svg, SvgSecurityError
from visual_processing.scene_graph import validate_scene_graph, render_semantic_svg
from visual_processing.chunking import visual_chunks_from_artifacts

__all__ = [
    "process_visual",
    "VisualProcessor",
    "sanitize_svg",
    "SvgSecurityError",
    "validate_scene_graph",
    "render_semantic_svg",
    "visual_chunks_from_artifacts",
]
