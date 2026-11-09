"""Validated NBA optimizer records. No provider-specific data or rules inference."""
from dataclasses import dataclass
from math import isfinite

POSITIONS = frozenset({'PG', 'SG', 'SF', 'PF', 'C'})
DEFAULT_SLOTS = ('PG1', 'PG2', 'SG1', 'SG2', 'SF1', 'SF2', 'PF1', 'PF2', 'C')
STACKING_TYPES = ('baseline', 'type_1', 'type_2', 'type_3', 'type_4', 'type_5')
FLEX_POSITIONS = {'G': frozenset({'PG', 'SG'}), 'F': frozenset({'SF', 'PF'}),
                  'G/F': POSITIONS - {'C'}, 'F/C': frozenset({'SF', 'PF', 'C'}),
                  'UTIL': POSITIONS}


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    team: str
    opponent: str
    game_id: str
    positions: frozenset[str]
    salary: int
    projected_points: float


@dataclass(frozen=True)
class ContestRules:
    # Traditional FanDuel classic research configuration; callers must verify
    # the actual contest. The CLI deliberately requires an explicit rules file.
    salary_cap: int = 60000
    slots: tuple[str, ...] = DEFAULT_SLOTS
    max_players_per_team: int = 4
    min_teams: int = 3


@dataclass(frozen=True)
class Lineup:
    assignments: tuple[tuple[str, Player], ...]

    @property
    def players(self):
        return tuple(player for _, player in self.assignments)

    @property
    def player_ids(self):
        return tuple(player.player_id for player in self.players)

    @property
    def projected_points(self):
        return sum(player.projected_points for player in self.players)

    @property
    def salary(self):
        return sum(player.salary for player in self.players)


def require_integer(value, name, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')


def require_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f'{name} must be a finite number')


def require_text(value, name):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f'{name} must be nonempty text without surrounding spaces')


def slot_positions(slot):
    require_text(slot, 'slot')
    base = slot.rstrip('0123456789')
    if base in POSITIONS:
        return frozenset({base})
    if base in FLEX_POSITIONS:
        return FLEX_POSITIONS[base]
    raise ValueError(f'Unsupported roster slot: {slot}')


def validate_pool(players, rules):
    require_integer(rules.salary_cap, 'salary_cap')
    require_integer(rules.max_players_per_team, 'max_players_per_team')
    require_integer(rules.min_teams, 'min_teams')
    if (not isinstance(rules.slots, (tuple, list)) or not rules.slots
            or any(not isinstance(slot, str) for slot in rules.slots)
            or len(rules.slots) != len(set(rules.slots))):
        raise ValueError('Roster slots must be nonempty and uniquely named')
    for slot in rules.slots:
        slot_positions(slot)
    if not players:
        raise ValueError('Player pool is empty')
    ids, teams, games = set(), {}, {}
    for player in players:
        for field in ('player_id', 'name', 'team', 'opponent', 'game_id'):
            require_text(getattr(player, field), field)
        if player.player_id in ids:
            raise ValueError(f'Duplicate player_id: {player.player_id}')
        ids.add(player.player_id)
        require_integer(player.salary, 'salary')
        require_number(player.projected_points, 'projected_points')
        if not isinstance(player.positions, (set, frozenset)) or not player.positions or not player.positions <= POSITIONS:
            raise ValueError('Player positions must be a nonempty set of PG/SG/SF/PF/C')
        if player.team == player.opponent:
            raise ValueError('A team cannot play itself')
        for team, opponent in ((player.team, player.opponent), (player.opponent, player.team)):
            identity = (opponent, player.game_id)
            if team in teams and teams[team] != identity:
                raise ValueError('Conflicting team/opponent/game mapping; supply one slate')
            teams[team] = identity
        matchup = frozenset({player.team, player.opponent})
        if player.game_id in games and games[player.game_id] != matchup:
            raise ValueError('A game_id cannot identify multiple matchups')
        games[player.game_id] = matchup


def validate_pairs(players, pairs):
    by_id = {player.player_id: player for player in players}
    result = set()
    for pair in pairs:
        if len(pair) != 2 or pair[0] == pair[1] or any(p not in by_id for p in pair):
            raise ValueError('Each screened pair must contain two distinct player IDs in the pool')
        first, second = (by_id[p] for p in pair)
        if (first.team, first.game_id) != (second.team, second.game_id):
            raise ValueError('Screened pairs must be teammates in the same game')
        result.add(tuple(sorted(pair)))
    return sorted(result)
