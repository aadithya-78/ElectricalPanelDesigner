"""
Preliminary Thermal Estimation and Cooling Calculation for Electrical Panels.
Formulas:
  Q_total = Sum(P_loss * Qty) [Watts]
  Surface Area A = 2*(W*H + W*D + H*D) [m^2]
  Q_natural = k * A * (T_internal - T_ambient) [Watts]
  Where k ~ 5.5 W/(m^2*K) for painted sheet steel enclosure.
  Q_excess = Q_total - Q_natural
  Airflow V = (3.1 * Q_excess) / delta_T [m^3/h]
"""
from typing import Dict, Any
from app.models.enclosure import Enclosure
from app.models.bom import BOM


class ThermalCalculator:
    HEAT_TRANSFER_COEFF = 5.5  # W/(m^2 * K) for painted sheet steel

    @classmethod
    def calculate(
        cls,
        bom: BOM,
        enclosure: Enclosure,
        ambient_temp_c: float = 35.0,
        target_internal_temp_c: float = 45.0
    ) -> Dict[str, Any]:
        """Compute heat dissipation balance and preliminary cooling recommendation."""
        total_heat_watts = bom.total_heat_loss()
        
        # Enclosure surface area in m^2 (excluding bottom mounting / floor contact if floor mount)
        w_m = enclosure.width / 1000.0
        h_m = enclosure.height / 1000.0
        d_m = enclosure.depth / 1000.0
        
        # Total effective heat exchange area (Top + 2 Sides + Front + Back)
        total_area_m2 = 2.0 * (w_m * h_m + w_m * d_m + h_m * d_m)
        effective_cooling_area_m2 = total_area_m2 * 0.85 # 15% reduction for back wall and bottom

        delta_t = max(1.0, target_internal_temp_c - ambient_temp_c)
        natural_dissipation_watts = cls.HEAT_TRANSFER_COEFF * effective_cooling_area_m2 * delta_t
        
        excess_heat_watts = max(0.0, total_heat_watts - natural_dissipation_watts)

        # Airflow calculation (m3/h)
        if excess_heat_watts > 0:
            required_airflow_m3h = round((3.1 * excess_heat_watts) / delta_t, 1)
        else:
            required_airflow_m3h = 0.0

        # Recommendation logic
        if excess_heat_watts <= 0:
            recommendation = "Natural Convection (No fan required; enclosure surface area is sufficient)"
            fan_type = "None"
        elif required_airflow_m3h < 120:
            recommendation = f"Standard Filter Fan ({int(required_airflow_m3h * 1.3)} m³/h recommended with bottom inlet filter)"
            fan_type = "Filter Fan"
        elif required_airflow_m3h < 500:
            recommendation = f"High-Capacity Filter Fan ({int(required_airflow_m3h * 1.25)} m³/h recommended with exhaust roof/side fan)"
            fan_type = "High-Capacity Filter Fan"
        else:
            recommendation = f"Enclosure Air Conditioner required (~{round(excess_heat_watts/1000.0, 1)} kW cooling capacity) to maintain IP rating and internal temp"
            fan_type = "Air Conditioner"

        return {
            "total_heat_loss_watts": total_heat_watts,
            "ambient_temp_c": ambient_temp_c,
            "target_internal_temp_c": target_internal_temp_c,
            "delta_t_k": delta_t,
            "enclosure_surface_area_m2": round(total_area_m2, 2),
            "natural_dissipation_watts": round(natural_dissipation_watts, 1),
            "excess_heat_watts": round(excess_heat_watts, 1),
            "required_airflow_m3h": required_airflow_m3h,
            "cooling_recommendation": recommendation,
            "cooling_type": fan_type,
            "requires_forced_cooling": excess_heat_watts > 0,
            "warning": "Detailed thermal CFD validation is required for high ambient industrial environments (>45°C)."
        }

