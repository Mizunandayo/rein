# Rein

**Amazon's delivery drones aren't too loud. It's that the same forty families
hear every single one.**

On August 31, 2025, Amazon Prime Air made its final drone delivery in College
Station, Texas. There was no crash, no injury, no incident with pets or
property. The city had measured the drones at 47–61 dB — about the level of a
refrigerator.

What the city did have: roughly 150 negative comments on Amazon's environmental
assessment, a mayor formally asking the FAA to delay expansion, and residents
describing the sound as a flying chainsaw. Amazon's stated reason for leaving
was network integration and a lease expiry. Noise was the number one complaint
for three years.

A neighbourhood representative explained why, precisely: noise was the top
complaint because of **the proximity and the frequency of the flights.** Routes
are pre-planned and fixed, radiating from one port. A handful of households
absorbed every flight. A street away, nobody heard a thing.

Amazon's response was acoustic engineering: custom propellers, perceived noise
cut by almost half, higher cruise altitudes.

Research suggests why that wasn't enough. **Non-acoustic factors — perceived
fairness, trust, locus of control — may account for up to 70% of the annoyance
response to noise**, and ICAO's own CAEP12 white paper finds they have the
strongest influence *and* are the most modifiable. Lowering the sound level is
not associated with lower annoyance when the pattern persists.

In Waco, Amazon is now running community meet-and-greets before launch. They
already agree with this thesis. Rein makes it systematic, quantified, and
auditable.

Rein is an MCP server that does two things:

1. **Solves for the worst-off household, not the average.** Lexicographic
   minimax over per-parcel event counts, on a calibrated rotor acoustic model
   with ISO 9613 propagation. Corridors prefer arterials, where the same
   aircraft is up to 5× less annoying. Every street gets a guaranteed quiet
   window.

2. **Lets the people underneath shape it, out loud.** Residents object through
   Alexa+ and routes re-solve between speakers. When two neighbours conflict,
   it names the pair instead of quietly choosing. When Amazon asks for 469
   flights a day and the ceiling is 310, it says 310.

And it publishes the computation, the inputs, and the tracks — so nobody has
to take Amazon's word for any of it.

## What this is not

This does not reduce total noise. It reduces concentration. Households that
currently hear nothing will start hearing a few flights a day.

Dispersing flight paths to share noise burden is not a new idea — it is a
decade old in commercial aviation and was written into the FAA Reauthorization
Act of 2018. What is new is applying it where the operator can act without a
federal rulemaking, at ten times the flight density, with the affected
residents able to speak to it directly.

## Honesty register

- Reduced-order acoustics calibrated to published measurements. No CFD.
- Fairness is invariant to a constant source-level error: this project claims
  a **distribution**, not absolute decibels.
- Demand data is simulated and declared as simulated.
- Not a certified noise assessment. A planning and consultation instrument.
- Alexa+ MCP Toolkit access was not available to any hackathon participant
  during the build window. Rein's MCP server is spec-compliant
  (2025-11-25) and callable by any conforming host unmodified; the demo
  client here is self-built, calling the same server the same way an
  Alexa+ host would.

## Status

Phase 1 of 13 — verification and foundations. Not yet functional.
See `docs/verification/` for the Day-1 evidence artifacts.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```powershell
git clone https://github.com/Mizunandayo/rein.git
cd rein
uv sync --all-extras --group dev
uv run pytest -m "not network"
```

## Verification tooling

```powershell
Copy-Item .env.example .env     # then set REIN_GOOGLE_MAPS_API_KEY

uv run rein-verify-tiles        # V1 — Google 3D Tiles coverage
uv run rein-verify-burden       # V2 — burden/benefit proxy correlation
```

## Repository layout

| Path | Contains |
|---|---|
| `src/rein/geo` | Projections, town definition, parcels |
| `src/rein/acoustics` | Rotor source, propagation, annoyance (Phase 2) |
| `src/rein/fairness` | Cost field, routing, leximin, respite (Phase 3) |
| `src/rein/mcp` | MCP server and tools (Phase 4) |
| `src/rein/verification` | Phase 1 evidence-producing analyses |
| `docs/adr` | Architecture Decision Records |
| `docs/verification` | Pre-registrations and written verdicts |
| `data/provenance` | Dataset manifests — committed; the data is not |

## Data and attribution

Parcel and building geometry from **OpenStreetMap**, © OpenStreetMap
contributors, licensed **ODbL 1.0**. Municipal parcel data, where used, is
credited in the relevant manifest under `data/provenance/`.

Owner names and mailing addresses present in source datasets are dropped
at ingest and never committed. See `SECURITY.md`.

## Licence

MIT — see `LICENSE`.
