"""Past-only empirical teammate screening; thresholds are research settings."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from statistics import StatisticsError, correlation
from nba_models import require_integer, require_number, require_text

MIN_SHARED_GAMES = 20
MIN_CORRELATION = 0.1
SHRINKAGE_GAMES = 20.0


@dataclass(frozen=True)
class HistoryRow:
    player_id: str
    team: str
    game_id: str
    game_time: datetime
    projection_time: datetime
    decision_time: datetime
    observed_at: datetime
    projected_points: float
    actual_points: float


@dataclass(frozen=True)
class ScreenedPair:
    first_id: str
    second_id: str
    shared_games: int
    correlation: float
    shrunk_correlation: float


def require_aware_time(value, name):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f'{name} must be a timezone-aware datetime')


def validate_history(history):
    identities, games = set(), {}
    for row in history:
        for field in ('player_id', 'team', 'game_id'):
            require_text(getattr(row, field), field)
        for field in ('game_time', 'projection_time', 'decision_time', 'observed_at'):
            require_aware_time(getattr(row, field), field)
        require_number(row.projected_points, 'historical projected_points')
        require_number(row.actual_points, 'actual_points')
        if not row.projection_time <= row.decision_time < row.game_time < row.observed_at:
            raise ValueError('Historical forecast/result timing is invalid')
        identity = (row.player_id, row.game_id)
        if identity in identities:
            raise ValueError('Duplicate historical player/game observation')
        identities.add(identity)
        if row.game_id in games and games[row.game_id] != row.game_time:
            raise ValueError('Historical game_id has inconsistent start times')
        games[row.game_id] = row.game_time


def screen_pairs(players, history, cutoff, *, min_games=MIN_SHARED_GAMES,
                 min_correlation=MIN_CORRELATION, shrinkage=SHRINKAGE_GAMES):
    """Screen positive forecast-error association using only available past games.

    Same-team observations must match the pair's current team. This reduces
    transfer across trades; it does not establish unchanged roles or causality.
    """
    require_aware_time(cutoff, 'cutoff')
    require_integer(min_games, 'min_games', minimum=3)
    require_number(min_correlation, 'min_correlation')
    require_number(shrinkage, 'shrinkage')
    if not 0 < min_correlation <= 1 or shrinkage < 0:
        raise ValueError('min_correlation must be in (0, 1] and shrinkage nonnegative')
    history = tuple(history)
    validate_history(history)
    current = {player.player_id: player for player in players}
    residuals = defaultdict(dict)
    for row in history:
        player = current.get(row.player_id)
        if (player is not None and row.team == player.team and row.game_time < cutoff
                and row.observed_at <= cutoff and row.game_id != player.game_id):
            residuals[row.player_id][row.game_id] = row.actual_points - row.projected_points
    result = []
    for first, second in combinations(sorted(players, key=lambda p: p.player_id), 2):
        if (first.team, first.game_id) != (second.team, second.game_id):
            continue
        shared = sorted(residuals[first.player_id].keys() & residuals[second.player_id].keys())
        if len(shared) < min_games:
            continue
        try:
            raw = correlation([residuals[first.player_id][g] for g in shared],
                              [residuals[second.player_id][g] for g in shared])
        except StatisticsError:
            continue  # Constant residuals have no defined correlation.
        shrunk = raw * len(shared) / (len(shared) + shrinkage)
        if shrunk >= min_correlation:
            result.append(ScreenedPair(first.player_id, second.player_id, len(shared), raw, shrunk))
    return result
