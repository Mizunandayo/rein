# V2 — Pre-registration

- **Written:** 2026-09-30
- **Committed before any analysis code ran:** yes — verify via
  `git log --follow docs/verification/V2-preregistration.md`

An analysis whose thresholds are chosen after seeing the result is not
evidence. This document fixes them in advance.

## Hypothesis

**H1.** Drone drop-zone eligibility increases with distance from viable
drone-port sites.

**H0.** No monotonic association between eligibility and distance.

## Proxies

**Viable port site.** A land-use polygon with
`landuse ∈ {industrial, commercial, retail}` and area ≥ 5,000 m².
Rationale: Prime Air sites occupy commercial/light-industrial land;
5,000 m² is a conservative lower bound for a facility with apron and
parking.

**Eligibility.** A dwelling scores 1 when both hold:

- **Detached:** `building ∈ {house, detached, bungalow, semidetached_house}`,
  or, where the tag is generic, footprint < 400 m² with ≤ 2 storeys.
  `building ∈ {apartments, residential, dormitory, terrace, hotel}` is
  never detached.
- **Clear space:** unbuilt parcel area ≥ 50 m², a conservative allowance
  for a 2 m drop zone plus clearance from eaves and boundaries.

Where parcel polygons are unavailable, unbuilt area is approximated from
a 12 m buffer around the footprint minus intersecting structures. This
substitution is recorded in the result.

## Statistic

Spearman rank correlation ρ between _distance to nearest viable port
site_ (metres, projected CRS EPSG:32614) and _eligibility score_.
Spearman rather than Pearson: the relationship is expected to be
monotonic but not linear, and rank methods are robust to the heavy-tailed
distance distribution.

95% confidence interval by percentile bootstrap, 2,000 resamples, seed 20260918. Minimum usable sample: 200 dwellings.

## Decision rule — fixed in advance

| Outcome          | Condition                                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------------------------- |
| **SUPPORTED**    | ρ > 0.15, 95% CI excludes 0, **and** the sign holds (ρ > 0.15 with CI excluding 0) in ≥ 3 of 4 sensitivity variants |
| **REFUTED**      | ρ ≤ 0, **or** the CI includes 0 in ≥ 3 of the 5 analyses (primary + 4 variants)                                     |
| **INCONCLUSIVE** | anything else                                                                                                       |

## Sensitivity variants — all four run, all four reported

| #   | Varies                | Alternative                                        |
| --- | --------------------- | -------------------------------------------------- |
| S1  | Port area threshold   | 2,500 m² instead of 5,000 m²                       |
| S2  | Clear-space threshold | 100 m² instead of 50 m²                            |
| S3  | Port land-use set     | `industrial` only                                  |
| S4  | Distance metric       | distance to the nearest of the three largest sites |

## Validation before touching real data

The pipeline must, on synthetic parcels:

1. Recover an injected positive correlation (ρ > 0.4).
2. Return a null result (|ρ| < 0.15, not SUPPORTED) on shuffled eligibility.
3. Recover an injected _negative_ correlation with the correct sign.
4. Refuse a sample below the minimum rather than report a fragile number.
5. Refuse to treat "no candidate ports" as distance zero.

Failing any of these means the pipeline is broken and no real-data result
may be reported.

## Consequence

- **SUPPORTED** → the burden/benefit quadrant (§11.3) leads the pitch,
  stated only in eligibility language (§2.6).
- **REFUTED / INCONCLUSIVE** → the quadrant framing is dropped entirely
  and the pitch leads with fairness. Reporting a null result honestly is
  itself a credential.
