#!/usr/bin/env python3
"""
Simulations/resa_ss_sa_substation.py
====================================

RESA POWER Unit Substation SS-SA — order model for the live diagram simulator.

Truth: specifications transcribed from Architect order images (2026-06-13).
Label: SIMULATION — not a licensed PE drawing or as-built document.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TRUTH_LABEL = "RESA_SS_SA_SUBSTATION_SIM_V1"
ORDER_ID = "SS-SA"
VENDOR = "RESA POWER"
VENDOR_ADDRESS = "16833 Edwards Road, Cerritos, CA 90703"
SHIP_DATE = "2026-09-28"


@dataclass(frozen=True)
class BreakerSpec:
    count: int
    amps: int
    trip_label: str
    voltage_v: int = 480
    aic_ka: int = 65
    mount: str = "Bolt-on"


@dataclass(frozen=True)
class SubstationOrder:
    order_id: str
    vendor: str
    sections: tuple[dict[str, Any], ...]
    distribution_sections: tuple[dict[str, Any], ...]
    misc: dict[str, Any]
    lead_time: dict[str, str]

    @property
    def breaker_inventory(self) -> list[BreakerSpec]:
        out: list[BreakerSpec] = []
        for block in self.distribution_sections:
            for br in block.get("breakers", []):
                out.append(BreakerSpec(**br))
        return out

    @property
    def total_breakers(self) -> int:
        return sum(b.count for b in self.breaker_inventory)


def default_order() -> SubstationOrder:
    return SubstationOrder(
        order_id=ORDER_ID,
        vendor=VENDOR,
        sections=(
            {
                "id": "S1",
                "name": "Load Interrupter Switch Section",
                "mechanical": [
                    "Indoor NEMA 1 steel enclosure",
                    "Tin-plated copper bus, 3-wire",
                    "15 kV max / 12 kV system",
                ],
                "electrical": [
                    "600 A load-interrupter switch",
                    "Fuses by others",
                    "UL listed LI switch",
                ],
                "sld_symbol": "LI_SWITCH",
                "hv_kv": 12.47,
            },
            {
                "id": "S2",
                "name": "Transformer Section",
                "mechanical": [
                    "2500 kVA dry-type transformer",
                    "Indoor enclosure",
                    "Copper windings",
                ],
                "electrical": [
                    "HV 12,470 V pigtail",
                    "LV 480Y/277 V flex",
                    "Dry-type substation transformer",
                ],
                "sld_symbol": "TRANSFORMER",
                "kva": 2500,
                "hv_kv": 12.47,
                "lv_v": 480,
            },
            {
                "id": "S3",
                "name": "Main Section",
                "mechanical": [
                    "NEMA 1 indoor lineup section",
                    "Copper bus 4000 A",
                ],
                "electrical": [
                    "4000 A / 480Y/277 V / 3P4W",
                    "65 kAIC",
                    "4000 A fusible bolt-pressure switch AFGFR",
                    "ERMS kit",
                    "Power Logic PM8000",
                    "(3) 4000:5 CT",
                ],
                "sld_symbol": "MAIN_SWITCH",
                "amps": 4000,
                "aic_ka": 65,
            },
        ),
        distribution_sections=(
            {
                "id": "S4",
                "name": "Distribution Section 4",
                "breakers": [
                    {"count": 3, "amps": 1000, "trip_label": "1000A"},
                    {"count": 4, "amps": 800, "trip_label": "800A"},
                ],
            },
            {
                "id": "S5",
                "name": "Distribution Section 5",
                "breakers": [
                    {"count": 2, "amps": 600, "trip_label": "600A"},
                    {"count": 1, "amps": 600, "trip_label": "450AT/600A"},
                    {"count": 1, "amps": 400, "trip_label": "400A"},
                    {"count": 1, "amps": 400, "trip_label": "350AT/400A"},
                ],
            },
        ),
        misc={
            "warranty": "1 Year Warranty",
            "deliverables": [
                "Front elevation drawings for GC submittal",
                "Summarized bill of materials",
                "Square D products listed on proposal",
            ],
            "notes": ["Adder for LI switch", "Shipping lead time per RESA quote"],
        },
        lead_time={
            "drawings": "2-4 weeks ARO",
            "shipping": "24-26 weeks after drawing approval",
        },
    )


def proof_of_property() -> dict[str, Any]:
    order = default_order()
    return {
        "P_n": "RESA SS-SA order renders as animated SLD + 3-line + mechanical sim",
        "order_id": order.order_id,
        "sections": len(order.sections),
        "distribution_sections": len(order.distribution_sections),
        "total_breakers": order.total_breakers,
        "falsifier": "missing section or zero animated elements on energize",
        "truth_label": "SIMULATION",
        "engineering_stamp": "FOR_PRESENTATION_NOT_PE_STAMPED",
    }