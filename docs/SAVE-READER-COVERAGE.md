# Save reader coverage: what fmsave opens, and what it never touches

Measured on `Kenneth  Igbo - Chelsea.fm` (FM 27.1.0, 6 Aug 2026) by patching the section and region
readers and calling every public API once (`scripts/save_reader_coverage.py`).

The save container holds **78 entries**. A full read touches **13**. So the gap is mostly *not read at
all*, not read-and-hidden.

## Read (13)

| Entry | Powers |
|---|---|
| `game_db` (163 MB) | players, clubs, competitions, contracts, fixtures, staff, finances, stadiums, tactics, set pieces, squad planner, injuries, suspensions, league tables, awards-adjacent records |
| `news` (17 MB) | decompressed during the sweep, **but no API returns it** |
| `humans` (26 KB) | the human manager/USER_DATA linkage |
| `injury_manager` (91 KB) | `injuries()`, `injury_types()` |
| `job_centre` (34 KB) | `job_vacancies()` |
| `match_stats_cfg` (2 MB) | intended for `team_match_stats()`, **which fails on 27.1.0** (see below) |
| `player_stats_hist_dt` (995 KB) | `player_match_stats()` |
| `save_game_summary` (1.8 KB) | save identity/version |
| `tactics_man` (1.6 MB) | `tactics()` |
| `tc_record_man` (17 MB) | club/competition records used by tables |
| `training_man` (81 KB) | `training()` |
| `feeder_man` (2 KB) | affiliates |
| synthetic region | `pl_hist_ls` / `non_pl_hist_ls` handling |

## Never opened (65)

Grouped by what they would give if decoded:

| Group | Entries | Sizes |
|---|---|---|
| **Transfers** | `transfer_man`, `trade_man` | 4.4 MB, 46 B |
| **Lists and scouting** | `shortlist_man`, `scout_man` | 3.6 MB, 280 KB |
| **Career records** | `person_record_manager`, `person_record_history_ls/_dt`, `pl_hist_ls/_dt`, `non_pl_hist_ls/_dt` | ~11 MB |
| **Competition archives** | `tc_league_history_*`, `tc_cup_history_*`, `tc_manager_history_*`, `award_*`, `comp_history_dt` | ~9 MB |
| **Managers/staff** | `manager_manager`, `official_manager`, `staff` history (`person_db_changes`) | 2.1 MB |
| **Money** | `finance_manager`, `financial_fair_play_manager`, `starting_club_debt_db` | 5.7 MB+ |
| **Interactions** | `press_conference_manager`, `team_talk_man`, `media_man`, `interaction_manager` | ~1 MB |
| **Matchday** | `weather_manager`, `matchday_manager`, `sim_stats`, `play_fixture_manager`, `match_stats_cfg` (partly) | ~380 KB |
| **Game state flags** | `fog_of_war`, `board_takeover_manager`, `dispute`, `fine_manager`, `morale_manager`, `captain_system`, `awol`, `virtual_manager`, `network_man`, `database_analyser`, `edit_session_man` | small |
| **Misc** | `memory_pools`, `game_info`, `496_265607481.scm`, `used_player_data`, `training_camp_man` | small–2 MB |

## Read but not returned

- **`news` (17 MB)** is decompressed and discarded — no `news()` API.
- **`match_stats_cfg`** is read, but `team_match_stats()` raises *"section 'match_stats_cfg': no entry"*
  even though the section exists in the index — a reader bug on 27.1.0, not a missing file.
- `humans`, `tc_record_man`, `player_stats_hist_dt` are read to build internal indexes and surface only
  indirectly.

## Suggested next decoders

1. `person_record_manager` + `pl_hist_*` — real career histories; makes development/scouting judgements reliable.
2. `shortlist_man` + `scout_man` — shortlists and scout reports, so recommendations can carry knowledge.
3. `manager_manager` — AI manager records and tendencies for opponent prep.
4. `news` — already decompressed, cheapest win.

## Reproducing

```sh
.venv/bin/python scripts/save_reader_coverage.py "…/Kenneth  Igbo - Chelsea.fm"
```

Patches `read_section`, `_section_loan` and the region readers, calls each public API once with no
arguments, and prints the touched and untouched entry sets.
