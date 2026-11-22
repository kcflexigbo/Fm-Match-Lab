# Ball position in FM27 27.1.0 (macOS x86_64) — what is known, and what is not

Status: **the native ball is reachable headless.** Use `match + 0x12ba0` for the last ball coordinates
applied by the simulation. `match + 0xaf0` is in the trajectory solver, not the current sample.
The earlier negative results below are preserved because they explain why the solver field was rejected.

Everything below is read-only observation of the installed engine through the host.

## What works

| Item | Where | Notes |
|---|---|---|
| Player position | `player + 0x140` | `float x, y, z` in yards; **x across (±37.5), y along (±52.5)**, origin centre spot |
| On pitch | `player + 0x23b6` | `1` while playing |
| Slot | `player + 0x23e1` | `0..10`; roster index ≠ slot |
| Per-tick history | `player + 0x170` | pointer to an array, stride `0x20`, first tick `+0x200`, last `+0x208` |
| Current tick | shared context `+0x154dc` | |
| Last applied ball sample | `match + 0x12a30 + 0x170` = `match + 0x12ba0` | `float x, y, z`; same pitch axes as players |

## Native ball coordinate path

Capstone trace on the `2505117` x86_64 slice:

1. `0x49e6541–0x49e6565` constructs the physics object at `match+0xad0` and passes it into the object at
   `match+0x12a30`. The constructor at `0x4a2fe90` stores that pointer at offset zero. The latter object's
   `+0x278` pointed back to `match` in both archived snapshots checked.
2. `0x4a46c30` reads the match tick via the backlink, indexes the physics trajectory, and writes XY
   to `ball+0x170` at `0x4a46e61` and Z to `ball+0x178` at `0x4a46e68`. Its diagnostic strings are
   `match_ball.cpp` and `get_coords` (`0x5979f33`, `0x5979fad`). The match loop has the same sampling and
   write sequence at `0x49ec45b–0x49ec7a5`.
3. The raw lookup has two levels: `i = clamp(tick, ball[+0x2c0], ball[+0x2a8]) - ball[+0x2c0]`
   (signed 32-bit tick bounds); `entry = physics+0xa4+12*i`; `j = u16(entry)+u8(entry+2)-1`;
   XYZ starts at `physics+0x6d0+0x40*j`. The sample height is adjusted before writing `ball+0x178`.
   `0x509caa0` initializes the `0x40`-stride record buffer; `0x509cbf0` advances the trajectory.
   This describes the observed reader, **not** a retained history API: the solver reuses its storage.
4. The `PLAYER_POSITIONS_PACKET` vtable is at `0x5d20440`. The producer branch at `0x4a0be57`
   allocates the packet and calls `0x4f97190`. That function builds two roster vectors (stride `0x20`),
   reading each player's `+0x140` at `0x4f97227` and `0x4f97347`. There is no appended ball sample.

The host reads the cached `get_coords` output instead of calling anything or indexing a possibly
reused trajectory. Host loop ticks are observation labels: in a 1,000-frame bounded trace, the
current trajectory indexed with `tick-1` matched the last applied XY exactly in 747 frames, vs 190
at `tick`. For example, host ticks 3000 and 3001 gave `(-2.82, 10.99)` and `(0.25, 10.00)`;
at host tick 3000 the trajectory indexed at 3000 already held the latter point. Do not treat the
cache as exact-frame playback or apply a blanket one-tick correction.

### Full-match A/B check

Same checked fixture and seeds, default `--tick-step 1`. Static means an XY step under 0.01 yd;
step percentiles exclude those samples.

| Seed | Ticks | Field | Within 2 yd | Static | Moving step median / p90 / p99 (yd) |
|---|---:|---|---:|---:|---|
| 1 | 23,377 | solver `+0xaf0` | 12.4% | 65.8% | 3.84 / 22.82 / 51.96 |
| 1 | 23,377 | applied `+0x12ba0` | 46.5% | 37.9% | 1.48 / 3.63 / 5.88 |
| 2 | 23,100 | solver `+0xaf0` | 12.7% | 66.6% | 3.77 / 22.92 / 52.97 |
| 2 | 23,100 | applied `+0x12ba0` | 44.8% | 36.8% | 1.44 / 3.63 / 5.95 |

Player frames were identical on both old/new pairs; scores and finish ticks were unchanged.
Proximity and motion are comparative diagnostics, not pass/fail rules: flight, restarts and stopped
play can legitimately make the ball distant or stationary. The named writer and trajectory reader
are the stronger identification evidence. Existing JSONL files still contain the old field; rebuild
and regenerate before showing the ball. The JSONL schema is unchanged.

Validation: 22 players per tick, median 0.36 yd of movement per engine tick (4 ticks = 1 match second),
sane bounds, coherent formations, and the goalkeeper's position fixes the attacking direction.

## The ball candidate, and why it is not the ball

`match + 0xaf0` holds `float x, y, z`; at rest `z = 0.111`, which is the ball radius, and at goals it sits
on the goal line. That is what made it look right at first. It fails every behavioural test:

| Test | Live ball | `match+0xaf0` |
|---|---|---|
| within 2 yd of a player | almost always | **11%** |
| within 5 yd | — | 32% |
| within 10 yd | — | 62% |
| more than 20 yd from everyone | rare | 14% |
| within 3 yd while "slow" | ~always (at the carrier's feet) | **18%** |
| moves every tick | ~always | static **67%** of ticks |
| update interval | 1 tick | median 1, mean **3.0**, p90 3 ticks |
| step when it does move | small | median 3.8 yd, p90 **23.1 yd** |
| time-lag alignment (players shifted −8..+8) | best at 0 | best at **+6 ticks, 27%** |

Eight coordinate transforms were tried (flip x/y/both, swap, and swaps with flips): as-is is the best at
19.5%, every other transform scores 2–6%, so it is not a frame/orientation error. It is also not a target
ahead of the carrier: the ball is ahead of the nearest player's movement 52% of the time — a coin flip.

## Searches performed (all negative)

1. **Pointer scan of the match object** (`match+0x0..0x1000`, 8-byte aligned): 54 pointers whose target
   looked positioned; all had zero floats at `+0x140`. Nothing ball-like.
2. **Entity scan of the shared match context** (`*(match+0x280)`, 0x18000 bytes, every pointer): 4,010
   candidates; none had a plausible `+0x170` history pointer or sane tick range, i.e. no entity objects
   other than those already known (players are reached through the teams, not this context).
3. **Full writable-memory scan** at tick 6000: every 4-byte-aligned float pair with `|x|≤40`, `|y|≤56`
   within 2 yd of an on-pitch player, excluding ±0x4000 around each player object → **3,764 candidates**.
   After three more ticks (still within 12 yd of a player, still in bounds): **3,755 survivors** — but only
   **578 distinct positions**, i.e. copies of the 22 players' own coordinates, and the `0xaf0` value itself
   appears at 24 addresses. The scan cannot separate the ball from position copies this way.

## Reproducing the measurements

```sh
APP="$HOME/FM27/Football Manager 27.app"
.venv/bin/python scripts/build_native_mac.py --game-root "$APP"
mkdir -p private/positions
FM27_POSITIONS_JSONL="$PWD/private/positions/pos.jsonl" \
FM27_GAME_ROOT="$APP/Contents/PlugIns/game_plugin.bundle/Contents/Resources" \
  private/engine/fm27_native/fm27_mac_host \
  --fixture private/engine/fm27_native/fixtures/match.pkm \
  --seed 1 --output private/positions/run.jsonl

# the diagnostics (proximity, static spells, lags, transforms, ahead-of-carrier)
.venv/bin/python scripts/ball_diagnostics.py private/positions/pos.jsonl
```

Repeat with seed 2 and a different output path for the second full match. Raw traces and comparison
outputs stay in git-ignored `private/positions/`.
