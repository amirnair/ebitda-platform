"""
billet_engine.py
----------------
Implements §4.4 Billet Procurement Engine.

Calculates:
    1. Billet required today (from production plan)
    2. Billet draw-down from stock
    3. Procurement recommendation for next delivery window
    4. Alert if billet stock will fall below safety level

Billet types and SKU mapping (§4.4):
    P1-6M    → P1 8mm, 10mm, 12mm, 16mm, 20mm
    P1-5.6M  → P1 25mm
    P1-5.05M → P1 32mm
    P2-6M    → P2 8mm, 10mm, 12mm, 16mm, 20mm
    P2-5.6M  → P2 25mm
    P2-4.9M  → P2 32mm

Rolling factor: 1.05 (§1.5) — uniform across all SKUs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from optimiser.sku_capacity import ROLLING_FACTOR, SKU_CAPACITY, ALL_SKU_CODES

# ---------------------------------------------------------------------------
# Billet type → SKU mapping (§4.4)
# ---------------------------------------------------------------------------
BILLET_TYPE_TO_SKUS: Dict[str, List[str]] = {
    "P1-6M":    ["P1-SKU-8", "P1-SKU-10", "P1-SKU-12", "P1-SKU-16", "P1-SKU-20"],
    "P1-5.6M":  ["P1-SKU-25"],
    "P1-5.05M": ["P1-SKU-32"],
    "P2-6M":    ["P2-SKU-8", "P2-SKU-10", "P2-SKU-12", "P2-SKU-16", "P2-SKU-20"],
    "P2-5.6M":  ["P2-SKU-25"],
    "P2-4.9M":  ["P2-SKU-32"],
}

# Reverse: sku_code → billet_type (derived from sku_capacity.py)
SKU_TO_BILLET_TYPE: Dict[str, str] = {
    sku_code: rec.billet_type
    for sku_code, rec in SKU_CAPACITY.items()
}

ALL_BILLET_TYPES = list(BILLET_TYPE_TO_SKUS.keys())
P1_BILLET_TYPES = [bt for bt in ALL_BILLET_TYPES if bt.startswith("P1")]
P2_BILLET_TYPES = [bt for bt in ALL_BILLET_TYPES if bt.startswith("P2")]

# Safety stock: days of billet to keep on hand
BILLET_SAFETY_DAYS: float = 3.0
# Procurement lead time: days to order ahead
PROCUREMENT_LEAD_DAYS: int = 2


@dataclass
class BilletStockState:
    """Current billet inventory by type."""
    billet_type: str
    qty_mt: float        # Current stock (MT)
    brand: str           # P1 or P2

    @property
    def is_p1(self) -> bool:
        return self.brand == "P1"


@dataclass
class BilletDrawdown:
    """Billet consumed from stock to fulfil today's production plan."""
    billet_type: str
    brand: str
    required_mt: float       # Billet required for today's plan
    available_mt: float      # Current stock
    drawdown_mt: float       # min(required, available)
    shortfall_mt: float      # max(0, required - available)
    closing_stock_mt: float  # available - drawdown
    is_critical: bool        # closing_stock < safety_threshold


@dataclass
class ProcurementRecommendation:
    """Purchase recommendation for one billet type."""
    billet_type: str
    brand: str
    closing_stock_mt: float          # After today's drawdown
    daily_consumption_mt: float      # Based on today's plan
    days_of_stock: float             # closing / daily_consumption
    safety_stock_mt: float           # BILLET_SAFETY_DAYS × daily
    order_quantity_mt: float         # Recommended order
    urgency: str                     # "CRITICAL" / "LOW" / "ADEQUATE"
    procurement_trigger: bool        # True if order should be placed


@dataclass
class BilletProcurementReport:
    """Full billet procurement output for one day."""
    planning_date: object
    company_id: str
    drawdowns: List[BilletDrawdown]
    recommendations: List[ProcurementRecommendation]
    total_billet_required_p1_mt: float
    total_billet_required_p2_mt: float
    total_billet_available_p1_mt: float
    total_billet_available_p2_mt: float
    critical_alerts: List[str] = field(default_factory=list)

    @property
    def has_critical_alerts(self) -> bool:
        return len(self.critical_alerts) > 0


def calculate_billet_requirements(
    production_plan: Dict[str, float],  # sku_code → production_mt
) -> Dict[str, float]:
    """
    Convert a production plan (SKU → MT) into billet requirements
    (billet_type → MT required).

    Uses rolling_factor = 1.05: 1.05 tonnes of billet → 1 tonne of TMT.
    """
    billet_req: Dict[str, float] = {bt: 0.0 for bt in ALL_BILLET_TYPES}
    for sku_code, prod_mt in production_plan.items():
        if prod_mt <= 0:
            continue
        billet_type = SKU_TO_BILLET_TYPE.get(sku_code)
        if billet_type:
            billet_req[billet_type] += prod_mt * ROLLING_FACTOR
    return {k: round(v, 3) for k, v in billet_req.items()}


def run_billet_engine(
    planning_date,
    company_id: str,
    production_plan: Dict[str, float],   # sku_code → production_mt (from LP)
    billet_stocks: Dict[str, float],     # billet_type → current stock MT
    forecast_demand: Optional[Dict[str, float]] = None,  # sku_code → demand MT
) -> BilletProcurementReport:
    """
    Full billet procurement engine.

    Args:
        planning_date:    Date of plan.
        company_id:       Multi-tenant key.
        production_plan:  LP output — how much of each SKU to produce.
        billet_stocks:    Current billet inventory by type.
        forecast_demand:  SKU-level demand forecast (used for safety stock calc).

    Returns:
        BilletProcurementReport with drawdowns + procurement recommendations.
    """
    billet_required = calculate_billet_requirements(production_plan)

    drawdowns: List[BilletDrawdown] = []
    recommendations: List[ProcurementRecommendation] = []
    critical_alerts: List[str] = []

    # Daily demand per billet type (from forecast) for safety stock calc
    daily_demand_by_billet: Dict[str, float] = {}
    if forecast_demand:
        for sku_code, demand_mt in forecast_demand.items():
            bt = SKU_TO_BILLET_TYPE.get(sku_code)
            if bt:
                daily_demand_by_billet[bt] = (
                    daily_demand_by_billet.get(bt, 0.0) + demand_mt * ROLLING_FACTOR
                )

    for billet_type in ALL_BILLET_TYPES:
        brand = "P1" if billet_type.startswith("P1") else "P2"
        required = billet_required.get(billet_type, 0.0)
        available = billet_stocks.get(billet_type, 0.0)
        drawdown = min(required, available)
        shortfall = max(0.0, required - available)
        closing = available - drawdown

        # Safety threshold
        daily_consumption = daily_demand_by_billet.get(billet_type, required)
        safety_mt = BILLET_SAFETY_DAYS * daily_consumption
        is_critical = closing < safety_mt and daily_consumption > 0

        drawdowns.append(BilletDrawdown(
            billet_type=billet_type,
            brand=brand,
            required_mt=round(required, 3),
            available_mt=round(available, 3),
            drawdown_mt=round(drawdown, 3),
            shortfall_mt=round(shortfall, 3),
            closing_stock_mt=round(closing, 3),
            is_critical=is_critical,
        ))

        if shortfall > 0:
            critical_alerts.append(
                f"BILLET SHORTFALL: {billet_type} — need {required:.1f} MT, "
                f"have {available:.1f} MT, shortfall {shortfall:.1f} MT"
            )

        # Procurement recommendation
        days_of_stock = closing / daily_consumption if daily_consumption > 0 else float("inf")

        if days_of_stock < 1.0:
            urgency = "CRITICAL"
            trigger = True
        elif days_of_stock < BILLET_SAFETY_DAYS:
            urgency = "LOW"
            trigger = True
        else:
            urgency = "ADEQUATE"
            trigger = False

        # Order quantity: top up to BILLET_SAFETY_DAYS + PROCUREMENT_LEAD_DAYS of stock
        target_stock = (BILLET_SAFETY_DAYS + PROCUREMENT_LEAD_DAYS) * daily_consumption
        order_qty = max(0.0, target_stock - closing) if trigger else 0.0

        recommendations.append(ProcurementRecommendation(
            billet_type=billet_type,
            brand=brand,
            closing_stock_mt=round(closing, 3),
            daily_consumption_mt=round(daily_consumption, 3),
            days_of_stock=round(days_of_stock, 1) if days_of_stock != float("inf") else 999.0,
            safety_stock_mt=round(safety_mt, 3),
            order_quantity_mt=round(order_qty, 2),
            urgency=urgency,
            procurement_trigger=trigger,
        ))

    total_req_p1 = sum(billet_required[bt] for bt in P1_BILLET_TYPES)
    total_req_p2 = sum(billet_required[bt] for bt in P2_BILLET_TYPES)
    total_avail_p1 = sum(billet_stocks.get(bt, 0.0) for bt in P1_BILLET_TYPES)
    total_avail_p2 = sum(billet_stocks.get(bt, 0.0) for bt in P2_BILLET_TYPES)

    return BilletProcurementReport(
        planning_date=planning_date,
        company_id=company_id,
        drawdowns=drawdowns,
        recommendations=recommendations,
        total_billet_required_p1_mt=round(total_req_p1, 3),
        total_billet_required_p2_mt=round(total_req_p2, 3),
        total_billet_available_p1_mt=round(total_avail_p1, 3),
        total_billet_available_p2_mt=round(total_avail_p2, 3),
        critical_alerts=critical_alerts,
    )
