# ChatGPT Research Prompt: College Football Player Seed Data

Use this prompt in ChatGPT Research mode.

```text
You are helping prepare seed data for a college football fantasy app. Research real, recent college football players and produce a single markdown file that can later be ingested into seed scripts.

Important context from the codebase:

1. Backend player model currently stores only:
   - external_id: string | null
   - name: string
   - position: string
   - school: string

2. Backend weekly player stats model stores:
   - player_id (we will map this later)
   - season: integer
   - week: integer
   - source: string
   - stats: JSON object

3. Frontend mock player shape currently expects richer fields:
   - name: string
   - school: string
   - pos: string
   - conf: string
   - rank: number
   - adp: number
   - posRank: number
   - rostered: number
   - status: "HEALTHY" | "OUT" | "QUESTIONABLE" | "DOUBTFUL" | "IR"
   - number?: number
   - projection: object
   - history: array of { year, stats }
   - analysis: string

4. Canonical Power 4 conferences/teams in this repo are:
   - SEC: Alabama, Arkansas, Auburn, Florida, Georgia, Kentucky, LSU, Mississippi State, Missouri, Oklahoma, Ole Miss, South Carolina, Tennessee, Texas, Texas A&M, Vanderbilt
   - BIG10: Illinois, Indiana, Iowa, Maryland, Michigan, Michigan State, Minnesota, Nebraska, Northwestern, Ohio State, Oregon, Penn State, Purdue, Rutgers, UCLA, USC, Washington, Wisconsin
   - BIG12: Arizona, Arizona State, Baylor, BYU, Cincinnati, Colorado, Houston, Iowa State, Kansas, Kansas State, Oklahoma State, TCU, Texas Tech, UCF, Utah, West Virginia
   - ACC: Boston College, California, Clemson, Duke, Florida State, Georgia Tech, Louisville, Miami, NC State, North Carolina, Pittsburgh, SMU, Stanford, Syracuse, Virginia, Virginia Tech, Wake Forest

Research requirements:

- Use browsing/research mode and cite sources.
- Use only real players.
- Prioritize offensive fantasy-relevant players first: QB, RB, WR, TE.
- Include only players on Power 4 teams listed above.
- Prefer the most recent completed season for stable stats. Since today is March 21, 2026, use 2025 season stats as the primary statistical baseline.
- For school/team assignment, use the most current verifiable affiliation as of March 21, 2026. If a player transferred after the 2025 season, use the current school and note the source.
- Do not invent missing values. If a value cannot be verified, set it to null and add a note in `## Research Notes`.
- Normalize school names exactly to the canonical names above.
- Keep positions limited to QB, RB, WR, TE unless a source clearly lists a different offensive fantasy position that is still relevant.

Target output size:

- 40 to 75 players total
- At least:
  - 10 QBs
  - 10 RBs
  - 15 WRs
  - 5 TEs

What to deliver:

Return one markdown document only. Do not wrap the whole answer in a code block.

The markdown document must contain these sections in this exact order:

1. `# College Football Fantasy Seed Research`
2. `## Scope`
3. `## Research Notes`
4. `## Sources`
5. `## players_json`
6. `## player_stats_json`
7. `## frontend_players_json`

Formatting rules:

- `## Sources` must be a bullet list with source title and URL.
- `## players_json` must contain exactly one fenced `json` code block with an array of objects.
- `## player_stats_json` must contain exactly one fenced `json` code block with an array of objects.
- `## frontend_players_json` must contain exactly one fenced `json` code block with an array of objects.
- No trailing commentary after the final JSON block.

Schema requirements:

For `players_json`, each object must be:

{
  "external_id": string | null,
  "name": string,
  "position": "QB" | "RB" | "WR" | "TE",
  "school": string
}

Guidance:
- `external_id` should be a stable public identifier if a reliable one is available from a source we can later map back to, otherwise null.
- `school` must match the canonical team list exactly.

For `player_stats_json`, each object must be:

{
  "player_lookup": {
    "name": string,
    "school": string,
    "position": string
  },
  "season": 2025,
  "week": integer,
  "source": string,
  "stats": {
    "...": "source-backed weekly stats object"
  }
}

Guidance for `player_stats_json`:
- Prefer weekly stat rows for 2025 season.
- If weekly rows are too difficult to verify consistently for all players, provide season-total rows instead using `"week": 0`.
- Keep the `stats` object flat and numeric where possible.
- Use source field values like `cfbd`, `sportsdataio`, `espn`, or `manual_research`.
- Include stat keys that fit the player position, such as:
  - QB: passingYards, passingTds, interceptions, rushingYards, rushingTds
  - RB: rushingYards, rushingTds, receptions, receivingYards, receivingTds
  - WR/TE: receptions, receivingYards, receivingTds, rushingYards, rushingTds
- Only include values supported by sources.

For `frontend_players_json`, each object must be:

{
  "name": string,
  "school": string,
  "pos": "QB" | "RB" | "WR" | "TE",
  "conf": "SEC" | "BIG10" | "BIG12" | "ACC",
  "rank": integer,
  "adp": number | null,
  "posRank": integer,
  "rostered": number | null,
  "status": "HEALTHY" | "OUT" | "QUESTIONABLE" | "DOUBTFUL" | "IR",
  "number": integer | null,
  "projection": {
    "passingYards": number | null,
    "passingTds": number | null,
    "ints": number | null,
    "rushingYards": number | null,
    "rushingTds": number | null,
    "receptions": number | null,
    "receivingYards": number | null,
    "receivingTds": number | null,
    "fpts": number,
    "qbr": number | null,
    "expectedPlays": number | null,
    "expectedRushPerPlay": number | null,
    "expectedTdPerPlay": number | null,
    "floor": number | null,
    "ceiling": number | null,
    "boomProb": number | null,
    "bustProb": number | null
  },
  "history": [
    {
      "year": integer,
      "stats": {
        "passingYards": number | null,
        "passingTds": number | null,
        "ints": number | null,
        "rushingYards": number | null,
        "rushingTds": number | null,
        "receptions": number | null,
        "receivingYards": number | null,
        "receivingTds": number | null,
        "fpts": number
      }
    }
  ],
  "analysis": string
}

Guidance for `frontend_players_json`:
- Base `history` primarily on 2025 season stats. Add 2024 history when verifiable and useful.
- `projection` should be a clearly labeled research-based estimate for the next season, not fabricated certainty. Use conservative numeric estimates and keep them internally consistent with the player’s history, team context, and role.
- `analysis` should be 1 to 3 sentences and grounded in the player’s role, recent production, team situation, and transfer/depth-chart context.
- `rank` should be overall fantasy rank within this output set.
- `posRank` should be positional rank within this output set.
- `rostered` and `adp` may be null if no reliable source is available.
- `status` should default to `HEALTHY` unless a reputable recent injury/status report says otherwise.
- `conf` must match the school’s canonical Power 4 conference listed above.

Quality bar:

- Cross-check player school, position, and 2025 production before including each player.
- Prefer primary or highly reputable sources such as official school rosters, ESPN, CFBD, Sports Reference, conference sites, or major national CFB coverage.
- If sources conflict on a transfer destination or position, choose the most recent reputable source and note the conflict briefly in `## Research Notes`.
- Avoid duplicate players.
- Ensure valid JSON in all three code blocks.
- Sort `frontend_players_json` by `rank` ascending.

Before finalizing, verify:

- every school is canonical
- every player in `player_stats_json` exists in `players_json`
- every player in `frontend_players_json` exists in `players_json`
- JSON parses cleanly
- the markdown has exactly the required sections
```
