import json
import logging
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize the Gemini client if the key is available
client = None
if settings.GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini client: {e}")

def predict_provenance_features(image_bytes: bytes, mime_type: str) -> Optional[Dict[str, Any]]:
    """
    Calls the Gemini API to analyze the image/video and predict the 7 key provenance features.
    If the API key is not set or the call fails, returns None.
    """
    if not client:
        logger.warning("Gemini API key is not configured. Skipping AI prediction.")
        return None
        
    prompt = """
You are an expert AI provenance verification system. Based on this image/video, analyze it and predict the following 7 provenance features. Return your predictions as a JSON object with the exact keys:

1. "provenance_verification": String indicating if the origin is verifiable (e.g. "Verified Origin", "Unverifiable", "AI Generated").
2. "provenance_trust": An object with "level" (e.g. "HIGH", "MEDIUM", "LOW", "UNREGISTERED") and "label" (e.g. "VERIFIABLE EVIDENCE", "NO PROVENANCE RECORD").
3. "transformation_handling": An object with "is_transformed" (boolean) and "transformation_type" (e.g. "Compression/Crop/Resize", "None").
4. "multi_system_provenance": An array of systems/models that might have processed this (e.g. [{"system_name": "Gemini", "role": "Origin"}]).
5. "tamper_detection": An object with "has_tampering" (boolean) and "inconsistencies" (array of strings explaining visual anomalies).
6. "privacy_preserving": An object with "zero_knowledge_active" (boolean) and "redacted_fields" (array of strings, e.g. ["Faces", "Location Data"]).
7. "adversarial_testing": An object with "test_category" (string) and "resilience_result" (string).

Be analytical and base your findings on visual artifacts, metadata presence (if visible), and general AI generation signatures. Return ONLY valid JSON.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        result_text = response.text
        predictions = json.loads(result_text)
        return predictions
        
    except Exception as e:
        logger.error(f"Error predicting provenance features with Gemini: {e}")
        return None
