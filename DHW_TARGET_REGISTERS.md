# The DHW target temperature registers

Reference notes for maintainers on the two "hot water target" parameters, why
the `number` and `water_heater` platforms gated them on different firmware
versions for eight months, and what to ask for when the next report about a
wrong DHW setpoint arrives.

**Status (2026-11-10):** both platforms switch from P0002 to P0105 at minor
**88.3**, and that stays. What changed is the *reason*. A disassembly of the
controller firmware ([Firmware evidence](#firmware-evidence-2026-11-10))
shows that the compressor works towards **P0002** on every series 1/2 build
(up to and including the latest V1/V2/F1 90.0) and on series 3 up to 3.89.
P0002 is an adaptive value that the controller steers towards P0105 by itself.
Only from 3.92 on series 3 does the DHW target start from P0105, as
`min(P0105, P0002)`. Writing P0105 is still the right action from 88.3 on:
on a V1.88.3 unit a remote P0105 write set P0002 to the same value
immediately, and P0105 is the ceiling P0002 climbs back to. The V1.90.0 run
that moved the `number` gate to 88.3 does **not** show the compressor
obeying P0105. It shows the 90.0 write defect, see
[the reinterpretation](#reinterpretation-2026-11-10). The history below is kept,
but read it with that correction in mind.

## The two registers

| | parameter | controller label | meaning |
|---|---|---|---|
| **P0002** | `ID_Einst_BWS_akt` | "Deckung WP" | the temperature reachable by the compressor alone, and **the value the DHW control works towards** below 3.92 ([firmware](#firmware-evidence-2026-11-10)). The controller manages it by itself: after an operating-limit stop it is set to the tank temperature reached, after a run that falls short it drops 1 K, after a run that reaches it it rises 0.5 K, capped at P0105 (manual, [#793](#793-how-deckung-wp-moves-2026-09-15), and the firmware's raise logic). So it is not a pure user setting. |
| **P0105** | `ID_Soll_BWS_akt` | "Wunschwert" | the desired value, shown as the primary figure on the controller display. Below 3.92 it is the ceiling P0002 is steered towards, and the target of "Warmwasser-Nachheizung" (P0994) when that is on. From 3.92 the DHW target itself starts from it. |
| **C0018** | `ID_WEB_Einst_BWS_akt` | "Warmwasser-Soll" | read-only. Below 3.92 the firmware fills it from the same function the compressor start uses: the **applied** P0002, plus P1122 `SMART_GRID_DHW_INCREASE` in Smart Grid state 3 (state 3 or 4 on 90.0). From minor ~90.1 it reads `min(P0002, P0105)` plus offset. "Applied" matters: on a unit whose writes do not take effect (V1.90.0/V2.90.0, see [#761](https://github.com/BenPru/luxtronik/issues/761) and the [reinterpretation](#reinterpretation-2026-11-10)), the P0002 parameter reads back the written value while C0018 keeps the value the control actually uses. A DHW target written over the Smart Home Interface (Modbus TCP) shows up only here, and is not capped by P0105; see [Targets written over the Smart Home Interface](#targets-written-over-the-smart-home-interface). Exposed as a sensor from 90.1 only; see [The controller target sensor](#the-controller-target-sensor-850-2026-10-31). |

C0018 is the useful one when analysing a dump for the Smart Grid offset and for
spotting the Event 2 relationship change. Below 3.92 it is also the best
single-snapshot answer to "what is the compressor aiming at", but only on a
unit whose writes are applied. On 90.0 units a P0002 that differs from C0018 is a
write that never took effect, not a second target.

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
- **FW V1.88.3** — writing P0105 = 60 mid-run set P0002 and C0018 to 60 at
  once. The run then stopped near 54 on a hot-gas peak of 100.5 °C, and P0002
  dropped to the tank temperature reached, which is the Deckung WP rule.
  ([#785](https://github.com/BenPru/luxtronik/issues/785), 2026-09-27 and
  2026-10-02)

Where in the firmware the propagation happens is not pinned down. In the
3.89.3 code the parameter-apply switch has a case for P0002 and none for
P0105, so the copy must happen elsewhere (candidates: the DHW coverage object,
or the GDI layer's `adjustDHWTargetTemperature`). That is a refinement. The
behaviour is observed on both series 1 and 3.

### Event 2 — C0018 starts following min(P0002, P0105)

At roughly minor 90.1. Below it **C0018** mirrors P0002 and P0105 does not
show up in it; at and above it C0018 follows `min(P0002, P0105)`. The firmware
shows this is not just the mirror changing: on series 3 the DHW target itself
moved from P0002 to a P0105-based value capped by P0002, somewhere between
3.89.3 and 3.92.x ([firmware](#firmware-evidence-2026-11-10)). Series 1 and 2
never made this change. This is why a P0002 stuck at the 75.0 sentinel stops
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

### Below minor 90.1 — C0018 mostly follows P0002

| firmware | P0002 | P0105 | C0018 | note |
|---|---|---|---|---|
| V1.88.3 | 43.0 | 46.0 | 43.0 | |
| V1.90.0 | 49.0 | 48.0 | 49.0 | `min()` would give 48.0 |
| V1.90.0 | 49.0 | 48.0 | 54.0 | Smart Grid +5 K on top of P0002 |
| V1.90.0 | 50.0 | 54.0 | 54.0 | `unknown-entry-1CA15E`, the #785 unit. P0002 = 50 was a remote write that this firmware stored but never applied, so the control still used the last panel value 54, and C0018 shows that. Smart Grid was off and P1122 = 2.0 K, so "+4 K" is ruled out |
| V1.90.0 | 50.0 | 37.5 | 50.0 | |
| V1.77 | 59.5 | 61.0 | 59.5 | |
| V1.73 | 44.0 | 46.0 | 44.0 | |
| V1.73 | 48.0 | 46.0 | 48.0 | `241125_0195/2026-02-04`, the two-pump mixture: its `devices` block says V3.89.5, but registers below index 1021 (these three included) are the V1.73 unit's own — see `diagnostics/INDEX.md` |
| V3.88.0 | 40.0 | 38.0 | 40.0 | `min()` would give 38.0 |
| V3.88.0 | 48.5 | 47.5 | 48.5 | `min()` would give 47.5 |

Every row fits "C0018 = applied P0002 + Smart Grid offset". The 1CA15E row is
no exception once the 90.0 write defect is taken into account (see the note).
The `211129_09` Smart Grid row (49 / 48 / 54) is P0002 + P1122, and that unit
has P1122 = 5.0 K. Across its seven dumps (V1.90.0, P1030 = 3) C0018 reads
exactly P0002 or P0002 + 5.0 (48 / 53, 49 / 54), depending on the Smart Grid
state at the moment of the dump. That is the firmware formula verbatim. Below
3.92 these rows therefore do say what the compressor aims at: the C0018 value.

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
(`75.0 / 53.0 / 59.5`) carries a raise. Read alone, a dump cannot tell a
Smart Grid offset from a target written over the
[Smart Home Interface](#targets-written-over-the-smart-home-interface).

Note the two V3.92.1 rows where P0105 is the *higher* value: the effective
target stays at P0002. P0105 acts as a ceiling, not as the setpoint. That
holds between these two registers only: a target written over the Smart Home
Interface is not capped by P0105.

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
  changes at Event 2. *(2026-11-10: the firmware settles the authority question
  directly. Below 3.92, C0018 comes from the same function the compressor start
  uses, so on a unit whose writes are applied it is the effective target. See
  [Firmware evidence](#firmware-evidence-2026-11-10).)*

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

*The reading in the next paragraphs was superseded on 2026-11-10; see
[Reinterpretation](#reinterpretation-2026-11-10) below. It is kept because the
gate change was made on it.*

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

### Reinterpretation (2026-11-10)

The run above is explained by the V1.90.0 write defect, not by P0105
governing. On the controller's 8889 interface a write has two steps
([firmware](#firmware-evidence-2026-11-10)): `storeParameter` stores the value
(which is what every poll reads back), and the main loop later *applies* it. For
P0002, applying copies the value into the variable the DHW control uses. On this
unit the second step did not happen until a panel confirm, the "value accepted,
never acted on" symptom that the reporter later fixed by downgrading to V1.88.3.

- **13 Sep run:** P0002 read back 58, but the control still had the last panel
  value, 54. Cut-in at 48 is 54 − 6 K hysteresis, and the stop near 54 is the
  same 54. P0105 being 54 too was a coincidence, so the run says nothing about
  P0105.
- **3 Sep dump** (P0002 50, P0105 54, C0018 54): the same thing. C0018 is the
  applied value.
- **22 Sep run** (P0105 written 58, P0002 55): after a panel press the pump
  heated towards 55, with C0018 at 55. P0002 governs.
- **27 Sep run on V1.88.3**, writes working: a P0105 write set P0002 and C0018
  at once (see [Event 1](#event-1--writing-p0105-starts-propagating-to-p0002)).

What this does to the open points above:

- *P0105 alone or `min()`?* Neither, on series 1/2 and V3 up to 3.89. The
  control works on P0002. A P0105 write seeds P0002 with the same value, and
  P0105 is the ceiling the adaptive P0002 climbs back to. Writing P0105 alone is
  therefore enough. Writing both would only matter if seeding failed, which no
  report shows on a unit with working writes.
- *Which register to display?* P0105 remains the right user-facing value: it is
  what the user set and what P0002 converges to. A lower P0002 is the controller
  saying the heat pump cannot currently reach it.
- *Units in `[88.3, 90.0]` that obey P0002:* that is all of them below 3.92. It
  is harmless as long as the P0105 write seeds P0002, which is observed on
  V1.88.3 and V3.90.0. Whether it also holds on V3.88.x/3.89.x is not observed
  directly.

## Firmware evidence (2026-11-10)

The controller application (`appl`, `bin/Controller` on 3.92) was extracted
from firmware images and disassembled. The latest image per series is public
on the portal the update entity already queries:
`https://www.heatpump24.com/software/fetchSoftware.php?softwareID=N`, with N =
0 V1, 1 V2, 2 V3, 3 V4, 4 F1. Older images came from a maintainer's own
downloads. Several builds were shipped unstripped, so their function names are
real. Stripped builds were matched against them by code signature and by the
order in which functions load their variables.

**The effective DHW target** is a function named
`effectiveDHWTargetTemperature()` in the named builds. Its callers include
the compressor start conditions (`getcondtionForSignalVD`,
`evalConditionsForTwoAvailableCompressors`), the DHW handler, the display and
the value export, which is very likely where C0018 comes from.

| build | names | effective DHW target |
|---|---|---|
| F1.88.3, V2.88.3 | yes | P0002 + P1122 if Smart Grid on and state 3 |
| V3.87.1, 3.88.0, 3.89.3 | yes | P0002 + P1122 if Smart Grid on and state 3 |
| V1.90.0, V2.90.0, F1.90.0 | stripped | P0002 + P1122 if Smart Grid state 3 or 4 |
| V3.92.3 | stripped (variables exported) | starts from P0105, may be replaced by an external energy manager value (`Einst_RFVEinb_akt` 6 with `Einst_SmartWW`), + P1122 in state 3 or 4. The DHW control then caps it by P0002 and P0973 (per the SHI analysis below), giving `min(P0105, P0002)` |
| V3.84.3 | yes | function not present (older structure, not analysed) |
| V4.81.3 | yes | separate code line, no such function, not analysed |

So the switch to a P0105-based target happened on series 3 between 3.89.3 and
3.92.x, which matches Event 2 (~90.1, only ever seen on 3.92.x units). Series
1 and 2 never switched: their newest release is 90.0.

**Deckung WP in code** (V2.88.3 DHW handler, same shape in 90.0): during a run
a flag is set once the tank reaches P0002 − hysteresis. After the run, if the
flag is set, the tank is still there, P0105 − 0.5 K ≥ P0002 and
Warmwasser-Nachheizung is off, then P0002 rises by 0.5 K and the flag clears.
The 1 K lowering and the limit-stop reset were not read in detail. They are
presumably in the coverage routine (`DhwCoverage::set` on series 1/2,
`CHotWaterCoverage` with `lowerValue`/`RiseValue` on series 3), which also
calls `SetParameter(1123, 0)`. With
Nachheizung (P0994) on, the handler sets the DHW control value to P0105 during a
request, so the heater finishes the cycle at the Wunschwert. The #785 unit's
P0002 climbing 50 → 54 (= P0105) between 3 and 28 September is this rule.

**The write path** (port 8889, all builds): command − 3002 selects write /
read parameters / read calculations / read visibilities. A write calls
`storeParameter`, which queues the value for the main loop. If it refuses the
write, **the echoed index in the reply is −1**, so a rejected write is
detectable from the acknowledgement. On 3.89.3 `storeParameter` also refuses
indices above 1153.

Method and caveats: pyelftools and capstone, scripts kept outside the
repository. Results from named builds are read directly. The 90.0 and 3.92.3
results rest on signature matches that were checked against the named builds
(the signature hits exactly the named function there). The P0002 address in the
90.0 builds rests on load-order alignment of two independent functions against
V2.88.3. V3.92.3's DHW control was described by an independent analysis of the
same binary, [Bankaifan/ha-luxtronik-shi](https://github.com/Bankaifan/ha-luxtronik-shi/blob/main/docs/firmware-3.92.3-shi-full-analysis.md)
(§3.2).

## What to ask the next reporter

*Updated 2026-11-10.* The "P0105 alone or `min()`" test is no longer needed
for series 1/2 (see [Reinterpretation](#reinterpretation-2026-11-10)). Two
things are still worth checking when the chance comes:

- **On 90.0 (V1/V2/F1), first rule out the write defect.** If a written value
  reads back but C0018 and the panel keep the old value, the write was stored
  but not applied ([#761](https://github.com/BenPru/luxtronik/issues/761),
  [#785](https://github.com/BenPru/luxtronik/issues/785)). No register question
  can be answered on such a unit. The known remedy is a downgrade to the
  pre-.90 release of the same series.
- **On V3.88.x or 3.89.x, does a P0105 write seed P0002?** This is observed on
  V1.88.3 and V3.90.0, not yet on 3.88/3.89. Ask for the firmware version and a
  dump, a P0105 write via `luxtronik2.write` to a clearly different value, and
  P0002 / P0105 / C0018 right after the write. If P0002 and C0018 follow, the
  88.3 gate is right there too. If they do not, the entity would have to write
  P0002 as well on those versions.

Also worth knowing: the corpus contains **no V1.x or V2.x dump at minor ≥ 90.1**
at all. If a report arrives from one, it is the first of its kind — capture it.

## #793: how "Deckung WP" moves (2026-09-15)

[#793](https://github.com/BenPru/luxtronik/issues/793) (WZS, **V1.81**, 1-min
polling) is the only case where a user logged P0002 minute by minute while a
DHW run failed, so it is the best evidence on the manual's rules. The Luxtronik
2.0 part-1 manual (83055200, rev. i, 2022, p. 22, "Trinkwarmwassertemperatur
ohne Nachheizung") describes a sequence: when the pump **shuts down on an
operating limit** (Einsatzgrenze), the tank temperature reached is *set as*
Deckung WP, which becomes the regulating value; each later run that cannot get
back to Deckung WP lowers it by 1 K, each one that does raises it 0.5 K
towards the Wunschwert. The Wunschwert itself never moves. The manual does not
say what ends a run in the 1 K case — a limit trip with the tank already close,
the maximum DHW runtime, heating priority or an EVU lock would all look the
same in P0002.

What the reporter saw, with no `3002` in his DEBUG log and later reproduced
with the integration disabled:

- Runs ending below Deckung WP: P0002 stepped 50→49→48→47, 1 K each, near the
  end of a run.
- One run on 2026-09-08 aborted twice on the **flow limit**: flow ~64.1 °C with
  P0149 `ID_Einst_TVLmax_akt` = 64 °C, hot gas 88–91 °C, tank at 44.7 then
  43.9 °C. At that moment P0002 jumped **48 → 43** — the tank temperature
  actually reached, not a 1 K step. That is the limit-shutdown case verbatim.
  Consistent with the corpus unit `241125_0195` (V1.73) drifting 48 → 44
  unobserved.
- The manual's recovery rule (successful runs bring Deckung WP back towards the
  Wunschwert in 0.5 K steps) stops *at* the Wunschwert. His later snapshot had
  P0002 (49) *above* P0105 (48), which recovery cannot produce; that fits him
  lowering the Wunschwert on the panel mid-troubleshooting after P0002 had
  already climbed back. A P0002 > P0105 snapshot therefore says nothing about
  the integration either way.

Consequences for this document: below 88.3 the `number` entity exposes a
controller-managed value that moves on its own; a "target decreases by itself"
report on such firmware is the controller, not a write, and the first thing to
check is whether flow/hot-gas hit a limit at the drop. Disabling the
integration removes the observer, not the effect. He did not attach his dump
(local network data survived redaction), so V1.81 is still absent from the
corpus.

## The controller target sensor (#850, 2026-10-31)

[#850](https://github.com/BenPru/luxtronik/issues/850) (LP16V, V3.92.3) asked
for C0018 as a sensor: P0105 sat at 48, P0002 at the 75.0 sentinel, and C0018
moved 48 → 50 → 55 as PV surplus raised the target. The sensor
`sensor.<prefix>_dhw_target_temperature_controller` exists from minor **90.1**
only (`min_firmware_version_minor`), for these reasons:

- **At and above 90.1** every divergent dump is V3.92.x and fits
  `min(P0002, P0105)` plus offset. One of them also carries behaviour: on
  `260126_0477` (V3.92.1, 2026-06-10) C0018 was raised to 59.5 with P0105 at
  53, and across three dumps the tank climbed 44.8 → 52.6 → 57.3 °C — past
  P0105, towards C0018. The offset also shows with the registers equal:
  `unknown-entry-GSZ1XT/2026-06-23` (V3.92.3) reads 47.5 / 47.5 / 51.5.
- **Below 90.1** C0018 is the applied P0002 plus the Smart Grid offset. That
  is a meaningful value (the firmware uses it for the compressor start), but it
  differs from what the `number`/`water_heater` entities show (P0105) whenever
  Deckung WP has dropped. *Originally this bullet said a V1.90.0 compressor was
  measured to ignore P0002. That reading was withdrawn on 2026-11-10 (see
  [Reinterpretation](#reinterpretation-2026-11-10)).* Whether to extend the
  sensor below 90.1 is now a product question, not an evidence question.
- **The 90.1 boundary itself is untested by the corpus**: every V3.90.0/90.1
  dump has P0002 = P0105. It rests on the 3.90.1 report in #280 and matches
  Event 2 above. A V3.90.x or V3.91.x dump with the two registers apart would
  confirm or move it.
- **Series 1 and 2 at 90.1 or later** get the sensor too, by the series-agnostic
  minor rule. The corpus has no such dump yet; if a V1.90.1+ or V2.90.1+ unit
  shows C0018 still mirroring P0002, the gate needs a series condition.
- **Series 4** (V4.81.3) is excluded by the minor comparison; nothing is known
  about C0018 there.

A firmware gate is the right lever here for the same reason as for P0002/P0105:
the register exists everywhere, only its meaning changes.

### Targets written over the Smart Home Interface

The #850 raise turned out not to be Smart Grid at all. The reporter's PV
manager, Solar Manager, writes the DHW target over the controller's Smart Home
Interface (Modbus TCP). P1030 `ID_Einst_SmartGrid` was off and EVU/EVU2 never
moved. His dump (`unknown-entry-T61YDK/2026-10-31`) read P0105 48, C0018 50.
That looked like P0105 + P1122 `SMART_GRID_DHW_INCREASE` (2.0). The 55 °C
phase also matched P0973 `ID_Einst_BW_max` (55.0). Both matches were
coincidence. He then changed Solar Manager's "normal" value from 50 to 51
during a normal phase. C0018 went to 51.0 within seconds, and a diff of all
parameters between the two dumps showed no change at all: P0105, P1122,
P0973 and P1030 were all the same.

What follows from this:

- A target written over the Smart Home Interface shows up **only in C0018**.
  No parameter on the 8889 interface mirrors it, so P0105, the `number` entity
  and the `water_heater` card all keep showing the configured setpoint.
- It is **not capped by P0105**: C0018 read 51 with P0105 at 48. So
  `min(P0002, P0105)` plus offset describes C0018 only when nothing writes over
  the Smart Home Interface.
- The `smart_grid_status` sensor reads the EVU/EVU2 inputs, so it cannot see
  this either.
- A raised C0018 in a dump is therefore not proof of Smart Grid. Other PV
  managers and energy managers can write over the same interface.

## Related

- [#280](https://github.com/BenPru/luxtronik/issues/280) — the original thread; contains the FW 3.79, 3.90.0 and 2.88.3 observations, and the Smart Grid explanation of C0018.
- [#428](https://github.com/BenPru/luxtronik/issues/428) — V3.92.0, P0002 showing "Deckung WP" instead of the setpoint.
- [#793](https://github.com/BenPru/luxtronik/issues/793) — V1.81, P0002 "decreasing by itself"; the Deckung-WP mechanics above.
- [#850](https://github.com/BenPru/luxtronik/issues/850) — V3.92.3, C0018 requested as a sensor; the 90.1 gate and the Smart Home Interface finding above.
- [#785](https://github.com/BenPru/luxtronik/issues/785) — V1.90.0 WZS: the measurement that moved the `number` gate, its reinterpretation as the 90.0 write defect, and the V1.88.3 propagation and Deckung WP runs.
- [Bankaifan/ha-luxtronik-shi firmware analysis](https://github.com/Bankaifan/ha-luxtronik-shi/blob/main/docs/firmware-3.92.3-shi-full-analysis.md) — independent disassembly of V3.92.3, used for the 3.92 DHW control.
- [#517](https://github.com/BenPru/luxtronik/issues/517) — unrelated to the thresholds: the `firmware_version_minor` crash on two-part versions introduced alongside `fecdf38`, since fixed.
