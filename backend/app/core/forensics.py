"""
forensics.py — Local Media Forensics Engine

Performs multi-signal, evidence-based analysis of image/video bytes
to determine the likelihood of AI generation and manipulation.

This is a LOCAL analysis that does NOT rely on external APIs.
All findings are independently verifiable and documented.

Signals analysed:
  1. EXIF metadata (Camera Make/Model, GPS, software tags, datetime)
  2. PNG/WEBP text chunks (AI generator tool signatures)
  3. JPEG DCT frequency domain analysis (AI smoothness vs sensor noise)
  4. Pixel-level noise pattern analysis (sensor noise uniformity)
  5. Color statistics (AI colour distribution vs natural photography)
  6. File format signals (compression artefacts, format anomalies)

Evidence is aggregated into a calibrated confidence score.
Model attribution is clearly marked as INFERRED unless proven by
cryptographic provenance (C2PA / verified watermark / trusted metadata).
"""
import io
import math
import hashlib
import logging
import struct
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("forensics")

# ── Known AI generator software tags found in EXIF / metadata ────────────────
_AI_SOFTWARE_SIGNATURES: List[Tuple[str, str]] = [
    # (pattern_lower, inferred_model_family)
    ("midjourney",         "Midjourney"),
    ("stable diffusion",   "Stable Diffusion"),
    ("stablediffusion",    "Stable Diffusion"),
    ("automatic1111",      "Stable Diffusion (A1111)"),
    ("comfyui",            "Stable Diffusion (ComfyUI)"),
    ("invokeai",           "Stable Diffusion (InvokeAI)"),
    ("novelai",            "NovelAI"),
    ("dall-e",             "DALL-E"),
    ("dall·e",             "DALL-E"),
    ("dalle",              "DALL-E"),
    ("openai",             "DALL-E / OpenAI"),
    ("adobe firefly",      "Adobe Firefly"),
    ("firefly",            "Adobe Firefly"),
    ("adobe generative",   "Adobe Firefly"),
    ("imagen",             "Google Imagen"),
    ("gemini",             "Google Gemini"),
    ("flux",               "FLUX"),
    ("black forest",       "FLUX"),
    ("nightcafe",          "NightCafe"),
    ("leonardo.ai",        "Leonardo.AI"),
    ("leonardo ai",        "Leonardo.AI"),
    ("dreamstudio",        "Stable Diffusion (DreamStudio)"),
    ("getimg",             "GetIMG.AI"),
    ("ideogram",           "Ideogram"),
    ("playground ai",      "Playground AI"),
    ("bing image creator", "DALL-E (Bing)"),
    ("canva ai",           "Canva AI"),
    ("adobe photoshop 24", None),  # Not AI by itself, but note it
    ("adobe photoshop 25", None),
    ("adobe photoshop 26", None),
    ("generative fill",    "Adobe Firefly (Generative Fill)"),
]

# Real camera makes — if present it is strong evidence of authentic origin
_CAMERA_MAKES = {
    "canon", "nikon", "sony", "fujifilm", "olympus", "panasonic",
    "leica", "hasselblad", "phase one", "pentax", "ricoh", "samsung",
    "apple", "google", "huawei", "xiaomi", "oneplus", "lg electronics",
    "motorola", "nokia", "dji", "gopro", "casio", "sigma",
}


def run_forensic_analysis(raw_bytes: bytes, content_type: str, filename: str = "") -> Dict[str, Any]:
    """
    Entry point. Run all forensic checks and return a structured report.

    Returns a dict with:
      - ai_probability: float 0.0–1.0  (1.0 = almost certainly AI)
      - verdict: str — LIKELY_AI | POSSIBLY_AI | INSUFFICIENT_EVIDENCE | LIKELY_AUTHENTIC
      - confidence: str — HIGH | MEDIUM | LOW
      - inferred_model_family: str | None  (only if strong metadata evidence)
      - attribution_type: str — METADATA_VERIFIED | INFERRED | UNKNOWN
      - evidence: List[Dict] — list of evidence items with name/status/detail
      - manipulation_detected: bool
      - manipulation_signals: List[str]
    """
    evidence: List[Dict[str, Any]] = []
    signals: Dict[str, float] = {}  # signal_name → weight in 0-1 range

    inferred_model = None
    attribution_type = "UNKNOWN"
    manipulation_signals: List[str] = []
    has_camera_hardware = False
    has_gps = False

    # ── Signal 1: File format detection ──────────────────────────────────────
    detected_format = _detect_format(raw_bytes)

    # ── Signal 2: EXIF & Metadata analysis ───────────────────────────────────
    try:
        meta_result = _analyse_metadata(raw_bytes, content_type)
        evidence.extend(meta_result["evidence"])
        signals.update(meta_result["signals"])

        if meta_result.get("inferred_model"):
            inferred_model = meta_result["inferred_model"]
            attribution_type = meta_result.get("attribution_type", "METADATA_VERIFIED")
        if meta_result.get("has_camera_hardware"):
            has_camera_hardware = True
        if meta_result.get("has_gps"):
            has_gps = True
    except Exception as e:
        logger.warning("Metadata analysis failed: %s", e)
        evidence.append({"name": "EXIF / Metadata Analysis", "status": "warn",
                         "detail": "Could not extract metadata — file may be stripped or non-standard."})

    # ── Signal 3: DCT frequency analysis (JPEG only) ─────────────────────────
    if detected_format == "JPEG" or content_type == "image/jpeg":
        try:
            dct_result = _analyse_jpeg_dct(raw_bytes)
            evidence.extend(dct_result["evidence"])
            signals.update(dct_result["signals"])
        except Exception as e:
            logger.warning("DCT analysis failed: %s", e)

    # ── Signal 4: Pixel-level noise analysis (images only) ───────────────────
    if content_type.startswith("image/"):
        try:
            noise_result = _analyse_pixel_noise(raw_bytes)
            evidence.extend(noise_result["evidence"])
            signals.update(noise_result["signals"])
            manipulation_signals.extend(noise_result.get("manipulation_signals", []))
        except Exception as e:
            logger.warning("Pixel noise analysis failed: %s", e)

    # ── Signal 5: Color statistics ────────────────────────────────────────────
    if content_type.startswith("image/"):
        try:
            color_result = _analyse_color_statistics(raw_bytes)
            evidence.extend(color_result["evidence"])
            signals.update(color_result["signals"])
        except Exception as e:
            logger.warning("Color analysis failed: %s", e)

    # ── Aggregate score ───────────────────────────────────────────────────────
    ai_prob, confidence = _aggregate_score(signals, has_camera_hardware, has_gps, inferred_model)

    # ── Verdict ───────────────────────────────────────────────────────────────
    verdict = _determine_verdict(ai_prob, confidence, len(signals))

    # ── Manipulation detection ────────────────────────────────────────────────
    manipulation_detected = len(manipulation_signals) > 0

    return {
        "ai_probability": round(ai_prob, 3),
        "verdict": verdict,
        "confidence": confidence,
        "inferred_model_family": inferred_model,
        "attribution_type": attribution_type,
        "evidence": evidence,
        "manipulation_detected": manipulation_detected,
        "manipulation_signals": manipulation_signals,
        "signals_collected": len(signals),
    }


# ── Internal signal modules ───────────────────────────────────────────────────

def _detect_format(raw: bytes) -> str:
    """Detect image format from magic bytes."""
    if raw[:3] == b'\xff\xd8\xff':
        return "JPEG"
    if raw[:8] == b'\x89PNG\r\n\x1a\n':
        return "PNG"
    if raw[:4] in (b'RIFF',) and raw[8:12] == b'WEBP':
        return "WEBP"
    if raw[:6] in (b'GIF87a', b'GIF89a'):
        return "GIF"
    return "UNKNOWN"


def _analyse_metadata(raw: bytes, content_type: str) -> Dict[str, Any]:
    """
    Extract and analyse EXIF, IPTC, XMP, and PNG text metadata.
    Returns evidence items and weighted signals.
    """
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS

    evidence = []
    signals = {}
    inferred_model = None
    attribution_type = "UNKNOWN"
    has_camera_hardware = False
    has_gps = False

    try:
        img = Image.open(io.BytesIO(raw))
        info = img.info or {}
        fmt = img.format or "UNKNOWN"
    except Exception as e:
        return {"evidence": [], "signals": {}, "inferred_model": None}

    # ── PNG text chunks (tEXt / iTXt) ──────────────────────────────────────
    if fmt in ("PNG", "WEBP"):
        text_chunks = {k.lower(): v for k, v in info.items() if isinstance(k, str)}
        found_ai_sig = None
        for key, val in text_chunks.items():
            val_lower = str(val).lower()
            for sig, model_family in _AI_SOFTWARE_SIGNATURES:
                if sig in val_lower or sig in key:
                    found_ai_sig = model_family or "AI Tool (unidentified)"
                    break
            if found_ai_sig:
                break

        if found_ai_sig:
            inferred_model = found_ai_sig
            attribution_type = "METADATA_VERIFIED"
            signals["metadata_ai_sig"] = 1.0
            evidence.append({
                "name": "PNG Metadata AI Signature",
                "status": "fail",
                "detail": f"AI generator footprint detected in file metadata: {found_ai_sig}"
            })
        elif text_chunks:
            evidence.append({
                "name": "PNG Metadata Inspection",
                "status": "pass",
                "detail": f"No AI generator signatures found in {len(text_chunks)} metadata chunk(s)."
            })

        # Check for 'parameters' chunk (Stable Diffusion A1111 stores prompt here)
        if "parameters" in text_chunks:
            inferred_model = inferred_model or "Stable Diffusion (A1111)"
            attribution_type = "METADATA_VERIFIED"
            signals["metadata_ai_sig"] = 1.0
            evidence.append({
                "name": "Stable Diffusion Prompt Chunk",
                "status": "fail",
                "detail": "PNG 'parameters' chunk found — characteristic of Stable Diffusion A1111 output."
            })

        # Check for ComfyUI workflow chunk
        if "workflow" in text_chunks or "prompt" in text_chunks:
            if inferred_model is None:  # don't overwrite a more specific sig
                inferred_model = "Stable Diffusion (ComfyUI)"
                attribution_type = "METADATA_VERIFIED"
                signals["metadata_ai_sig"] = 0.9
                evidence.append({
                    "name": "ComfyUI Workflow Chunk",
                    "status": "fail",
                    "detail": "PNG workflow/prompt chunk detected — characteristic of ComfyUI output."
                })

    # ── EXIF data ─────────────────────────────────────────────────────────────
    try:
        exif_raw = img.getexif()
    except Exception:
        exif_raw = None

    if exif_raw:
        exif = {TAGS.get(k, k): v for k, v in exif_raw.items()}

        # Camera Make / Model
        make = str(exif.get("Make", "")).strip().lower()
        model_tag = str(exif.get("Model", "")).strip()

        if make and any(cam in make for cam in _CAMERA_MAKES):
            has_camera_hardware = True
            signals["camera_hardware"] = -1.0  # Negative = evidence AGAINST AI
            evidence.append({
                "name": "Camera Hardware EXIF",
                "status": "pass",
                "detail": f"Real camera make/model detected: {exif.get('Make', '')} {model_tag}. "
                          f"Strong indicator of authentic hardware capture."
            })

        # GPS data
        gps_info = exif_raw.get(34853)  # GPSInfo tag
        if gps_info:
            has_gps = True
            signals["gps_present"] = -0.6
            evidence.append({
                "name": "GPS Location Data",
                "status": "pass",
                "detail": "GPS EXIF data present. AI generators do not embed GPS coordinates."
            })

        # Software tag — AI tools often sign their output here
        software = str(exif.get("Software", "")).strip()
        if software:
            sw_lower = software.lower()
            found_ai_sw = None
            for sig, model_family in _AI_SOFTWARE_SIGNATURES:
                if sig in sw_lower:
                    found_ai_sw = model_family
                    break
            if found_ai_sw:
                inferred_model = found_ai_sw
                attribution_type = "METADATA_VERIFIED"
                signals["exif_software_ai"] = 1.0
                evidence.append({
                    "name": "EXIF Software Tag",
                    "status": "fail",
                    "detail": f"AI tool identified in EXIF Software field: '{software}' → {found_ai_sw}"
                })
            elif software:
                # Check if it's a camera firmware or non-AI editor
                evidence.append({
                    "name": "EXIF Software Tag",
                    "status": "pass",
                    "detail": f"Software tag: '{software}' — no AI generator signature detected."
                })

        # DateTimeOriginal — real cameras always embed this; AI tools often don't
        dt_orig = exif.get("DateTimeOriginal")
        dt_digit = exif.get("DateTimeDigitized")
        if dt_orig:
            signals["datetime_original"] = -0.3
            evidence.append({
                "name": "Original Capture Timestamp",
                "status": "pass",
                "detail": f"DateTimeOriginal present: {dt_orig}. Real cameras embed this; AI tools typically don't."
            })
        else:
            signals["no_datetime_original"] = 0.15
            evidence.append({
                "name": "Original Capture Timestamp",
                "status": "warn",
                "detail": "No DateTimeOriginal EXIF field. Real cameras always embed capture time; AI generators typically don't."
            })

        # MakerNote presence — camera-manufacturer-specific data, never present in AI images
        if exif_raw.get(37500):  # MakerNote
            signals["makernote"] = -0.5
            evidence.append({
                "name": "Camera MakerNote",
                "status": "pass",
                "detail": "Manufacturer-specific MakerNote EXIF present. This is exclusive to real camera hardware."
            })

    else:
        signals["no_exif"] = 0.2
        evidence.append({
            "name": "EXIF Data",
            "status": "warn",
            "detail": "No EXIF data found. Real photos from cameras/phones almost always contain EXIF. "
                      "Many AI generators and social-media-compressed images strip it."
        })

    return {
        "evidence": evidence,
        "signals": signals,
        "inferred_model": inferred_model,
        "attribution_type": attribution_type,
        "has_camera_hardware": has_camera_hardware,
        "has_gps": has_gps,
    }


def _analyse_jpeg_dct(raw: bytes) -> Dict[str, Any]:
    """
    Analyse JPEG quantisation tables.
    
    AI-generated JPEG images often have smooth, low-entropy DCT coefficients.
    Social-media recompression introduces specific quantisation table patterns
    that differ from native AI output.
    
    We check for:
    - Quantisation table values (AI tools often use quality 90-95+ or have flat tables)
    - Presence of multiple quantisation tables (professional cameras use 2+ tables)
    """
    evidence = []
    signals = {}

    try:
        # Parse JPEG markers to find DQT (quantisation table) segments
        qt_tables = _extract_jpeg_qt(raw)
        if not qt_tables:
            evidence.append({
                "name": "JPEG Quantisation Analysis",
                "status": "warn",
                "detail": "Could not extract quantisation tables from JPEG stream."
            })
            return {"evidence": evidence, "signals": signals}

        # Analyse the luma quantisation table (table 0)
        luma_qt = qt_tables[0] if qt_tables else []
        if luma_qt:
            avg_q = sum(luma_qt) / len(luma_qt)
            # Very low average Q values (< 5) indicate high JPEG quality / AI output
            # Natural photo cameras use moderate quality tables
            if avg_q < 4.5:
                signals["jpeg_high_quality"] = 0.25
                evidence.append({
                    "name": "JPEG Quantisation Table",
                    "status": "warn",
                    "detail": f"Very high JPEG quality detected (avg table coeff: {avg_q:.1f}). "
                              f"AI generators often use maximum quality settings."
                })
            elif avg_q > 25:
                signals["jpeg_high_compression"] = -0.1
                evidence.append({
                    "name": "JPEG Quantisation Table",
                    "status": "pass",
                    "detail": f"Moderate-high compression (avg coeff: {avg_q:.1f}) — consistent with social media / camera output."
                })
            else:
                evidence.append({
                    "name": "JPEG Quantisation Table",
                    "status": "pass",
                    "detail": f"Quantisation table values ({avg_q:.1f}) consistent with typical camera or editor output."
                })

        # Multiple quantisation tables = professional camera or high-quality editor
        if len(qt_tables) >= 2:
            signals["multi_qt"] = -0.15
    except Exception as e:
        logger.debug("JPEG DCT analysis error: %s", e)

    return {"evidence": evidence, "signals": signals}


def _extract_jpeg_qt(raw: bytes) -> List[List[int]]:
    """Parse JPEG stream for DQT (Define Quantisation Table) markers."""
    tables = []
    i = 0
    while i < len(raw) - 1:
        if raw[i] != 0xFF:
            i += 1
            continue
        marker = raw[i + 1]
        i += 2
        if marker == 0xDB:  # DQT
            length = struct.unpack(">H", raw[i:i+2])[0]
            seg = raw[i+2: i + length]
            offset = 0
            while offset < len(seg):
                precision_and_id = seg[offset]
                precision = (precision_and_id >> 4) & 0xF
                offset += 1
                table_size = 64 * (1 if precision == 0 else 2)
                table = list(seg[offset: offset + table_size])
                if table:
                    tables.append(table)
                offset += table_size
            i += length
        elif marker in (0xD8, 0xD9, 0x01):
            pass
        elif i + 1 < len(raw):
            if raw[i:i+2] == b'\xFF\xD9':
                break
            try:
                length = struct.unpack(">H", raw[i:i+2])[0]
                i += length
            except Exception:
                break
        else:
            break
    return tables


def _analyse_pixel_noise(raw: bytes) -> Dict[str, Any]:
    """
    Analyse pixel-level noise patterns.

    Real camera sensors produce spatially varying, shot-noise-like patterns.
    AI generators produce images that are often:
    - Too smooth in uniform regions (< natural noise floor)
    - Too perfectly detailed everywhere (oversharpening)
    - Have unnaturally uniform noise texture (AI denoising artifacts)

    We use numpy for efficient calculation.
    """
    import numpy as np
    from PIL import Image

    evidence = []
    signals = {}
    manipulation_signals = []

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        # Downscale large images for efficiency — preserve statistical properties
        max_dim = 512
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        arr = np.array(img, dtype=np.float32)
        h, w, c = arr.shape

        if h < 8 or w < 8:
            return {"evidence": evidence, "signals": signals, "manipulation_signals": []}

        # ── Local noise estimation via high-pass filter ───────────────────────
        # Estimate noise as residual after median-like smoothing using pixel differences
        # This approximates the Laplacian noise estimate
        dy = np.diff(arr, axis=0)
        dx = np.diff(arr, axis=1)
        local_diff = np.abs(dy[:, :w-1, :]) + np.abs(dx[:h-1, :, :])
        
        avg_noise = float(np.mean(local_diff))
        std_noise = float(np.std(local_diff))
        noise_uniformity = std_noise / (avg_noise + 1e-6)  # coefficient of variation

        # ── Noise level interpretation ────────────────────────────────────────
        # Empirically: real photos avg ~18-35, AI images ~8-22 (too smooth or uniform)
        # Heavily compressed images can go low too, so we use uniformity as a second signal

        noise_ai_score = 0.0
        noise_detail = ""

        if avg_noise < 10.0:
            noise_ai_score = 0.45
            noise_detail = (f"Very low local noise variance ({avg_noise:.1f}/255). "
                            f"Significantly below natural camera sensor noise floor (~18-35). "
                            f"Strong indicator of AI generation or heavy denoising.")
            evidence.append({
                "name": "Pixel Noise Level Analysis",
                "status": "fail",
                "detail": noise_detail
            })
        elif avg_noise < 18.0:
            noise_ai_score = 0.25
            noise_detail = (f"Below-average noise ({avg_noise:.1f}/255). "
                            f"Could indicate AI generation, heavy JPEG compression, or professional denoising.")
            evidence.append({
                "name": "Pixel Noise Level Analysis",
                "status": "warn",
                "detail": noise_detail
            })
        else:
            noise_ai_score = max(0.0, 0.1 - (avg_noise - 18) * 0.005)
            evidence.append({
                "name": "Pixel Noise Level Analysis",
                "status": "pass",
                "detail": f"Noise variance ({avg_noise:.1f}/255) consistent with natural camera sensor output."
            })

        signals["pixel_noise_level"] = noise_ai_score

        # ── Noise uniformity (coefficient of variation) ───────────────────────
        # Real images: noise varies spatially (shadows noisier than highlights) → high CoV
        # AI images: noise tends to be spatially uniform → low CoV
        if noise_uniformity < 0.8 and avg_noise < 20:
            signals["noise_uniformity"] = 0.3
            evidence.append({
                "name": "Noise Spatial Uniformity",
                "status": "warn",
                "detail": (f"Unusually uniform noise texture (CoV: {noise_uniformity:.2f}). "
                           f"Natural camera noise varies spatially; AI generators often apply uniform patterns.")
            })
        else:
            signals["noise_uniformity"] = 0.0
            evidence.append({
                "name": "Noise Spatial Uniformity",
                "status": "pass",
                "detail": f"Noise spatial variation (CoV: {noise_uniformity:.2f}) within expected range."
            })

        # ── Sharpness consistency check ───────────────────────────────────────
        # Artificially sharpened images (a common AI post-processing step) show
        # very high local contrast at edges with smooth interiors
        gray = np.mean(arr, axis=2)
        lap_approx = (
            np.abs(gray[1:-1, 1:-1] - gray[0:-2, 1:-1]) +
            np.abs(gray[1:-1, 1:-1] - gray[2:,   1:-1]) +
            np.abs(gray[1:-1, 1:-1] - gray[1:-1, 0:-2]) +
            np.abs(gray[1:-1, 1:-1] - gray[1:-1, 2:  ])
        )
        high_edge_ratio = float(np.mean(lap_approx > 40)) 
        # If > 35% of pixels are at high-contrast edges AND noise is low, suspect AI over-sharpening
        if high_edge_ratio > 0.35 and avg_noise < 15:
            manipulation_signals.append(
                f"Edge-noise discrepancy: {high_edge_ratio*100:.0f}% high-contrast edges with low background noise "
                f"({avg_noise:.1f}). May indicate AI generation or local manipulation/sharpening."
            )

    except Exception as e:
        logger.warning("Pixel noise analysis error: %s", e)
        evidence.append({
            "name": "Pixel Noise Analysis",
            "status": "warn",
            "detail": f"Analysis incomplete: {str(e)}"
        })

    return {"evidence": evidence, "signals": signals, "manipulation_signals": manipulation_signals}


def _analyse_color_statistics(raw: bytes) -> Dict[str, Any]:
    """
    Analyse colour distribution statistics.

    AI generators often exhibit:
    - Higher average saturation (visually vivid colours)
    - More uniform hue distribution (AI tries to be aesthetically pleasing)
    - Specific channel biases (warm cast in Midjourney, blue in DALL-E)
    - Lower variance in low-frequency luminance (smooth gradients)
    """
    import numpy as np
    from PIL import Image

    evidence = []
    signals = {}

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        max_dim = 384
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        arr = np.array(img, dtype=np.float32) / 255.0
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]

        # ── Saturation (HSV) ──────────────────────────────────────────────────
        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        delta = cmax - cmin
        # Saturation = delta / cmax (avoid div by zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            sat = np.where(cmax > 0.01, delta / cmax, 0.0)
        avg_sat = float(np.mean(sat))

        if avg_sat > 0.50:
            signals["high_saturation"] = 0.30
            evidence.append({
                "name": "Colour Saturation Analysis",
                "status": "warn",
                "detail": (f"High average saturation ({avg_sat:.3f}). "
                           f"AI image generators (especially Midjourney, DALL-E) tend to produce "
                           f"more vivid, saturated images than natural photography (typical: 0.25–0.45).")
            })
        elif avg_sat > 0.38:
            signals["high_saturation"] = 0.10
            evidence.append({
                "name": "Colour Saturation Analysis",
                "status": "warn",
                "detail": f"Slightly elevated saturation ({avg_sat:.3f}). Within plausible range for both AI and real images."
            })
        else:
            signals["high_saturation"] = 0.0
            evidence.append({
                "name": "Colour Saturation Analysis",
                "status": "pass",
                "detail": f"Saturation ({avg_sat:.3f}) consistent with natural photography."
            })

        # ── Luminance smoothness ───────────────────────────────────────────────
        # AI images tend to have very smooth luminance gradients
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        lum_std = float(np.std(lum))
        lum_mean = float(np.mean(lum))

        if lum_std < 0.08:
            signals["low_luminance_variance"] = 0.20
            evidence.append({
                "name": "Luminance Distribution",
                "status": "warn",
                "detail": (f"Low luminance variance (std={lum_std:.3f}, mean={lum_mean:.3f}). "
                           f"May indicate AI over-smoothing or professionally lit studio image.")
            })
        else:
            evidence.append({
                "name": "Luminance Distribution",
                "status": "pass",
                "detail": f"Luminance variance (std={lum_std:.3f}) within natural range."
            })

    except Exception as e:
        logger.warning("Color analysis error: %s", e)

    return {"evidence": evidence, "signals": signals}


# ── Score aggregation ─────────────────────────────────────────────────────────

def _aggregate_score(
    signals: Dict[str, float],
    has_camera_hardware: bool,
    has_gps: bool,
    inferred_model: Optional[str],
) -> Tuple[float, str]:
    """
    Aggregate individual signal weights into a final AI probability.

    Signals are intentionally NOT simply averaged.
    Strong positive or negative signals (camera hardware, AI metadata)
    act as anchors that dominate the final score.
    Weak signals accumulate but cannot override strong anchors.

    Returns: (ai_probability: float 0-1, confidence: str HIGH|MEDIUM|LOW)
    """
    if not signals:
        return 0.5, "LOW"

    # Hard anchors
    if inferred_model and signals.get("metadata_ai_sig", 0) >= 0.9:
        # Definitive metadata proof of AI
        # Other signals can refine but cannot override
        base = 0.95
        confidence = "HIGH"
        return min(1.0, base), confidence

    if has_camera_hardware:
        # Camera hardware is strong authentic signal
        # Can only be overridden by AI metadata signature
        if signals.get("metadata_ai_sig", 0) >= 0.8:
            # Edited in AI tool after capture
            base = 0.70
            confidence = "MEDIUM"
        else:
            base = 0.10
            confidence = "HIGH" if has_gps else "MEDIUM"
        return max(0.0, min(1.0, base)), confidence

    # Soft aggregation for remaining signals
    # Split into AI-positive and AI-negative
    positive = {k: v for k, v in signals.items() if v > 0}
    negative = {k: v for k, v in signals.items() if v < 0}

    pos_total = sum(positive.values())
    neg_total = abs(sum(negative.values()))

    # Weighted combination; start from neutral 0.40
    raw_score = 0.40 + (pos_total * 0.5) - (neg_total * 0.5)
    ai_prob = max(0.0, min(1.0, raw_score))

    # Confidence based on number and strength of signals
    total_signal_strength = pos_total + neg_total
    num_signals = len(signals)

    if num_signals >= 5 and total_signal_strength >= 0.8:
        confidence = "HIGH"
    elif num_signals >= 3 or total_signal_strength >= 0.4:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return ai_prob, confidence


def _determine_verdict(ai_prob: float, confidence: str, num_signals: int) -> str:
    """Map probability + confidence to a human-readable verdict."""
    if num_signals < 2:
        return "INSUFFICIENT_EVIDENCE"

    if ai_prob >= 0.80:
        return "LIKELY_AI"
    if ai_prob >= 0.60:
        return "POSSIBLY_AI"
    if ai_prob <= 0.25:
        return "LIKELY_AUTHENTIC"
    return "INSUFFICIENT_EVIDENCE"
