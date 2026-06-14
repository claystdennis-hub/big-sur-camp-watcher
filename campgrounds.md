# Big Sur campgrounds — IDs and booking deep links

When you get an alert, tap the matching link to land on the booking page. Be
logged in already so checkout is just date + pay.

## Recreation.gov (federal — Los Padres NF)

| Campground | ID | Booking / availability link |
|---|---|---|
| Kirk Creek (oceanfront bluff) | `233116` | https://www.recreation.gov/camping/campgrounds/233116/availability |
| Plaskett Creek (near Sand Dollar Beach) | `231959` | https://www.recreation.gov/camping/campgrounds/231959/availability |

Recreation.gov releases new dates on a **rolling 6-month window** and offers a
free official **"Notify me"** waitlist on each campground page — worth turning on
in addition to this tool.

## ReserveCalifornia (state parks)

| Park | rec-area ID | Park page |
|---|---|---|
| Pfeiffer Big Sur SP | `690` | https://www.reservecalifornia.com (search "Pfeiffer Big Sur") |
| Andrew Molera SP | discover ↓ | — |
| Limekiln SP | discover ↓ | — |

ReserveCalifornia uses a single-page app, so it has no clean per-site deep
link — the alert gets you to the park; you pick the site there. New inventory
drops **6 months out at 8:00:00 AM PT** and coastal sites can vanish in seconds.

### Discover the missing IDs

After install, run these to get the rec-area / campground IDs, then paste them
into `search_config.yaml`:

```bash
camply recreation-areas --provider ReserveCalifornia --search "Andrew Molera"
camply recreation-areas --provider ReserveCalifornia --search "Limekiln"
# confirm a park's campgrounds:
camply campgrounds --provider ReserveCalifornia --rec-area 690
```

## Private campgrounds (no API — not automatable)

Big Sur Campground & Cabins, Fernwood, Riverside, Ventana. These book through
their own sites or Hipcamp and can't be polled programmatically. If the public
parks stay full, Hipcamp listings within ~30 min often have openings — check
those manually.
