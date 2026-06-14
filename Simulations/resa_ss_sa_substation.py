#!/usr/bin/env python3
"""
Simulations/resa_ss_sa_substation.py
====================================

RESA POWER service-entrance switchboard RPS-666530-1 — order model for the
live diagram simulator.

Truth: specifications transcribed from Sergey's AutoCAD Electrical drawing
RPS-666530-1 (1600A, SCE N1 / PG&E, EUSERC), shared 2026-06-14. Clearly
legible items are encoded verbatim; the Section #4 branch-breaker schedule is
too small to read off the photo and is marked "per drawing — confirm".
Label: SIMULATION — not a licensed PE drawing or as-built document.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TRUTH_LABEL = "RESA_RPS_666530_1_SWBD_SIM_V2"
ORDER_ID = "RPS-666530-1"
VENDOR = "RESA POWER"
VENDOR_ADDRESS = "16833 Edwards Road, Cerritos, CA 90703"
SERVICE = "1600A · SCE N1 / PG&E · EUSERC"
SYSTEM = "240V 3-phase · 65 kAIC"
SYSTEM_V = 240
AIC_KA = 65
SHIP_DATE = "Per RESA quote"


@dataclass(frozen=True)
class BreakerSpec:
    count: int
    amps: int
    trip_label: str
    voltage_v: int = 240
    aic_ka: int = 65
    mount: str = "Group-mount"


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
                "id": "SECTION #1",
                "name": "Main + Incoming Pull",
                "mechanical": [
                    "Supply 1600A / Section 1600A",
                    "Main 1600AT (2000AF) 3P, 65 kAIC @ 240V",
                    "LSI trip · RELT maintenance switch",
                    "Incoming pull: (4) EUSERC press bolts per L-N · access 35 in",
                ],
                "electrical": [
                    "MCB 1600AT/2000AF 3P 65kAIC@240V LSI",
                    "RELT reduced-energy let-through (maintenance)",
                    "EUSERC 345 / ESR 6-14",
                    "EUSERC 347 / ESR 6-12",
                ],
                "sld_symbol": "MAIN",
                "amps": 1600,
            },
            {
                "id": "SECTION #2",
                "name": "Utility Metering + FCB-1",
                "mechanical": [
                    "Supply 1600A / Section 400A",
                    "Utility metering compartment · 15CLP",
                    "FCB-1 400AT/400AF feeder",
                    "TM/POD · 80% rated",
                ],
                "electrical": [
                    "EUSERC 325 · KRP-SCE ESR-6 (6-7)",
                    "SCE/EUSERC 320, 332",
                    "SCE ESR-6 (6-19)(6-24)",
                    "FCB-1 400AT/400AF 3P TM/POD 80% rated",
                ],
                "sld_symbol": "METER_FEED",
                "amps": 400,
            },
            {
                "id": "SECTION #3",
                "name": "Utility Metering + FCB-2",
                "mechanical": [
                    "Supply 1600A / Section 400A",
                    "Utility metering compartment · 15CLP",
                    "FCB-2 400AT/400AF feeder",
                    "TM/POD · 80% rated",
                ],
                "electrical": [
                    "EUSERC 325 · KRP-SCE ESR-6 (6-7)",
                    "SCE/EUSERC 320, 332",
                    "SCE ESR-6 (6-19)(6-24)",
                    "FCB-2 400AT/400AF 3P TM/POD 80% rated",
                ],
                "sld_symbol": "METER_FEED",
                "amps": 400,
            },
            {
                "id": "SECTION #4",
                "name": "1200A Distribution",
                "mechanical": [
                    "Supply 1600A / Section 1200A",
                    "Distribution breakers + branch sub-panel",
                    "SCE ESR-6 (6-10)(6-28)(6-29)",
                    "EUSERC 306, 353, 304",
                ],
                "electrical": [
                    "1200A distribution section",
                    "Branch-breaker schedule per drawing (confirm)",
                    "Panel of branch breakers (TYP)",
                ],
                "sld_symbol": "DIST",
                "amps": 1200,
            },
        ),
        # Feeder taps off the 1600A main — drives the single-line / three-line.
        distribution_sections=(
            {
                "id": "SECTION #2",
                "name": "FCB-1",
                "breakers": [
                    {"count": 1, "amps": 400, "trip_label": "FCB-1 400AT/400AF 3P TM/POD 80%"},
                ],
            },
            {
                "id": "SECTION #3",
                "name": "FCB-2",
                "breakers": [
                    {"count": 1, "amps": 400, "trip_label": "FCB-2 400AT/400AF 3P TM/POD 80%"},
                ],
            },
            {
                "id": "SECTION #4",
                "name": "1200A Distribution",
                "breakers": [
                    {"count": 1, "amps": 1200, "trip_label": "1200A Section (panel schedule per dwg)"},
                ],
            },
        ),
        misc={
            "service": SERVICE,
            "system": SYSTEM,
            "main": "1600AT/2000AF 3P 65kAIC@240V LSI · RELT",
            "warranty": "1 Year Warranty",
            "base": (
                "Min front clearance 38 in · Base 11 + 25 = 38 in · "
                "Padlockable handle, 3-point latch · Louvers w/ filters · "
                "EUSERC 354 · PG&E PG.1A FIG 10-32"
            ),
            "notes": [
                "EACH SECTION TO BE SHIPPED INDIVIDUALLY",
                "Transcribed from RPS-666530-1 (AutoCAD Electrical) — confirm Section #4 schedule",
            ],
        },
        lead_time={
            "drawings": "2-4 weeks ARO",
            "shipping": "Per RESA quote",
        },
    )


def proof_of_property() -> dict[str, Any]:
    order = default_order()
    return {
        "P_n": "RESA RPS-666530-1 switchboard renders as animated single-line + three-line + mechanical sim",
        "order_id": order.order_id,
        "service": order.misc["service"],
        "system": order.misc["system"],
        "sections": len(order.sections),
        "feeder_taps": order.total_breakers,
        "falsifier": "missing section or zero animated elements on energize",
        "truth_label": "SIMULATION",
        "engineering_stamp": "FOR_PRESENTATION_NOT_PE_STAMPED",
        "transcription": "Section #4 branch schedule unread from photo — confirm",
    }
