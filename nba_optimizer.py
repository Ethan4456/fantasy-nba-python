"""Sequential provider-forecast NBA lineup optimization with PuLP/CBC."""
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
import pulp
from nba_models import (ContestRules, Lineup, STACKING_TYPES, require_integer,
                        require_number, slot_positions, validate_pairs, validate_pool)
from nba_stacking import add_stacking_constraints


def build_model(players, rules, stacking, pairs):
    model = pulp.LpProblem('nba_lineup', pulp.LpMaximize)
    assignments = {(i, j): pulp.LpVariable(f'slot_{i}_{j}', cat='Binary')
                   for i, player in enumerate(players) for j, slot in enumerate(rules.slots)
                   if player.positions & slot_positions(slot)}
    selected = {i: pulp.lpSum(var for (p, _), var in assignments.items() if p == i)
                for i in range(len(players))}
    for j in range(len(rules.slots)):
        model += pulp.lpSum(var for (_, s), var in assignments.items() if s == j) == 1
    for expression in selected.values():
        model += expression <= 1
    model += pulp.lpSum(player.salary * selected[i] for i, player in enumerate(players)) <= rules.salary_cap
    teams = defaultdict(list)
    for i, player in enumerate(players):
        teams[player.team].append(i)
    used_teams = []
    for indices in teams.values():
        used = pulp.LpVariable(f'team_{len(used_teams)}', cat='Binary')
        count = pulp.lpSum(selected[i] for i in indices)
        model += count <= rules.max_players_per_team * used
        model += count >= used
        used_teams.append(used)
    model += pulp.lpSum(used_teams) >= rules.min_teams
    add_stacking_constraints(model, players, selected, stacking, pairs)
    model += pulp.lpSum(player.projected_points * selected[i] for i, player in enumerate(players))
    return model, assignments, selected


def extract_lineup(players, rules, assignments):
    chosen = tuple((slot, players[i]) for j, slot in enumerate(rules.slots)
                   for i in range(len(players))
                   if (i, j) in assignments and pulp.value(assignments[i, j]) > 0.5)
    lineup = Lineup(chosen)
    if len(chosen) != len(rules.slots) or len(set(lineup.player_ids)) != len(rules.slots):
        raise RuntimeError('Solver returned an invalid slot assignment')
    return lineup


def generate_lineups(players, rules=None, *, stacking='baseline', screened_pairs=(),
                     num_lineups=1, max_overlap=None, time_limit=60):
    """Return exactly the requested optimal lineups, or raise; never relax a rule.

    screened_pairs is an explicit prequalified allowlist at this low-level API.
    The CLI obtains it from timestamp-checked historical residual screening.
    """
    players = tuple(players)
    rules = rules or ContestRules()
    validate_pool(players, rules)
    if stacking not in STACKING_TYPES:
        raise ValueError(f'Unknown stacking type: {stacking}')
    require_integer(num_lineups, 'num_lineups')
    max_overlap = len(rules.slots) - 1 if max_overlap is None else max_overlap
    require_integer(max_overlap, 'max_overlap', minimum=0)
    if max_overlap >= len(rules.slots):
        raise ValueError('max_overlap must be smaller than the roster size')
    require_number(time_limit, 'time_limit')
    if time_limit <= 0:
        raise ValueError('time_limit must be positive')
    pairs = validate_pairs(players, screened_pairs)
    if stacking in ('type_2', 'type_4') and not pairs:
        raise ValueError('This stacking type requires at least one screened teammate pair')
    model, assignments, selected = build_model(players, rules, stacking, pairs)
    from nba_io import local_output_path
    output_root = local_output_path(Path(__file__).resolve().parent / 'outputs' / '.solver').parent
    with TemporaryDirectory(prefix='cbc_', dir=output_root) as scratch_directory:
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, threads=1, gapRel=0)
        solver.tmpDir = scratch_directory
        results = []
        for lineup_index in range(num_lineups):
            model.solve(solver)
            if model.status != pulp.LpStatusOptimal or model.sol_status != pulp.LpSolutionOptimal:
                raise ValueError(f'Could not prove an optimal lineup {lineup_index + 1}: '
                                 f'{pulp.LpStatus[model.status]}. No complete result returned.')
            lineup = extract_lineup(players, rules, assignments)
            results.append(lineup)
            ids = set(lineup.player_ids)
            model += pulp.lpSum(selected[i] for i, player in enumerate(players)
                                if player.player_id in ids) <= max_overlap
    return results


def parse_args():
    import argparse
    from nba_screening import MIN_SHARED_GAMES, MIN_CORRELATION, SHRINKAGE_GAMES
    parser = argparse.ArgumentParser(description='Local NBA research optimizer; no contest submission or backtest claim.')
    parser.add_argument('--players', required=True, help='Normalized local player CSV')
    parser.add_argument('--rules', required=True, help='Explicit contest-rule JSON')
    parser.add_argument('--cutoff', required=True, help='Initial decision time with timezone')
    parser.add_argument('--stacking', choices=STACKING_TYPES, default='baseline')
    parser.add_argument('--history', help='Normalized historical forecast/result CSV; required for types 2 and 4')
    parser.add_argument('--min-shared-games', type=int, default=MIN_SHARED_GAMES)
    parser.add_argument('--min-correlation', type=float, default=MIN_CORRELATION)
    parser.add_argument('--shrinkage-games', type=float, default=SHRINKAGE_GAMES)
    parser.add_argument('--num-lineups', type=int, default=1)
    parser.add_argument('--max-overlap', type=int)
    parser.add_argument('--time-limit', type=float, default=60, help='Seconds per solve; uncertified incumbents are rejected')
    parser.add_argument('--output', required=True, help='New CSV path beneath outputs/')
    return parser, parser.parse_args()


def main():
    from dataclasses import asdict
    from nba_io import local_output_path, parse_time, read_history, read_players, read_rules, write_lineups
    from nba_screening import screen_pairs
    parser, args = parse_args()
    try:
        output = local_output_path(args.output)
        if output.exists():
            raise FileExistsError('Choose a new output filename; existing files are never overwritten')
        cutoff = parse_time(args.cutoff)
        players, rules = read_players(args.players, cutoff), read_rules(args.rules)
        if args.stacking in ('type_2', 'type_4') and not args.history:
            raise ValueError('Types 2 and 4 require --history for pre-cutoff pair screening')
        screened = screen_pairs(players, read_history(args.history), cutoff,
                                min_games=args.min_shared_games, min_correlation=args.min_correlation,
                                shrinkage=args.shrinkage_games) if args.history else []
        lineups = generate_lineups(players, rules, stacking=args.stacking,
                                   screened_pairs=[(p.first_id, p.second_id) for p in screened],
                                   num_lineups=args.num_lineups, max_overlap=args.max_overlap,
                                   time_limit=args.time_limit)
        metadata = {'cutoff': cutoff.isoformat(), 'rules': asdict(rules),
                    'num_lineups': args.num_lineups,
                    'max_overlap': args.max_overlap if args.max_overlap is not None else len(rules.slots)-1,
                    'min_shared_games': args.min_shared_games, 'min_correlation': args.min_correlation,
                    'shrinkage_games': args.shrinkage_games, 'screened_pairs': [asdict(p) for p in screened],
                    'interpretation': 'optimizer output; not a validated historical backtest'}
        write_lineups(lineups, output, args.stacking, metadata)
    except (ValueError, OSError, pulp.PulpSolverError) as error:
        parser.error(str(error))
    print(f'Wrote {len(lineups)} {args.stacking} lineup(s) to {output}')


if __name__ == '__main__':
    main()
