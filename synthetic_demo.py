"""Create invented local inputs and exercise all six CLI configurations."""
import csv
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from nba_io import HISTORY_COLUMNS, PLAYER_COLUMNS, PROJECT_ROOT
from nba_models import DEFAULT_SLOTS, STACKING_TYPES


def write_csv(path, columns, rows):
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def create_inputs(directory):
    cutoff = datetime(2025, 2, 1, 19, tzinfo=timezone.utc)
    players = []
    for team_index, (team, opponent, game_id) in enumerate((('A','B','AB'),('B','A','AB'),
                                                           ('C','D','CD'),('D','C','CD'))):
        for position_index, position in enumerate(('PG','SG','SF','PF','C')):
            index = team_index * 5 + position_index
            players.append(dict(player_id=f'invented_{index}', name=f'Invented Player {index}',
                                team=team, opponent=opponent, game_id=game_id, positions=position,
                                salary=4500+500*(index % 4), projected_points=20+(index*13) % 29,
                                projection_time=(cutoff-timedelta(hours=1)).isoformat(),
                                game_time=(cutoff+timedelta(hours=1)).isoformat()))
    history = []
    for day in range(30):
        game_time = cutoff - timedelta(days=day+2)
        for player in players:
            # A and B have deliberately aligned residuals; C and D vary by role.
            error = (day % 7) - 3
            if player['team'] in ('C','D') and player['positions'] in ('SG','PF'):
                error = -error
            history.append(dict(player_id=player['player_id'], team=player['team'],
                                game_id=f'past_{player["game_id"]}_{day}', game_time=game_time.isoformat(),
                                projection_time=(game_time-timedelta(hours=2)).isoformat(),
                                decision_time=(game_time-timedelta(hours=1)).isoformat(),
                                observed_at=(game_time+timedelta(hours=3)).isoformat(),
                                projected_points=30, actual_points=30+error))
    write_csv(directory/'players.csv', PLAYER_COLUMNS, players)
    write_csv(directory/'history.csv', HISTORY_COLUMNS, history)
    (directory/'rules.json').write_text(json.dumps(dict(salary_cap=60000,slots=DEFAULT_SLOTS,
                                                     max_players_per_team=4,min_teams=3), indent=2))
    return cutoff


def main():
    output_root = PROJECT_ROOT/'outputs'
    output_root.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='synthetic_demo_', dir=output_root))
    cutoff = create_inputs(directory)
    for stacking in STACKING_TYPES:
        subprocess.run([sys.executable, str(PROJECT_ROOT/'nba_optimizer.py'),
                        '--players', str(directory/'players.csv'), '--rules', str(directory/'rules.json'),
                        '--history', str(directory/'history.csv'), '--cutoff', cutoff.isoformat(),
                        '--stacking', stacking, '--num-lineups', '3', '--max-overlap', '7',
                        '--output', str(directory/f'{stacking}.csv')], check=True)
    print(f'Completed 6 configurations with invented inputs only: {directory}')


if __name__ == '__main__':
    main()
