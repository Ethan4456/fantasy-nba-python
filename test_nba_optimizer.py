"""Invented fixtures and an independent exhaustive oracle; no paid records."""
import importlib.util
import itertools
import unittest
from collections import Counter

AVAILABLE = importlib.util.find_spec('nba_optimizer') is not None
if AVAILABLE:
    from nba_models import ContestRules, Player
    from nba_optimizer import generate_lineups


def make_pool():
    # Deliberately flexible positions exercise slot assignment without duplication.
    return [Player(str(i), f'Invented {i}', team, opp, game,
                   frozenset(pos.split('/')), 4500 + (i % 4) * 500, 20 + (i * 13) % 29)
            for i, (team, opp, game, pos) in enumerate([
                ('A','B','AB','PG'), ('A','B','AB','SG/SF'), ('A','B','AB','PF'),
                ('A','B','AB','C'), ('B','A','AB','PG/SG'), ('B','A','AB','SF'),
                ('B','A','AB','PF/C'), ('C','D','CD','PG'), ('C','D','CD','SG'),
                ('C','D','CD','SF/PF'), ('D','C','CD','PG/SG'), ('D','C','CD','SF'),
                ('D','C','CD','PF'), ('D','C','CD','C')])]


def can_assign(players, slots):
    if not slots:
        return True
    position = slots[0]
    return any(position in player.positions and
               can_assign(players[:i] + players[i+1:], slots[1:])
               for i, player in enumerate(players))


def core_holds(players, stacking, pairs):
    ids = {p.player_id for p in players}
    by_team = Counter(p.team for p in players)
    selected_pairs = [(a,b) for a,b in pairs if a in ids and b in ids]
    if stacking == 'baseline':
        return True
    if stacking == 'type_2':
        return bool(selected_pairs)
    if stacking == 'type_4':
        return any(any(q.team == p.opponent and q.game_id == p.game_id for q in players)
                   for p in players if any(p.player_id == a for a,b in selected_pairs))
    sizes = {'type_1':(1,1), 'type_3':(2,1), 'type_5':(2,2)}[stacking]
    return any(by_team[p.team] >= sizes[0] and by_team[p.opponent] >= sizes[1]
               for p in players)


def exhaustive_best(pool, stacking, pairs, previous=(), overlap=8):
    best = None
    for group in itertools.combinations(pool, 9):
        ids = {p.player_id for p in group}
        counts = Counter(p.team for p in group)
        if sum(p.salary for p in group) > 48000 or max(counts.values()) > 4 or len(counts) < 3:
            continue
        if any(len(ids & old) > overlap for old in previous):
            continue
        if not core_holds(group, stacking, pairs):
            continue
        if not can_assign(list(group), ('PG','PG','SG','SG','SF','SF','PF','PF','C')):
            continue
        score = sum(p.projected_points for p in group)
        best = score if best is None else max(best, score)
    return best


class OptimizerTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(AVAILABLE, 'NBA optimizer has not been implemented')
        self.pool = make_pool()
        self.rules = ContestRules(salary_cap=48000)
        self.pairs = [('0','1'), ('7','9')]

    def test_all_six_types_match_exhaustive_optimum(self):
        for stacking in ('baseline','type_1','type_2','type_3','type_4','type_5'):
            with self.subTest(stacking=stacking):
                result = generate_lineups(self.pool, self.rules, stacking=stacking,
                                          screened_pairs=self.pairs)[0]
                self.assertAlmostEqual(result.projected_points,
                                       exhaustive_best(self.pool, stacking, self.pairs))
                self.assertEqual(len(set(result.player_ids)), 9)
                self.assertTrue(core_holds(list(result.players), stacking, self.pairs))
                for slot, player in result.assignments:
                    self.assertIn(slot.rstrip('0123456789'), player.positions)

    def test_sequential_overlap_checks_every_previous_lineup(self):
        results = generate_lineups(self.pool, self.rules, stacking='type_4',
                                   screened_pairs=self.pairs, num_lineups=3, max_overlap=7)
        previous = []
        for result in results:
            self.assertAlmostEqual(result.projected_points,
                                   exhaustive_best(self.pool, 'type_4', self.pairs, previous, 7))
            ids = set(result.player_ids)
            self.assertTrue(all(len(ids & old) <= 7 for old in previous))
            previous.append(ids)

    def test_bad_pools_and_parameters_are_rejected(self):
        from dataclasses import replace
        for mutation in (replace(self.pool[0], salary=-1),
                         replace(self.pool[0], projected_points=float('nan')),
                         replace(self.pool[0], positions=frozenset({'G'})),
                         replace(self.pool[0], opponent='C')):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                generate_lineups([mutation]+self.pool[1:], self.rules)
        with self.assertRaises(ValueError):
            generate_lineups(self.pool+[self.pool[0]], self.rules)
        for kwargs in ({'stacking':'unknown'}, {'num_lineups':0}, {'max_overlap':9},
                       {'num_lineups':True}, {'stacking':'type_2'},
                       {'stacking':'type_4','screened_pairs':[('0','7')]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                generate_lineups(self.pool, self.rules, **kwargs)

    def test_infeasible_request_never_returns_partial_lineups(self):
        with self.assertRaisesRegex(ValueError, 'lineup 2'):
            generate_lineups(self.pool, self.rules, num_lineups=2, max_overlap=0)
        with self.assertRaisesRegex(ValueError, 'lineup 1'):
            generate_lineups(self.pool, ContestRules(salary_cap=1))

    def test_type_4_requires_opponent_of_the_screened_pair(self):
        # Nine players can form unrelated AB stacks; the sole approved CD pair
        # has no D player. Type 2 succeeds, but Type 4 must be infeasible.
        from dataclasses import replace
        pool = [replace(p, team='E', opponent='F', game_id='EF') if p.team=='D'
                else replace(p, opponent='Z', game_id='CZ') if p.team=='C' else p
                for p in self.pool]
        self.assertTrue(generate_lineups(pool, self.rules, stacking='type_2',
                                        screened_pairs=[('7','9')]))
        with self.assertRaises(ValueError):
            generate_lineups(pool, self.rules, stacking='type_4', screened_pairs=[('7','9')])


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('nba_screening'), 'Pair screening is not implemented')

    def test_screening_uses_residuals_and_only_past_available_results(self):
        from datetime import datetime, timedelta, timezone
        from nba_screening import HistoryRow, screen_pairs
        cutoff = datetime(2025, 2, 1, tzinfo=timezone.utc)
        history = []
        for day, error in enumerate((-3., -1., 1., 3.)):
            game_time = cutoff - timedelta(days=10-day)
            for player_id, residual in (('0', error), ('1', 2*error), ('2', -error)):
                history.append(HistoryRow(player_id, 'A', f'old_{day}', game_time,
                                          game_time-timedelta(hours=2), game_time-timedelta(hours=1),
                                          game_time+timedelta(hours=3), 30., 30.+residual))
        pairs = screen_pairs(make_pool(), history, cutoff, min_games=4, min_correlation=.4, shrinkage=4)
        self.assertEqual([(p.first_id,p.second_id,p.shared_games) for p in pairs], [('0','1',4)])
        self.assertAlmostEqual(pairs[0].correlation, 1.)
        self.assertAlmostEqual(pairs[0].shrunk_correlation, .5)
        from dataclasses import replace
        future = [replace(row, game_id='future', game_time=cutoff+timedelta(days=1),
                          decision_time=cutoff, projection_time=cutoff,
                          observed_at=cutoff+timedelta(days=2)) for row in history[:3]]
        self.assertEqual(screen_pairs(make_pool(), history+future, cutoff, min_games=4,
                                      min_correlation=.4, shrinkage=4), pairs)
        late_result = [replace(row, observed_at=cutoff+timedelta(days=1)) for row in history]
        self.assertEqual(screen_pairs(make_pool(), late_result, cutoff, min_games=4), [])
        constant = [replace(row, actual_points=row.projected_points) for row in history]
        self.assertEqual(screen_pairs(make_pool(), constant, cutoff, min_games=4), [])
        late_forecast = [replace(history[0], projection_time=history[0].game_time)] + history[1:]
        with self.assertRaises(ValueError):
            screen_pairs(make_pool(), late_forecast, cutoff, min_games=4)
        with self.assertRaises(ValueError):
            screen_pairs(make_pool(), history+[history[0]], cutoff, min_games=4)


class InputOutputTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('nba_io'), 'Local IO is not implemented')

    def write_pool(self, path):
        import csv
        columns = ['player_id','name','team','opponent','game_id','positions','salary',
                   'projected_points','projection_time','game_time']
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for p in make_pool():
                writer.writerow(dict(player_id=p.player_id,name=p.name,team=p.team,
                                     opponent=p.opponent,game_id=p.game_id,positions='/'.join(sorted(p.positions)),
                                     salary=p.salary,projected_points=p.projected_points,
                                     projection_time='2025-02-01T17:00:00Z', game_time='2025-02-01T20:00:00Z'))

    def test_csv_reader_rejects_late_forecast_instead_of_dropping_player(self):
        import tempfile
        from pathlib import Path
        from nba_io import read_players, parse_time
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'players.csv'
            self.write_pool(path)
            cutoff = parse_time('2025-02-01T19:00:00Z')
            self.assertEqual(read_players(path, cutoff), make_pool())
            path.write_text(path.read_text().replace('17:00:00Z','19:30:00Z',1))
            with self.assertRaisesRegex(ValueError, 'cutoff'):
                read_players(path, cutoff)
            with self.assertRaises(ValueError):
                parse_time('2025-02-01T19:00:00')

    def test_cli_exports_all_six_on_synthetic_data(self):
        import subprocess
        from pathlib import Path
        demo = Path(__file__).with_name('synthetic_demo.py')
        self.assertTrue(demo.exists(), 'Synthetic demo is not implemented')
        result = subprocess.run([__import__('sys').executable,str(demo)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('6 configurations', result.stdout)

    def test_output_cannot_overwrite_inputs_or_existing_files(self):
        import tempfile
        from pathlib import Path
        from nba_io import write_lineups
        lineup = generate_lineups(make_pool(), ContestRules(salary_cap=48000))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                write_lineups(lineup, Path(directory)/'source.csv', 'baseline')
        root = Path(__file__).parent/'outputs'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = Path(directory)/'lineups.csv'
            write_lineups(lineup, path, 'baseline')
            old = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_lineups(lineup, path, 'baseline')
            self.assertEqual(path.read_bytes(), old)


class ConstraintBoundaryTests(unittest.TestCase):
    def test_each_stack_changes_the_unconstrained_solution(self):
        pool = []
        for i, (team, opponent) in enumerate((('A','B'),('C','D'),('E','F'),('G','H'))):
            for suffix, side, other, score in (('star',team,opponent,100-i),
                                               ('mate',team,opponent,60-i),
                                               ('opp',opponent,team,55-i),
                                               ('opp2',opponent,team,50-i)):
                pool.append(Player(team+suffix, team+suffix, side, other, team+opponent,
                                   frozenset({'PG'}), 5000, score))
        rules = ContestRules(30000, ('UTIL1','UTIL2','UTIL3','UTIL4'), 4, 1)
        expected = {'baseline':394, 'type_1':352, 'type_2':355,
                    'type_3':314, 'type_4':309, 'type_5':265}
        for stacking, score in expected.items():
            with self.subTest(stacking=stacking):
                result = generate_lineups(pool, rules, stacking=stacking,
                                          screened_pairs=[('Estar','Emate')])[0]
                self.assertEqual(result.projected_points, score)

    def test_flexible_slots_do_not_allow_reusing_a_player(self):
        pool = [Player('one','One','A','B','AB',frozenset({'PG','SG'}),5000,100),
                Player('two','Two','B','A','AB',frozenset({'C'}),5000,30),
                Player('three','Three','C','D','CD',frozenset({'SG'}),5000,10)]
        rules = ContestRules(20000, ('G/F','F/C','UTIL'), 2, 3)
        result = generate_lineups(pool, rules)[0]
        self.assertEqual(result.projected_points, 140)
        self.assertEqual(set(result.player_ids), {'one','two','three'})

    def test_malformed_rules_fail_with_actionable_value_error(self):
        for slots in ([['PG']], ['PG','PG'], [], 'PG'):
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                generate_lineups(make_pool(), ContestRules(slots=slots))


class FinalRegressionTests(unittest.TestCase):
    def test_correlated_raw_scores_do_not_qualify_opposite_forecast_errors(self):
        from datetime import datetime, timedelta, timezone
        from nba_screening import HistoryRow, screen_pairs
        cutoff = datetime(2025, 2, 1, tzinfo=timezone.utc)
        history = []
        for day, error in enumerate((-3., -1., 1., 3.)):
            game_time = cutoff - timedelta(days=10-day)
            forecast = 20 + 100*day
            for player_id, residual in (('0', error), ('1', -error)):
                history.append(HistoryRow(player_id,'A',f'old_{day}',game_time,
                                          game_time-timedelta(hours=2),game_time-timedelta(hours=1),
                                          game_time+timedelta(hours=3),forecast,forecast+residual))
        self.assertEqual(screen_pairs(make_pool(), history, cutoff, min_games=4), [])

    def test_solver_failure_cleans_private_scratch_inside_outputs(self):
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        import pulp
        written = []
        original_solver = pulp.PULP_CBC_CMD

        class InterruptedSolver(original_solver):
            def actualSolve(self, model, **kwargs):
                with tempfile.NamedTemporaryFile(dir=self.tmpDir, suffix='.mps', delete=False) as stream:
                    path = Path(stream.name)
                written.append(path)
                model.writeMPS(str(path))
                raise pulp.PulpSolverError('Invented interruption after writing the model')

        try:
            with patch('nba_optimizer.pulp.PULP_CBC_CMD', InterruptedSolver):
                with self.assertRaises(pulp.PulpSolverError):
                    generate_lineups(make_pool(), ContestRules(salary_cap=48000))
            self.assertEqual(len(written), 1)
            self.assertTrue(written[0].is_relative_to(Path(__file__).parent/'outputs'))
            self.assertFalse(written[0].exists(), 'Failure left model coefficients on disk')
        finally:
            for path in written:
                path.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
