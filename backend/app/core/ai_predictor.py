"""
ai_predictor.py — Provenance Feature Predictor

Runs two independent analysis pipelines:

1. LOCAL FORENSIC ENGINE (always runs)
   Pixel noise, EXIF metadata, PNG text chunks, JPEG DCT analysis,
   color statistics. Evidence-based, calibrated, no external API.

2. GEMINI VLM AUGMENTATION (optional, runs only if API key is configured)
   Uses Gemini as a secondary, corroborating signal — NOT as the primary
   verdict source. Its output is clearly marked as INFERRED and only
   used to augment (not override) forensic findings.

The two pipelines are merged with clear provenance of each finding.
"""
import json
import logging
from typing import Any, Dict, Optional

from app.config import settings
from app.core.forensics import run_forensic_analysis

logger = logging.getLogger(__name__)

# ── Gemini client (optional) ──────────────────────────────────────────────────
_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    key = settings.GEMINI_API_KEY
    if not key:
        return None
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=key)
        logger.info("Gemini client initialised for optional VLM augmentation.")
    except Exception as e:
        logger.warning("Failed to initialise Gemini client: %s", e)
        _gemini_client = None
    return _gemini_client


# ── Gemini augmentation prompt ────────────────────────────────────────────────
_GEMINI_PROMPT = """You are a careful, conservative AI forensics assistant.

Analyse this image and provide a structured second opinion on whether it appears to be AI-generated or authentic.

Rules:
- Only report what you can directly observe in the image.
- Do NOT guess the AI model unless you have strong visual evidence specific to that model.
- Do NOT fabricate certainty. If you are unsure, say so.
- Distinguish between OBSERVED (you can see it) and INFERRED (you are estimating).

Return ONLY valid JSON with this exact structure:
{
  "visual_assessment": "AI_GENERATED" | "LIKELY_AI" | "UNCERTAIN" | "LIKELY_AUTHENTIC" | "AUTHENTIC",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "observed_signals": ["list of specific visual observations supporting your assessment"],
  "model_family_hint": null or "model family name if strongly indicated by specific visual signatures",
  "model_attribution_basis": null or "explain why you think this model if you specified one",
  "manipulation_observations": ["any specific regions or elements that look inconsistent or edited"],
  "reasoning_summary": "2-3 sentence summary of your reasoning"
}"""


def predict_provenance_features(image_bytes: bytes, mime_type: str) -> Optional[Dict[str, Any]]:
    """
    Run the full provenance analysis pipeline.

    Returns a structured dict that the verification endpoint can use to
    augment the ledger-based verdict.

    The dict is structured to match the 7 provenance feature fields
    that verification.py expects, but now backed by real forensic evidence.
    """
    filename = ""  # filename not available here; forensics degrades gracefully

    # ── Step 1: Always run local forensics ────────────────────────────────────
    forensic = None
    try:
        forensic = run_forensic_analysis(image_bytes, mime_type, filename)
        logger.info(
            "Forensics complete — verdict=%s, ai_prob=%.3f, confidence=%s, signals=%d",
            forensic.get("verdict"),
            forensic.get("ai_probability", 0),
            forensic.get("confidence"),
            forensic.get("signals_collected", 0),
        )
    except Exception as e:
        logger.error("Forensic analysis failed: %s", e)

    # ── Step 2: Optional Gemini augmentation ──────────────────────────────────
    gemini_result = None
    client = _get_gemini_client()
    if client and mime_type.startswith("image/"):
        try:
            from google.genai import types
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    _GEMINI_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            gemini_result = json.loads(response.text)
            logger.info(
                "Gemini augmentation complete — assessment=%s, confidence=%s",
                gemini_result.get("visual_assessment"),
                gemini_result.get("confidence"),
            )
        except Exception as e:
            logger.warning("Gemini augmentation skipped: %s", e)
            gemini_result = None

    # ── Step 3: Merge into the 7-feature response format ─────────────────────
    return _build_feature_response(forensic, gemini_result)


def _build_feature_response(
    forensic: Optional[Dict[str, Any]],
    gemini: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Maps forensic + gemini findings into the 7-feature provenance dict
    that verification.py consumes.
    """
    if forensic is None and gemini is None:
        return None

    ai_prob = forensic.get("ai_probability", 0.5) if forensic else 0.5
    verdict = forensic.get("verdict", "INSUFFICIENT_EVIDENCE") if forensic else "INSUFFICIENT_EVIDENCE"
    conf = forensic.get("confidence", "LOW") if forensic else "LOW"
    inferred_model = forensic.get("inferred_model_family") if forensic else None
    attribution_type = forensic.get("attribution_type", "UNKNOWN") if forensic else "UNKNOWN"
    evidence_items = forensic.get("evidence", []) if forensic else []
    manipulation_detected = forensic.get("manipulation_detected", False) if forensic else False
    manipulation_signals = forensic.get("manipulation_signals", []) if forensic else []

    # ── Incorporate Gemini if available ───────────────────────────────────────
    gemini_label = ""
    if gemini:
        g_assess = gemini.get("visual_assessment", "UNCERTAIN")
        g_conf = gemini.get("confidence", "LOW")
        g_model_hint = gemini.get("model_family_hint")
        g_obs = gemini.get("observed_signals", [])
        g_manip = gemini.get("manipulation_observations", [])
        g_summary = gemini.get("reasoning_summary", "")

        gemini_label = f"Gemini VLM: {g_assess} ({g_conf} confidence)"

        # Only update model attribution if Gemini found something AND forensics didn't
        if g_model_hint and not inferred_model:
            inferred_model = f"{g_model_hint} (VLM-inferred)"
            attribution_type = "INFERRED"

        # Add Gemini observations as additional evidence (clearly labelled)
        if g_obs:
            evidence_items.append({
                "name": "Gemini VLM Visual Assessment",
                "status": _gemini_assess_to_status(g_assess),
                "detail": f"[SECONDARY SIGNAL] {g_summary or ', '.join(g_obs[:3])}"
            })

        # Merge manipulation signals
        if g_manip:
            manipulation_signals.extend([f"[VLM] {m}" for m in g_manip[:3]])
            if g_manip:
                manipulation_detected = True

        # Blend scores: forensics has 70% weight, Gemini 30%
        g_prob = _gemini_assess_to_prob(g_assess, g_conf)
        ai_prob = ai_prob * 0.70 + g_prob * 0.30

        # Recalibrate verdict with blended score
        if forensic:
            verdict = _recalculate_verdict(ai_prob, conf, len(evidence_items))

    # ── Build trust info ──────────────────────────────────────────────────────
    trust_level, trust_label = _map_to_trust(verdict, ai_prob, conf, inferred_model, attribution_type)

    # ── Format evidence metrics list ──────────────────────────────────────────
    # Trim to top 5 most informative
    top_evidence = _prioritise_evidence(evidence_items)

    # ── Build model attribution string ────────────────────────────────────────
    if inferred_model:
        if attribution_type == "METADATA_VERIFIED":
            model_str = f"{inferred_model} [Metadata Confirmed]"
        elif attribution_type == "INFERRED":
            model_str = f"{inferred_model} [Inferred — not cryptographically verified]"
        else:
            model_str = inferred_model
    else:
        model_str = "Unknown / Not Determinable"

    # ── Tamper analysis ───────────────────────────────────────────────────────
    tamper_inconsistencies = []
    if manipulation_detected:
        tamper_inconsistencies = manipulation_signals or [
            "Visual analysis detected potential manipulation or AI-editing artefacts."
        ]

    # ── Adversarial test category ─────────────────────────────────────────────
    if verdict == "LIKELY_AI":
        test_category = "AI Synthesis Detection"
        resilience = f"Synthetic content detected (AI prob: {ai_prob*100:.0f}%){' — ' + gemini_label if gemini_label else ''}"
    elif verdict == "POSSIBLY_AI":
        test_category = "AI Synthesis Detection (Uncertain)"
        resilience = f"Moderate synthetic signals (AI prob: {ai_prob*100:.0f}%){' — ' + gemini_label if gemini_label else ''}"
    elif verdict == "LIKELY_AUTHENTIC":
        test_category = "Authenticity Verification"
        resilience = f"Authentic signals detected (AI prob: {ai_prob*100:.0f}%)"
    else:
        test_category = "Inconclusive Analysis"
        resilience = f"Insufficient evidence for definitive classification (AI prob: {ai_prob*100:.0f}%)"

    return {
        # Feature 1: Provenance verification signal
        "provenance_verification": verdict,

        # Feature 2: Trust
        "provenance_trust": {
            "level": trust_level,
            "label": trust_label,
        },
        # Additional evidence metrics (for trust card)
        "evidence_metrics": top_evidence,

        # Feature 3: Transformation
        "transformation_handling": {
            "is_transformed": manipulation_detected,
            "transformation_type": "AI Editing / Manipulation" if manipulation_detected else None,
        },

        # Feature 4: Multi-system provenance
        "multi_system_provenance": _build_pipeline(inferred_model, attribution_type),

        # Feature 5: Tamper detection
        "tamper_detection": {
            "has_tampering": manipulation_detected,
            "inconsistencies": tamper_inconsistencies,
            "tamper_type": "AI Generation / Manipulation" if manipulation_detected else None,
        },

        # Feature 6: Privacy — unchanged, pass through
        "privacy_preserving": {
            "zero_knowledge_active": False,
            "redacted_fields": [],
        },

        # Feature 7: Adversarial testing
        "adversarial_testing": {
            "test_category": test_category,
            "resilience_result": resilience,
        },

        # Extra fields consumed by verification.py for building origin/status
        "_forensic_verdict": verdict,
        "_ai_probability": round(ai_prob, 3),
        "_confidence": conf,
        "_inferred_model": model_str,
        "_attribution_type": attribution_type,
    }


def _gemini_assess_to_prob(assessment: str, confidence: str) -> float:
    """Convert Gemini's string assessment to a numeric probability."""
    conf_mult = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}.get(confidence, 0.5)
    base = {
        "AI_GENERATED": 0.95,
        "LIKELY_AI": 0.75,
        "UNCERTAIN": 0.50,
        "LIKELY_AUTHENTIC": 0.25,
        "AUTHENTIC": 0.05,
    }.get(assessment, 0.50)
    # Dampen with confidence — uncertain Gemini readings move toward 0.5
    return base * conf_mult + 0.5 * (1 - conf_mult)


def _gemini_assess_to_status(assessment: str) -> str:
    """Map Gemini assessment string to evidence status."""
    return {
        "AI_GENERATED": "fail",
        "LIKELY_AI": "fail",
        "UNCERTAIN": "warn",
        "LIKELY_AUTHENTIC": "pass",
        "AUTHENTIC": "pass",
    }.get(assessment, "warn")


def _recalculate_verdict(ai_prob: float, confidence: str, num_signals: int) -> str:
    from app.core.forensics import _determine_verdict
    return _determine_verdict(ai_prob, confidence, num_signals)


def _map_to_trust(
    verdict: str,
    ai_prob: float,
    confidence: str,
    inferred_model: Optional[str],
    attribution_type: str,
) -> tuple:
    """Map forensic verdict to frontend trust level + label."""
    if verdict == "LIKELY_AI":
        if confidence == "HIGH":
            return "UNTRUSTED", f"AI GENERATED - {int(ai_prob*100)}% CONFIDENCE"
        return "UNTRUSTED", f"LIKELY AI GENERATED ({int(ai_prob*100)}%)"
    if verdict == "POSSIBLY_AI":
        return "MEDIUM", f"UNCERTAIN - POSSIBLE AI ({int(ai_prob*100)}%)"
    if verdict == "LIKELY_AUTHENTIC":
        return "HIGH", f"LIKELY AUTHENTIC - {int((1-ai_prob)*100)}% CONFIDENCE"
    # INSUFFICIENT_EVIDENCE
    return "UNREGISTERED", "INSUFFICIENT FORENSIC EVIDENCE"


def _prioritise_evidence(items: list) -> list:
    """Sort evidence by informativeness (fail > warn > pass), cap at 6."""
    order = {"fail": 0, "warn": 1, "pass": 2}
    sorted_items = sorted(items, key=lambda x: order.get(x.get("status", "warn"), 1))
    return sorted_items[:6]


def _build_pipeline(inferred_model: Optional[str], attribution_type: str) -> list:
    """Build multi-system pipeline list for the frontend."""
    pipeline = [{"system_name": "ProvLedger Forensic Engine", "role": "Local Analysis (EXIF, DCT, Noise, Color)"}]
    if _get_gemini_client():
        pipeline.append({"system_name": "Gemini 2.5 Flash", "role": "Secondary VLM Augmentation (INFERRED)"})
    if inferred_model:
        label = "Detected Generator" if attribution_type == "METADATA_VERIFIED" else "Inferred Generator (not verified)"
        pipeline.append({"system_name": inferred_model, "role": label})
    return pipeline
