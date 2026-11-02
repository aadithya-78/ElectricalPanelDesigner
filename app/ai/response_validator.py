"""
Pydantic schemas and response validation for AI outputs.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ClarificationQuestion(BaseModel):
    question: str
    options: List[str] = Field(default_factory=list)


class RequirementAnalysisResult(BaseModel):
    application: str = "Variable Speed Drive Panel"
    motor_kw: float = 18.5
    motor_kw_note: str = ""
    supply_voltage: int = 415
    phases: int = 3
    frequency_hz: int = 50
    drive_type: str = "Schneider ATV630"
    motor_quantity: int = 1
    control_type: str = "Local/Remote with Emergency Stop"
    ip_rating: str = "IP54"
    installation: str = "Indoor"
    cable_entry: str = "Bottom"
    ambient_temp_c: float = 40.0
    full_load_current_amps: float = 38.0
    preferred_brands: Dict[str, str] = Field(default_factory=dict)
    provisional_assumptions: List[str] = Field(default_factory=list)
    clarification_needed: List[ClarificationQuestion] = Field(default_factory=list)


class BOMComponentItem(BaseModel):
    item_no: int
    category: str = "Power"
    name: str
    manufacturer: str = "Generic"
    part_number: Optional[str] = None
    part_number_verified: bool = False
    description: str = ""
    quantity: int = 1
    width_mm: float = 50.0
    height_mm: float = 75.0
    depth_mm: float = 60.0
    mounting_type: str = "Plate"
    clearance_top_mm: float = 10.0
    clearance_bottom_mm: float = 10.0
    clearance_sides_mm: float = 5.0
    heat_loss_watts: float = 0.0
    unit_price: float = 0.0
    is_optional: bool = False
    reason: Optional[str] = ""
    notes: Optional[str] = ""


class BOMGenerationResult(BaseModel):
    summary: str = "Engineering BOM"
    components: List[BOMComponentItem] = Field(default_factory=list)

