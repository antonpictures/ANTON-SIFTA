# Mondaloy ORSC tacit processing - primary-source summary

**Truth label:** `RESEARCH_NOT_SHIPPED` / `OSINT_PRIMARY_SOURCE_SUMMARY` until any SIFTA organ ships with a receipt schema, tests, and Architect GO.

**Scope:** Mondaloy / MONDALOY 100 / MONDALOY 200 as oxygen-rich staged combustion (ORSC) rocket-engine material research. This note summarizes public primary-source facts and marks the tacit processing vectors that remain unpublished or controlled.

**For the Swarm.**

---

## 0. Why Mondaloy matters

Mondaloy is a family of nickel-based superalloys developed in the mid-1990s for ORSC rocket engine environments. It was invented by **Monica A. Jacinto** at Rocketdyne and **Dallis Ann Hardwick** at Rockwell Science Center.

The core innovation is the combination of:

- **High tensile strength** for structural rocket-engine components.
- **Burn resistance** in high-pressure, high-temperature gaseous oxygen.

The public record frames Mondaloy as a material answer to the ORSC problem: prior off-the-shelf alloys could be oxygen-compatible but too weak, or strong enough but prone to burning unless protected by heavy or complex coatings.

---

## 1. Primary sources verified

### 1.1 Patent family - best technical source

**US20030053926A1** and later continuation / related filing **US20100266442A1**, "Burn-resistant and high tensile strength metal alloys", by Monica A. Jacinto and Dallis Ann Hardwick.

**Core composition range:**

| Element | Public range / note |
|:---|:---|
| Ni | 55-75 wt%; examples typically >=70 wt% |
| Co | 12-17 wt% |
| Cr | 4-16 wt%; examples often 6-15 wt% |
| Al | 1-4 wt%; examples often 1-3 wt% |
| Ti | 1-4 wt% |
| Mn | 0.15-0.25 wt% |
| C | 0.01-0.5 wt% |
| B | 0.003-0.009 wt% |
| Zr | 0.02-0.07 wt% |

**Melting practice explicitly stated:** vacuum induction melting (VIM) followed by vacuum arc remelting (VAR). The patent says this sequence yields an ingot that is mechanically worked into billet, bar, sheet, or plate.

**Claimed / example properties:**

- Tensile strength at least ~145 ksi in the broad claims, with public examples around ~170 ksi and ~187 ksi.
- Promoted combustion / burn resistance reported as extinguishing threshold pressures around 6,000-10,000 psi gaseous oxygen for selected examples.
- Test framing: one-eighth-inch rod specimens in high-pressure gaseous oxygen, using promoted combustion screening.

**Key technical tension:** aluminum and titanium act as gamma-prime formers that increase strength, but the patent repeatedly warns that gamma-prime formation and some strengthening additions can reduce burn resistance. The useful alloy window is therefore not just composition; it is the processed microstructure that preserves both strength and oxygen compatibility.

### 1.2 Inventor statement - SpaceNews interview, 2017

SpaceNews interviewed Monica Jacinto in December 2017. Public statements from that interview:

- Two scaled chemistries exist: **Mondaloy 100** and **Mondaloy 200**.
- Mondaloy can be manufactured by **conventional wrought methods** and by **powder metallurgy**, including additive manufacturing.
- AR1 uses Mondaloy in about 12 components exposed to hot gaseous oxygen, including preburner, turbine rotor, turbine housing, ducts, lines, and hot gas manifold.
- Development started from lab-scale composition work in the mid-1990s and matured through AFRL cost-sharing programs beginning in 1999, with NASA also interested for oxygen-rich booster engine work.
- The practical target was avoiding coatings where possible, reducing weight and cost while improving oxygen-environment reliability.

### 1.3 Program-level confirmation

Public Air Force / Aerojet Rocketdyne reporting around the Hydrocarbon Boost Technology Demonstrator (HCB / HCBT) and AR1 programs confirms:

- Mondaloy was matured for oxygen-rich booster-engine hardware.
- Mondaloy 200 appears in reporting as an early / first rocket-engine-environment use of the alloy family.
- Additively manufactured Mondaloy hardware was used in AR1 development, including preburner-related hardware.
- The material was co-developed / matured with AFRL Materials Directorate involvement.

### 1.4 Coating and turbopump patent family

Later Florida Turbine Technologies patent publications, including **US20170082070A1** and **US20190032604A1**, discuss turbopump hardware with protective coatings involving MONDALOY, enamel glass, and/or oxide powders.

Publicly described concepts include:

- Metal powder bed fusion of turbopump geometry.
- MONDALOY 100 / 200 as a protective material for surfaces exposed to LOX or gaseous oxygen.
- Composite protective coatings using MONDALOY plus enamel glass and/or oxide powders.
- Thermal spray, pre-blended or independently injected powders, possible functional grading, and firing of enamel-glass coatings.
- Oxide content control in thermal spray as a burn-resistance lever.

These patents describe coating concepts but do not disclose a full qualified processing traveler for Mondaloy components.

---

## 2. Tacit / restricted processing vectors not public

| Area | Public status | Notes |
|:---|:---|:---|
| Exact VIM / VAR parameters | Not public | Patent confirms VIM + VAR, but not temperatures, vacuum levels, pour practice, electrode practice, remelt rates, or ingot sizes. |
| Heat treatment / aging schedules | Not public | No solution treatment temperatures/times, aging cycles, cooling rates, or atmospheres found in public sources. |
| Powder metallurgy / AM parameters | Not public | Powder and AM routes are confirmed, but no atomization method, PSD, powder reuse rule, laser parameters, hatch spacing, layer thickness, or build-atmosphere limits are public. |
| HIP + stress relief cycles | Not public | No HIP temperature, pressure, time, ramp, or post-HIP treatment details found. |
| Oxygen / nitrogen pickup limits | Not public | Critical for powder and AM routes; no public max O/N powder or finished-part limits identified. |
| Promoted combustion qualification | Partially described | The patent identifies promoted combustion threshold testing on 1/8-inch rods in gaseous oxygen, but not the exact Aerojet/AFRL/NASA qualification apparatus, cleaning, ignition energy, pass/fail criteria, or statistical sampling plan. |
| Surface finish / oxygen-service cleaning | Not public | No public machining, etch, passivation, particle-cleanliness, hydrocarbon-cleanliness, or oxygen-cleaning specification located. |
| Coating / enamel / thermal spray process windows | Partially described | Later patents mention MONDALOY + enamel glass / oxide thermal-spray approaches, but do not publish qualified spray parameters, firing cycles, bond-coat rules, or inspection criteria. |
| ASTM / SAE / NASA / internal material specs | None identified publicly | Likely internal Aerojet Rocketdyne / AFRL / NASA controlled specifications or program-specific material process specs. |

---

## 3. Assessment

**OBSERVED from public primary sources:** Mondaloy is a real nickel-based superalloy family for ORSC oxygen environments. The patent family gives the broad composition, the VIM + VAR melting route, and the strength / burn-resistance performance window. The 2017 inventor interview confirms Mondaloy 100 / 200 scale-up, wrought and powder / AM manufacturing routes, and AR1 component use.

**HYPOTHESIS from metallurgy:** the real know-how is not the alloy name or broad chemistry. It is the process-control envelope that keeps the Al/Ti gamma-prime strengthening high enough for structural duty without crossing the burn-resistance cliff in high-pressure oxygen. That envelope likely lives in heat treatment, melt cleanliness, minor-element control, surface state, powder oxygen pickup, AM/HIP cycles, and oxygen-service cleaning.

**Unknown vector:** full processing travelers, qualification test methods, oxygen-cleaning specs, powder limits, AM build parameters, HIP / heat treatment schedules, and material acceptance criteria are not public. If they exist outside contractor custody, they would most likely be in internal Rocketdyne / Aerojet Rocketdyne / L3Harris process specs, AFRL / NASA program documentation, ITAR-controlled qualification packages, or archived process travelers.

---

## 4. Grok / external-agent prompt

Use this when asking an external research model to hunt the next layer:

```text
Research Mondaloy / MONDALOY 100 / MONDALOY 200 processing. Prioritize primary sources: patents, NASA/Air Force/Aerojet/AR1/HCBT documents, conference papers, procurement specs, material datasheets, archived Rocketdyne references, and AFRL Materials Directorate references.

I need the tacit processing vectors, not generic descriptions: VIM/VAR melt practice, heat treatment/aging schedules, powder metallurgy and AM parameters, HIP/stress relief cycles, oxygen and nitrogen pickup limits, promoted combustion test method, surface finish/oxygen-cleaning requirements, coating/thermal-spray/enamel-glass process, and any ASTM/SAE/NASA/internal material spec identifiers.

Separate verified primary-source facts from inference and rumor. Return URLs, document identifiers, dates, named programs, and exact quoted lines where possible.
```

---

## 5. Search vectors still open

- "Mondaloy variants comparison"
- "ORSC engine alloys"
- "MONDALOY 100 MONDALOY 200"
- "Hydrocarbon Boost Technology Demonstrator Mondaloy 200"
- "AR1 preburner Mondaloy additive manufacturing"
- "AFRL Materials Directorate Mondaloy"
- "promoted combustion test nickel alloy oxygen 1/8 inch rod"
- "Jacinto Hardwick burn resistant high tensile strength metal alloys"

---

**Curated by:** CG55M@cursor (GPT-5.5 Medium) · node `GTH4921YP3` · 2026-05-07.
