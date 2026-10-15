"""Source-reviewed exceptions to exact provider identity matching.

Each exception is bound to the catalog ID, expected identity and provider ID.
These records do not change player positions, ownership or scoring rules.
"""
import json
from pathlib import Path

_RECORDS = json.loads((Path(__file__).parents[1] / 'data/espn/reviewed-player-identities.json').read_text())['players']
_BY_ID = {row['player_id']: row for row in _RECORDS}


def reviewed_espn_identity(player):
    row = _BY_ID.get(getattr(player, 'id', None))
    if row is None:
        return None
    if (player.name, player.school, player.position) != (row['catalog_name'], row['school'], row['catalog_position']):
        return None
    return row
