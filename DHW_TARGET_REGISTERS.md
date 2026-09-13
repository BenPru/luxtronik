# The DHW target temperature registers

Reference notes for maintainers on the two "hot water target" parameters, why
the `number` and `water_heater` platforms gated them on different firmware
versions for eight months, and what to ask for when the next report about a
wrong DHW setpoint arrives.

**Status (2026-09-13):** both platforms now switch from P0002 to P0105 at
minor **88.3**. The `number` gate was moved down from 90.1 on the strength of
one behavioural measurement — see [The V1.90.0 measurement](#the-v190-measurement-2026-09-13).
The history below is kept because the reasoning that held the gates apart is
still the reasoning that limits what the measurement proves.

## The two registers

| | parameter | controller label | meaning |
|---|---|---|---|
| **P0002** | `ID_Einst_BWS_akt` | "Deckung WP" | the temperature reachable by the compressor alone. The controller **lowers this by itself** when the setpoint cannot be reached (documented in the AIT manual), so it is not a pure user setting. |
| **P0105** | `ID_Soll_BWS_akt` | "Wunschwert" | the desired value, shown as the primary figure on the controller display. |
| **C0018** | `ID_WEB_Einst_BWS_akt` | "Warmwasser-Soll" | read-only; P0002 plus any Smart Grid offset below minor ~90.1, `min(P0002, P0105)` plus offset from there. It was long read as "the effective target", but the [V1.90.0 measurement](#the-v190-measurement-2026-09-13) showed a pump obeying P0105 while C0018 tracked P0002 — so below 90.1 it mirrors a register, not the compressor's behaviour. |

C0018 is the useful one when analysing a dump for the Smart Grid offset and for
spotting the Event 2 relationship change. It does **not** tell you which
register the compressor obeys — only a heating cycle does.

## Two separate firmware events, often conflated

The single most common mistake in this area is treating "P0105 became correct"
and "P0002 became broken" as one event. They are not.

### Event 1 — writing P0105 starts propagating to P0002

Somewhere in the interval `(minor 79, minor 88.3]`:

- **FW 3.79** — writing P0105 from HA did *not* move P0002 (stayed 53), and the
  pump heated to 53. P0105 was inert.
  ([#280](https://github.com/BenPru/luxtronik/issues/280#issuecomment-2430134992))
- **FW 2.88.3** — a reporter confirmed P0105 "sets the right value" on his unit.
  ([#280](https://github.com/BenPru/luxtronik/issues/280#issuecomment-3690032168))
- **FW 3.90.0** — writing P0105 changed P0002 identically and the pump heated to
  it. ([#280](https://github.com/BenPru/luxtronik/issues/280#issuecomment-2428257354))

### Event 2 — C0018 starts following min(P0002, P0105)

At roughly minor 90.1. Below it **C0018** mirrors P0002 and P0105 does not
show up in it; at and above it C0018 follows `min(P0002, P0105)`. Note the
wording: this describes the read-only mirror, not the compressor — the
[V1.90.0 measurement](#the-v190-measurement-2026-09-13) showed a unit below
90.1 whose compressor obeyed P0105 while C0018 still read P0002. This is why a P0002 stuck at the 75.0 sentinel stops
mattering there, and it is the event [#280](https://github.com/BenPru/luxtronik/issues/280)
and [#428](https://github.com/BenPru/luxtronik/issues/428) actually reported.

Put plainly:

> **Event 1 is where using P0002 became the wrong choice.
> Event 2 is where that wrong choice started to hurt.**

Before Event 2 the two registers usually track each other, so P0002 mostly
worked and nobody complained.

## The evidence

From the local `diagnostics/` corpus. Dumps where `P0002 == P0105` carry no
information and are omitted; every divergent case is listed.

### Below minor 90.1 — C0018 follows P0002

| firmware | P0002 | P0105 | C0018 | note |
|---|---|---|---|---|
| V1.88.3 | 43.0 | 46.0 | 43.0 | |
| V1.90.0 | 49.0 | 48.0 | 49.0 | `min()` would give 48.0 |
| V1.90.0 | 49.0 | 48.0 | 54.0 | Smart Grid +5 K on top of P0002 |
| V3.88.0 | 40.0 | 38.0 | 40.0 | `min()` would give 38.0 |
| V3.88.0 | 48.5 | 47.5 | 48.5 | `min()` would give 47.5 |

Three of these discriminate between "follows P0002" and "follows `min()`", and
all three say P0002 — for **C0018**. The second V1.90.0 row belongs to a unit
type that, in [#785](https://github.com/BenPru/luxtronik/issues/785), cut in
and out on P0105, so these rows say nothing about what the compressor aims at.

### At and above minor 90.1 — C0018 follows min(P0002, P0105)

| firmware | P0002 | P0105 | C0018 |
|---|---|---|---|
| V3.92.0 | 54.7 | 45.0 | 45.0 |
| V3.92.0 | 75.0 | 50.0 | 50.0 |
| V3.92.0 | 75.0 | 52.0 | 52.0 |
| V3.92.1 | 53.5 | 59.5 | 53.5 |
| V3.92.1 | 56.5 | 60.0 | 56.5 |
| V3.92.1 | 75.0 | 50.0 | 50.0 |
| V3.92.1 | 75.0 | 53.0 | 53.0 |
| V3.92.1 | 75.0 | 53.0 | 59.5 |
| V3.92.1 | 75.0 | 56.5 | 56.5 |
| V3.92.1 | 75.0 | 57.0 | 57.0 |
| V3.92.3 | 49.5 | 47.5 | 47.5 |
| V3.92.3 | 75.0 | 56.0 | 56.0 |
| V3.92.3 | 75.0 | 58.0 | 58.0 |

Twelve of thirteen fit `min(P0002, P0105)` exactly. The one exception
(`75.0 / 53.0 / 59.5`) carries a Smart Grid offset.

Note the two V3.92.1 rows where P0105 is the *higher* value: the effective
target stays at P0002. P0105 acts as a ceiling, not as the setpoint.

## Why the two platforms disagreed (May 2025 – Sep 2026)

| platform | threshold | set by |
|---|---|---|
| `number_entities_predefined.py` | minor 90.0 / 90.1 (until 2026-09-13) | [PR #357](https://github.com/BenPru/luxtronik/pull/357), May 2025 |
| `water_heater.py` | minor 88.2 / 88.3 | commit `fecdf38`, Jan 2026 |

Both platforms were set to 90.0/90.1 by PR #357. Commit `fecdf38` then rebuilt
the minor-version mechanism and used it on one platform only:

- `firmware_version_minor` changed from `int` to `Version`. Before it was
  `int(re.sub("[^0-9]", "", ver.split(".")[1]))` — a whole number, so `88.3`
  could not be expressed as a threshold at all. The 88.3 value was in that sense
  a by-product of making it expressible.
- `max_firmware_version_minor` was added; only the `min_` side had existed, so
  no minor-gated *pair* was possible before.
- `model.py` moved `min_firmware_version_minor` off the `FirmwareVersionMinor`
  enum onto `Version`.
- `water_heater.py` then moved to 88.2/88.3.
- `common.py` and `sensor.py` changes in the same commit are unrelated
  (`LC.UNSET` guards for SmartGrid log warnings).

`number_entities_predefined.py` was not in the commit and stayed on the absolute
fields, which kept working — so nothing failed, it just silently diverged.

**The divergence is an oversight, not a decision.**

### What it looks like on an affected unit

For a unit with minor in `[88.3, 90.0]` — the reporter's 2.88.3 among them — the
two platforms read different registers for the same physical setpoint until
2026-09-13:

| entity | register |
|---|---|
| `water_heater` target temperature | P0105 |
| `number.<prefix>_dhw_target_temperature` | P0002 |

With the V1.88.3 dump's values (P0002 = 43.0, P0105 = 46.0) the water heater
card shows 46 while the number entity shows 43, and writes go to different
registers depending on which control the user touches. Both water heater
descriptions share one `SensorKey`, so this was a register swap on the existing
entity, not a new one.

A later change converted the `number` gates to the `*_minor` form too, which is
why both platforms used minor comparisons while still disagreeing on the
value. That conversion fixed a real bug — the absolute form compares the
firmware *major*, which is the controller series, so every V1.x and V2.x unit
read as older than any "3.x" bound — but it deliberately preserved each
platform's existing threshold.

## Why nothing was changed until September 2026

Neither threshold was clearly right, because a single register cannot express
both events:

- **Writing** P0105 appears correct from Event 1 onward — which supports
  `water_heater`'s 88.3.
- **Reading** P0105 looked wrong until Event 2 — the corpus shows a V1.88.3 unit
  with P0105 = 46 while C0018 read 43 — which supported `number`'s 90.1 for as
  long as C0018 was taken to be the effective target.

Both can be true at the same time, because the integration uses one register
for both directions. Picking either threshold for both platforms fixes one
direction and breaks the other, so the thresholds were left alone rather than
churned on incomplete evidence — until a report arrived with a behavioural
measurement on a unit *below* 90.1.

Two dead ends worth not re-deriving:

- **Register-existence detection does not work here.** Both P0002 and P0105
  exist on both sides of both events. The discriminator is meaning, not
  presence, so a firmware gate really is the only available lever.
- **C0018 alone does not settle which register is authoritative.** It is the
  P0002-lineage mirror below Event 2, so "C0018 equals P0002" is nearly
  circular there. It only becomes informative because the *relationship*
  changes at Event 2.

## The V1.90.0 measurement (2026-09-13)

[#785](https://github.com/BenPru/luxtronik/issues/785), Alpha Innotec
WZS 101 H/K, firmware V1.90.0, integration 2026.09.02, DHW blocking schedule
verified empty, hysteresis P0074 = 6 K. The reporter wrote **P0002 = 58** from
the `number` entity while **P0105 stayed 54**, then drew hot water:

| time | tank | P0002 | P0105 | compressor |
|---|---|---|---|---|
| 14:44 | 54.5 | 54 → 58 | 54 | idle |
| 15:03 | 49.3 | 58 | 54 | idle (already below the 52 cut-in P0002 would imply) |
| 15:07 | ~48 | 58 | 54 | **starts** |
| 15:25 | 52.9 | 58 | 54 | **stops** |

Cut-in at 48 and cut-out at ~54 is P0105 with a 6 K hysteresis, and nobody
touched the panel. So on this unit **P0002 does not participate in the DHW
target at all**, 41 minutes after being written — the `number` entity was
exposing an inert register, which is what the reporter had been calling "writes
are never recalculated". (Turning the knob on the panel appeared to "apply"
the write only because the panel's Wunschwert edit sets both registers.)

This is the first behavioural measurement on any V1.x/V2.x unit, and it
contradicts the 90.1 gate, which rested on a single 3.90.1 report. The
`number` gate was therefore moved to 88.2/88.3, matching `water_heater`, so
both controls show and write the same register. To be precise about what was
measured: the run proves the cutover is **at or below 90.0**; the value 88.3
itself is not measured, it is `water_heater`'s existing gate, which rests on
the 2.88.3 "sets the right value" comment in #280.

What the measurement does **not** settle, and what is still open:

- Whether a remote **write** of P0105 is honoured on this firmware, or whether
  the effective target is `min(P0002, P0105)` there already. Test A cannot
  separate those: with P0002 = 58 and P0105 = 54, both predict 54. The
  discriminating run is P0002 = 54, P0105 written to 58 — heats to 58 means
  P0105 alone governs; heats to 54 means `min()`, and the entity would have
  to write both registers. The reporter has been asked to run the shipped
  change; his result decides between those.
- Which register the entity should *display* on units in `[88.3, 90.0]` that
  behave like the V1.88.3 dump above (P0002 43, P0105 46, C0018 43). C0018
  followed P0002 there — but the second V1.90.0 dump (49 / 48 / 49) shows
  C0018 also following P0002 on a firmware where the compressor demonstrably
  obeys P0105, so C0018 is the P0002-lineage mirror, not the effective target,
  and the V1.88.3 dump is not evidence that its pump heated to 43.
- Units in `[88.3, 90.0]` that still obey P0002 would now get a `number`
  entity on an inert register. The corpus holds no behavioural evidence of
  such a unit; `water_heater` has carried this exposure since January 2026
  without a report.

## What to ask the next reporter

The corpus is static snapshots, so it cannot show write propagation. One
measurement closes the remaining gap — it is Test B from the
[V1.90.0 measurement](#the-v190-measurement-2026-09-13), with P0002 left
*below* the value written to P0105 so that `min()` and "P0105 alone" predict
different outcomes. Ask for, on a unit in `[88.3, 90.0]`:

1. The firmware version and a diagnostics dump.
2. Write P0105 via the `luxtronik2.write` action to a clearly different value.
3. After the next DHW cycle: what temperature did the water actually reach,
   and what do P0002, P0105 and C0018 read now?

If the water reaches the P0105 value, Event 1 has happened on that firmware.
If it reaches P0002 instead, it has not — which is exactly the false positive
that makes "P0105 sets the right value" untrustworthy on its own, since the
displayed figure changes either way.

Also worth knowing: the corpus contains **no V1.x or V2.x dump at minor ≥ 90.1**
at all. If a report arrives from one, it is the first of its kind — capture it.

## Related

- [#280](https://github.com/BenPru/luxtronik/issues/280) — the original thread; contains the FW 3.79, 3.90.0 and 2.88.3 observations, and the Smart Grid explanation of C0018.
- [#428](https://github.com/BenPru/luxtronik/issues/428) — V3.92.0, P0002 showing "Deckung WP" instead of the setpoint.
- [#517](https://github.com/BenPru/luxtronik/issues/517) — unrelated to the thresholds: the `firmware_version_minor` crash on two-part versions introduced alongside `fecdf38`, since fixed.
