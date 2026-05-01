# GPS · mobility · privacy — bibliography seed for **union field** (Architect silicon only)

**For the Swarm.** 🐜⚡  
**Binding:** [IDE_BOOT_COVENANT.md](../IDE_BOOT_COVENANT.md) + NPPL — **no third-party surveillance**, **no** weaponized tracking. This doc is **owner-of-silicon + voluntary iPhone bridge** only, aligned with `System/swarm_iphone_gps_receiver.py` (LAN-private sources, optional token, append-only `iphone_gps_traces.jsonl`).

**Union field (spec vocabulary):** one **spatiotemporal substrate** merging (a) **stationary node** (M5 anchor), (b) **Architect locus** (iPhone GPS pings), (c) **stigmergic deposits** (JSONL traces, receipts) — **pheromone strength** = recency × accuracy × policy gates, **not** omniscient world model.

---

## 1 — DOI-anchored core (minimal human work; paste to Grok to extend)

| Topic | Paper / venue | Stable id | Map → SIFTA |
|:---|:---|:---|:---|
| **Statistical laws of human mobility** | Gonzalez, Hidalgo & Barabási (2008) *Nature* | [DOI 10.1038/nature06958](https://doi.org/10.1038/nature06958) | **Return-to-hub** + characteristic distance → **home / studio / errand** priors for **freshness windows** and “expected return” scheduling hints. |
| **Predictability ceiling** | Song *et al.* (2010) *Science* | [DOI 10.1126/science.1177170](https://doi.org/10.1126/science.1177170) | **Honest bound** on how well any “Alice predicts Architect location” feature can work — avoid overclaiming inference. |
| **Trajectory mining roadmap** | Zheng (2015) *ACM TIST* — *Trajectory Data Mining: An Overview* | [DOI 10.1145/2743025](https://doi.org/10.1145/2743025) | **Preprocessing, segmentation, clustering, outlier detection** for `iphone_gps_traces.jsonl` offline tools (trip detection, gas-stop vs motion). |
| **Spatial + temporal k-anonymity** | Gruteser & Grunwald (2003) *MobiSys* | [DOI 10.1145/1066116.1189037](https://doi.org/10.1145/1066116.1189037) | **Cloaking / coarsening** before any export or federation — pair with **LAN-only** + **token** already in receiver. |
| **Geo differential privacy** | Andrés *et al.* (2013) *CCS* — geo-indistinguishability | [DOI 10.1145/2508859.2516735](https://doi.org/10.1145/2508859.2516735); [arXiv:1212.1984](https://arxiv.org/abs/1212.1984) | **Optional noise layer** if Architect ever shares aggregates off-node; planar Laplace mechanism. |

---

## 1.5 — Defensive Telemetry & Anti-Spoofing (Owner-Sovereign Defense Only)

*The NPPL explicitly forbids offensive tracking. The following research areas are legitimate for SIFTA exclusively for **self-defense** (protecting the Architect's hardware from external spoofing or jamming).*

| Area | Why it’s legitimate for SIFTA | Entry cites (for DOI verification) |
|:---|:---|:---|
| **GNSS spoofing / jamming awareness** | Protect receiver and decisions that trust GPS. | Humphreys / Psiaki line on civil GPS spoofing & mitigation; search “GPS spoofing civil aviation mitigation survey”. |
| **Signal authentication** | Trust sensor readings, not neighbors’ phones. | ESA Galileo OSNMA docs; GPS ISM / civil monitoring literature. |
| **Cellular threat models (SS7, fake BTS)** | Harden devices & OS; not to attack others. | Academic surveys on cellular security; GSMA fraud / security guidelines. |
| **Location privacy (Architect as subject)** | Minimize leak when exporting data. | Gruteser & Grunwald (MobiSys); Andrés et al. geo-indistinguishability (above). |
| **Spectrum policy** | Legal use of SDR / scanning is jurisdiction-specific. | FCC / national regulator primaries — requires human lawyer, not repo lore. |

---

## 2 — Second-ring (keywords for Grok / C55M to DOI-lock next)

* **Map matching / HMM on roads:** Newson & Krumm; Lou *et al.* — snap noisy GPS to graph.  
* **Stay-point detection:** Li *et al.*; Ashbrook & Starner — segment trips → **calendar-like atoms** for scheduling.  
* **Geofencing + temporal logic:** Allen interval algebra + simple cylindrical (lat, lon, r, t) predicates — **union field voxels**.  
* **Episodic mobility / exploration–return:** Song *et al.* scaling laws; Pappalardo *et al.* “Returners vs explorers” — personality of **mobility style** (optional UX).  
* **Energy / duty cycle on phone:** duty-cycled GPS sampling papers — **battery honesty** for Shortcut frequency.  
* **Kalman / particle smoothing on GNSS:** standard robotics — **Kalman filter** row for denoising before ledger write (implementation ref, not philosophy).

---

## 3 — Copy-paste for Grok (Architect: one shot, returns table)

```text
Extend GPS_UNION_FIELD_BIBLIOGRAPHY_SEED.md §2 into 15 more rows.

Each row: Topic | First author (year) | Venue | DOI or arXiv | One-line map to {iphone_gps_traces.jsonl, union_field_voxel, scheduling, privacy_export}.

Hard rules: NPPL — no military surveillance; only owner-consented mobility. Prefer map matching, stay points, geofencing, sampling schedules, federated location DP.
```

---

## 4 — Repo SoT (implementation, not papers)

* `System/swarm_iphone_gps_receiver.py` — HTTP ingest, LAN filter, staleness `SIFTA_IPHONE_GPS_STALE_S`, token `SIFTA_IPHONE_GPS_TOKEN`.  
* `System/swarm_gps_sensor.py` — related GPS organ surface.  
* Ledgers: `.sifta_state/iphone_gps_traces.jsonl`, `iphone_gps_latest.json` (and `gps_traces.jsonl` if legacy path).

---

*Seed: 2026-04-30 — CG55M (M5 hill). Extend with Grok/C55M; do not ship off-node traces without Architect GO + privacy row.*
