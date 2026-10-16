# Week 7 challenge publication — October 16, 2026

The owner explicitly requested opening all five competitions for participation.
A trusted operator used the existing configuration, validation and publication
services. Account roles were unchanged; publication is recorded as an operator
action with the owner's request and source verification in each challenge audit.
No entries, league rosters, fantasy scores or participant awards were created.

All included canonical event IDs, teams, scheduled states and kickoffs matched
ESPN's October 17 scoreboard or event summary before publication. School aliases
were resolved explicitly (for example Arizona St / Arizona State). Sources:
[ESPN scoreboard](https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates=20261017&groups=80&limit=1000),
[Miami–Florida State](https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=401858263),
[Baylor–TCU](https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=401856832),
[BYU–Notre Dame](https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=401856809).

| Competition | Published slate | Entry cutoff, Eastern |
| --- | --- | --- |
| Slate 12 | Twelve games; Alabama at Tennessee featured for tiebreaker | October 17, 11:55 AM EDT |
| Upset Hunter | Twelve explicitly designated underdogs with frozen 1–5 points | October 17, 11:55 AM EDT |
| Fantasy Five | 263 canonical eligible players from the same twelve games | October 17, 11:55 AM EDT |
| Lock of the Week | The same twelve-game slate | October 17, 11:55 AM EDT |
| Rivalry Duels | Five shared games | October 17, 3:25 PM EDT |

The twelve games are Ohio State at Indiana, Florida at Texas, Penn State at
Michigan, North Carolina at Duke, Georgia Tech at Virginia Tech, Alabama at
Tennessee, Auburn at Georgia, Missouri at Ole Miss, Arizona State at Texas Tech,
Florida State at Miami, TCU at Baylor and Notre Dame at BYU. Duels uses Penn State
at Michigan, North Carolina at Duke, Alabama at Tennessee, Florida State at Miami
and TCU at Baylor.

Upset teams were verified from the current provider's underdog flags. Editorial
difficulty is frozen at publication using the absolute margin: up to 3 → 1 point,
up to 7 → 2, up to 14 → 3, up to 21 → 4, above 21 → 5. These are free challenge
points, not wagers. No sportsbook links or wagering controls were added to CFFB.

All five plans passed server validation before mutation. Readback reports Open
for each challenge; server deadlines, sticky closure, immutable publication,
canonical pool rules and Wednesday matchup rollover remain enforced. Future
weeks still need their own validated publication; this operation does not copy
Week 7's slate forward or reopen it after its cutoff.
