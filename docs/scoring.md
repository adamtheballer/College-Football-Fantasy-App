# Scoring Contract

This app scores only college fantasy offensive players and kickers.

Supported fantasy positions:

- `QB`
- `RB`
- `WR`
- `TE`
- `FLEX`
- `SUPERFLEX`
- `K`

Unsupported positions, including `DST`, `D/ST`, `DEF`, `LB`, `DB`, and other IDP positions, score `0` and are not part of the game.

## Rule Profiles

Scoring rules are validated before league creation/update. Invalid rules fail instead of silently becoming `0`.

Supported profiles:

- `offense`
- `kicker`

Flat scoring JSON is supported for simple league settings:

```json
{
  "ppr": 1,
  "pass_yards": 0.04,
  "pass_tds": 4,
  "passing_interceptions": -2,
  "rush_yards": 0.1,
  "rush_tds": 6,
  "rec_yards": 0.1,
  "rec_tds": 6,
  "fg_made_0_39": 3,
  "fg_made_40_49": 4,
  "fg_made_50_plus": 5,
  "xp_made": 1
}
```

Nested scoring JSON is supported when explicit profiles are needed:

```json
{
  "offense": {
    "receptions": 1,
    "pass_yards": 0.04,
    "pass_tds": 4
  },
  "kicker": {
    "fg_made_0_39": 3,
    "fg_made_40_49": 4,
    "fg_made_50_plus": 5,
    "xp_made": 1
  }
}
```

## Default Offense Rules

| Rule | Points |
|---|---:|
| `pass_yards` | `0.04` |
| `pass_tds` | `4` |
| `passing_interceptions` | `-2` |
| `rush_yards` | `0.1` |
| `rush_tds` | `6` |
| `receptions` | `1` |
| `rec_yards` | `0.1` |
| `rec_tds` | `6` |
| `two_point_conversions` | `2` |
| `fumbles_lost` | `-2` |
| `fumble_return_tds` | `6` |

## Default Kicker Rules

| Rule | Points |
|---|---:|
| `fg_made_0_39` | `3` |
| `fg_made_40_49` | `4` |
| `fg_made_50_plus` | `5` |
| `xp_made` | `1` |
| `fg_missed` | `-1` |

## Validation Rules

The app rejects:

- Unknown scoring profiles.
- Unknown scoring keys.
- Null, empty, non-numeric, `NaN`, or infinite values.
- Mixed nested-profile and flat scoring keys.
- Ambiguous aliases that map to the same canonical rule in one config.
- Malformed scoring JSON.

## Stat Normalization

Provider stats are normalized into canonical stat keys before scoring. Example:

| Provider field | Canonical stat |
|---|---|
| `PassingYards` | `pass_yards` |
| `PassingTouchdowns` | `pass_tds` |
| `Interceptions` | `passing_interceptions` for supported offensive positions |
| `RushingYards` | `rush_yards` |
| `RushingTouchdowns` | `rush_tds` |
| `Receptions` | `receptions` |
| `ReceivingYards` | `rec_yards` |
| `ReceivingTouchdowns` | `rec_tds` |
| `FieldGoalsMade0to39` | `fg_made_0_39` |
| `FieldGoalsMade40to49` | `fg_made_40_49` |
| `FieldGoalsMade50Plus` | `fg_made_50_plus` |
| `ExtraPointsMade` | `xp_made` |

## Score Versioning

Each `player_week_scores` row records:

- `stat_version`
- `source_provider`
- `source_event_id`
- `source_updated_at`
- `calculation_version`
- `previous_score`
- `correction_delta`

Recalculating with unchanged inputs is idempotent and does not increment `stat_version`. When provider stats or score-relevant source metadata changes, the row stores the previous score, increments `stat_version`, and records the point delta.
