"""Normalized local CSV inputs, explicit rules, and local-only atomic exports."""
import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from nba_models import ContestRules, Player, validate_pool
from nba_screening import HistoryRow, require_aware_time, validate_history

PROJECT_ROOT = Path(__file__).resolve().parent
PLAYER_COLUMNS = ('player_id', 'name', 'team', 'opponent', 'game_id', 'positions',
                  'salary', 'projected_points', 'projection_time', 'game_time')
HISTORY_COLUMNS = ('player_id', 'team', 'game_id', 'game_time', 'projection_time',
                   'decision_time', 'observed_at', 'projected_points', 'actual_points')
RULE_FIELDS = {'salary_cap', 'slots', 'max_players_per_team', 'min_teams'}


def parse_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require_aware_time(parsed, 'timestamp')
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError('Use an ISO 8601 timestamp with an explicit timezone') from error


def read_rows(path, columns):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('Missing or duplicate CSV column names')
        if set(reader.fieldnames) != set(columns):
            raise ValueError(f'Expected CSV columns: {", ".join(columns)}')
        rows = list(reader)
    for index, row in enumerate(rows, 2):
        if None in row or any(value is None or not value.strip() for value in row.values()):
            raise ValueError(f'Malformed or missing CSV value on row {index}')
    return rows


def read_players(path, cutoff):
    require_aware_time(cutoff, 'cutoff')
    players, games = [], {}
    for row in read_rows(path, PLAYER_COLUMNS):
        projection_time, game_time = parse_time(row['projection_time']), parse_time(row['game_time'])
        if not projection_time <= cutoff < game_time:
            raise ValueError('Forecast is after cutoff or a game starts at/before cutoff; reject the whole pool')
        if row['game_id'] in games and games[row['game_id']] != game_time:
            raise ValueError('Game has inconsistent start times')
        games[row['game_id']] = game_time
        positions = row['positions'].split('/')
        if len(positions) != len(set(positions)):
            raise ValueError('Duplicate position eligibility')
        players.append(Player(row['player_id'], row['name'], row['team'], row['opponent'],
                              row['game_id'], frozenset(positions), int(row['salary']),
                              float(row['projected_points'])))
    validate_pool(players, ContestRules())
    return players


def read_rules(path):
    with Path(path).open(encoding='utf-8') as stream:
        values = json.load(stream)
    if not isinstance(values, dict) or set(values) != RULE_FIELDS or not isinstance(values['slots'], list):
        raise ValueError(f'Rules JSON must explicitly supply {sorted(RULE_FIELDS)}; slots must be a list')
    return ContestRules(values['salary_cap'], tuple(values['slots']),
                        values['max_players_per_team'], values['min_teams'])


def read_history(path):
    result = [HistoryRow(row['player_id'], row['team'], row['game_id'],
                         *(parse_time(row[key]) for key in ('game_time', 'projection_time', 'decision_time', 'observed_at')),
                         float(row['projected_points']), float(row['actual_points']))
              for row in read_rows(path, HISTORY_COLUMNS)]
    validate_history(result)
    return result


def local_output_path(path):
    destination = Path(path).resolve()
    root = PROJECT_ROOT / 'outputs'
    if not destination.is_relative_to(root) or destination == root:
        raise ValueError('Generated files must stay inside this project\'s ignored outputs/ directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def write_lineups(lineups, path, stacking, metadata=None):
    destination = local_output_path(path)
    if destination.exists():
        raise FileExistsError(f'Output already exists: {destination}')
    columns = ('lineup', 'stacking', 'slot', 'player_id', 'name', 'team', 'opponent',
               'game_id', 'salary', 'projected_points', 'total_salary', 'total_projected_points', 'run_settings')
    settings = json.dumps(metadata or {}, sort_keys=True, allow_nan=False)
    # Hard-link the finished temporary file: atomic, and fails rather than
    # overwriting an existing destination (even if another process races us).
    with tempfile.NamedTemporaryFile(mode='w', newline='', encoding='utf-8',
                                     dir=destination.parent, suffix='.tmp') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for index, lineup in enumerate(lineups, 1):
            for slot, player in lineup.assignments:
                writer.writerow(dict(lineup=index, stacking=stacking, slot=slot,
                                     player_id=player.player_id, name=player.name, team=player.team,
                                     opponent=player.opponent, game_id=player.game_id, salary=player.salary,
                                     projected_points=player.projected_points, total_salary=lineup.salary,
                                     total_projected_points=lineup.projected_points, run_settings=settings))
        stream.flush()
        os.fsync(stream.fileno())
        os.link(stream.name, destination)
