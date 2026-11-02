"""
Gemini AI Client with model discovery, rate-limiting resilience, and offline fallback.
Loads API key securely from environment variable or .env file.
"""
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from app.ai.prompt_templates import (
    REQUIREMENT_ANALYSIS_SYSTEM_PROMPT,
    BOM_GENERATION_SYSTEM_PROMPT
)
from app.ai.response_validator import (
    RequirementAnalysisResult,
    BOMGenerationResult
)
from app.ai.offline_fallback import (
    get_offline_requirement_analysis,
    get_offline_bom_18kw_atv630
)

# Load environment variables without overriding system env
load_dotenv()

logger = logging.getLogger("AIPanelDesigner.GeminiClient")


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self._client = None
        self._available_models: List[str] = []
        self._init_client()

    def _init_client(self):
        """Safely initialize the google-genai client without leaking secrets."""
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Google GenAI client successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize GenAI client: {str(e)}")
                self._client = None
        else:
            logger.info("No GEMINI_API_KEY provided; offline fallback will be active.")
            self._client = None

    def update_settings(self, api_key: str, model_name: str):
        """Update API key and model on the fly."""
        self.api_key = api_key
        self.model_name = model_name
        self._init_client()

    def get_available_models(self) -> List[str]:
        """Discover available models from Gemini API."""
        if not self._client:
            return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b"]
        
        try:
            models = self._client.models.list()
            flash_models = []
            all_models = []
            for m in models:
                name = m.name.replace("models/", "")
                all_models.append(name)
                if "flash" in name.lower() or "gemini" in name.lower():
                    flash_models.append(name)
            
            # Prefer flash models for cost-efficiency
            if flash_models:
                self._available_models = flash_models
            else:
                self._available_models = all_models
            return self._available_models
        except Exception as e:
            logger.warning(f"Model discovery error: {str(e)}")
            return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    def _clean_json_text(self, text: str) -> str:
        """Strip markdown code blocks or surrounding text to get raw JSON."""
        # Find ```json ... ``` or ``` ... ```
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        # Fallback to finding outermost { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1].strip()
        return text.strip()

    def analyze_requirement(self, user_requirement: str) -> Dict[str, Any]:
        """
        Extract structured electrical parameters from natural language requirement.
        Falls back to rule-based offline analysis if API fails.
        """
        if not self._client or not self.api_key:
            logger.info("Using offline requirement analysis.")
            return get_offline_requirement_analysis(user_requirement)

        prompt = f"{REQUIREMENT_ANALYSIS_SYSTEM_PROMPT}\n\nUser Requirement:\n\"{user_requirement}\""
        
        try:
            logger.info(f"Calling Gemini model {self.model_name} for requirement analysis...")
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            raw_text = response.text or ""
            cleaned = self._clean_json_text(raw_text)
            parsed = json.loads(cleaned)
            # Validate with Pydantic
            validated = RequirementAnalysisResult.model_validate(parsed)
            return validated.model_dump()
        except Exception as e:
            logger.warning(f"Gemini API call failed ({str(e)}). Using offline requirement analysis.")
            return get_offline_requirement_analysis(user_requirement)

    def generate_bom(
        self,
        requirement_data: Dict[str, Any],
        manufacturer_selections: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Generate preliminary engineering BOM.
        Falls back to offline verified BOM if API fails.
        """
        if not self._client or not self.api_key:
            logger.info("Using offline verified BOM generation.")
            return get_offline_bom_18kw_atv630(manufacturer_selections)

        prompt = (
            f"{BOM_GENERATION_SYSTEM_PROMPT}\n\n"
            f"PANEL SPECIFICATION:\n"
            f"- Application: {requirement_data.get('application', '18.5 kW VFD Panel')}\n"
            f"- Motor Rating: {requirement_data.get('motor_kw', 18.5)} kW ({requirement_data.get('motor_kw_note', '')})\n"
            f"- Voltage: {requirement_data.get('supply_voltage', 415)}V AC, {requirement_data.get('phases', 3)}-Phase, 50Hz\n"
            f"- Drive Type: {requirement_data.get('drive_type', 'Schneider ATV630')}\n"
            f"- Ingress Protection: {requirement_data.get('ip_rating', 'IP54')}\n"
            f"- Control Mode: {requirement_data.get('control_type', 'Local/Remote')}\n"
            f"- Cable Entry: {requirement_data.get('cable_entry', 'Bottom')}\n\n"
            f"SELECTED MANUFACTURERS:\n"
            f"{json.dumps(manufacturer_selections, indent=2)}\n\n"
            f"Generate the comprehensive BOM JSON:"
        )

        try:
            logger.info(f"Calling Gemini model {self.model_name} for BOM generation...")
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            raw_text = response.text or ""
            cleaned = self._clean_json_text(raw_text)
            parsed = json.loads(cleaned)
            validated = BOMGenerationResult.model_validate(parsed)
            return [c.model_dump() for c in validated.components]
        except Exception as e:
            logger.warning(f"Gemini BOM generation failed ({str(e)}). Using offline verified dataset.")
            return get_offline_bom_18kw_atv630(manufacturer_selections)

