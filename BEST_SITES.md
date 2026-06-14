# Big Sur — best specific sites (alert target list)

Ranked for **your** preferences: tent-forward, quiet (RV-limited, minimal
generators), and **hike-to is a plus**. Bigger RV-friendly campgrounds are
deprioritized even when individual sites are nice.

Legend — **Monitor:** how the alerter watches it.
✅ camply (Recreation.gov / ReserveCalifornia) · ⚙️ custom monitor · ✋ manual

## How these were chosen (the method)
1. **campsitephotos.com** — a photo of nearly every numbered site (view, privacy, slope, tree cover).
2. **Satellite view over the reservation map** — shows bluff-edge / riverfront vs. interior sites.
3. **Review mining** — Campendium, The Dyrt, Reddit r/bigsur for specific numbers + what to avoid.
4. **RV & generator policy** — no-hookup and tent-only/walk-in loops self-select for quiet.

---

## Master ranking (by your preferences)

| Rank | Site | Why it fits you | Monitor |
|---|---|---|---|
| 1 | **Ventana #49 / #50** | Tent-only, no RVs/vans, **hike-to**, redwood canyon. Your Mecca. | ⚙️ Hyatt |
| 2 | **Julia Pfeiffer Burns env. sites (2)** | **Hike-in**, tent-only, no vehicles, ocean bluff. The purest match — and brutally scarce. | ✅ ReserveCalifornia |
| 3 | **Andrew Molera trail camp** | **¼-mile hike-in, no cars at site**, tent meadow by the river. Quiet by design. | ✅ ReserveCalifornia |
| 4 | **Kirk Creek #9** (then 11, 22, 5, 8) | Oceanfront bluff, **no hookups** so no big-rig/generator circus; 5 hiker/biker walk-in sites too. | ✅ Recreation.gov |
| 5 | **Treebones walk-in tent sites** | Walk-in, ocean-view, tent-only, no campfires. Quiet, basic, dramatic. | ⚙️/✋ Treebones |
| 6 | **Limekiln — redwood sites 13–29** | Tiny park = quiet; creekside redwoods, more tent-ish than the ocean loop. | ✅ ReserveCalifornia |

Everything below the line (Plaskett, Pfeiffer main loops, the private RV resorts)
is RV-tolerant or busy — listed for completeness, not prioritized.

---

## The targets in detail

### 1. Ventana Campground — Hyatt (property SJCAC)  ⚙️ in scope
Tent-only (no RVs, vans, or roof tents), 40-acre redwood canyon, **3-night
minimum in summer**. Sites **49 & 50 are hike-to** — exactly your preference. You
book via Hyatt, pick dates, see open sites, and get the site you select.
**Monitoring:** Hyatt's system, not a government one, so camply can't see it — but
it *is* pollable (your buddy's Gemini script proves the availability endpoint
works). We build a small custom monitor for SJCAC that checks your date pattern
and alerts when 49/50 open. **If you can send me your buddy's script, I'll start
from it instead of reverse-engineering Hyatt from scratch.**

### 2. Julia Pfeiffer Burns — environmental sites  ✅ ReserveCalifornia
Only **two** hike-in, tent-only sites near the water, no vehicles allowed, on an
ocean bluff. Best preference-match on this whole list and the hardest to get,
which makes it the ideal alert target — you'd almost never catch these manually.
`camply recreation-areas --provider ReserveCalifornia --search "Julia Pfeiffer Burns"`

### 3. Andrew Molera — trail camp  ✅ ReserveCalifornia
Park in the day lot, walk ~¼ mile to 22 tent sites in a meadow by the Big Sur
River. No cars at the sites = quiet. Standard sites reservable 6 months out;
hike-and-bike sites first-come. Pick sites nearest the river/meadow edge (verify
on campsitephotos).
`camply recreation-areas --provider ReserveCalifornia --search "Andrew Molera"`

### 4. Kirk Creek — Recreation.gov #233116  ✅
Oceanfront bluff. **No hookups** and a 30-ft limit keep it from being RV-overrun,
though vans/small RVs do take bluff sites; generators are allowed daytime only and
banned during quiet hours (after 10pm). Site-specific booking.
- **S-tier:** **9** (the reel site — spacious, private, biggest grass apron, best view)
- **A-tier (bluff edge):** 11, 22, then 15, 17, 19, 21
- **B-tier (open ocean views, flatter ground):** 5, 8
- **Quiet/cheap option:** the 5 **hiker/biker walk-in** sites
- **Skip:** interior/inland sites

### 5. Treebones Resort — walk-in tent sites  ⚙️/✋
Mostly a glamping resort (yurts, autonomous tents), but it has a handful of
**walk-in tent campsites with sweeping ocean views** — tent-only, no campfires,
bring everything. Quiet and stunning. Booked through Treebones directly; no
government API, so it's a custom monitor or a manual check.

### 6. Limekiln SP — ReserveCalifornia  ✅
Tiny, dramatic park. Two zones:
- **Redwood sites 13–29** — creekside under redwoods, shadier/quieter, more tent-ish *(your better fit)*
- **Ocean sites** — beside the beach but allow RVs up to 24 ft
`camply recreation-areas --provider ReserveCalifornia --search "Limekiln"`

---

## Lower priority (RV-tolerant or busy — listed for completeness)

### Plaskett Creek — Recreation.gov #231959  ✅
Cypress meadow set back across Hwy 1, walk to Sand Dollar Beach / Jade Cove.
Allows RVs. Best if you go: 10, 14, 17, 19, 39 (outer perimeter for privacy);
avoid 6–8 (generator noise).

### Pfeiffer Big Sur SP — ReserveCalifornia rec-area #690  ✅
Big 189-site redwood/river campground with a dump station — developed and busy,
the opposite of quiet. If you want it anyway, chase riverfront: **174, 59, 61**
(then 57, 75, 79, 89, 93, 150, 151, 175–179), and favor South/Weyland loops over
Main.

### Private redwood resorts (all RV-tolerant) — ✋ direct booking
- **Big Sur Campground & Cabins** — riverside redwoods, rigs up to 40 ft (RV-heavy).
- **Fernwood Resort** — redwoods, partial RV hookups + tent/glamping.
- **Riverside Campground & Cabins** — riverside, rigs up to 25 ft, hookups.
- **Ripplewood Resort** — mostly cabins, not real tent camping.

---

## What this means for the build
- **camply covers** Kirk Creek, JP Burns, Andrew Molera, Limekiln (+ Plaskett,
  Pfeiffer if you want them) — one tool, both government providers.
- **Custom monitors** for **Ventana (Hyatt)** and optionally **Treebones** — small
  separate scripts that hit the same notification channel. Ventana is the priority;
  send the buddy's script to bootstrap it.
- **Manual only:** the private redwood resorts (and Treebones if we skip its monitor).
