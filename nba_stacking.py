"""Linear constraints for the five minimum-core stacking configurations."""
from collections import defaultdict
import pulp


def add_game_stack(model, players, selected, sizes):
    team_indices = defaultdict(list)
    for index, player in enumerate(players):
        team_indices[player.team].append(index)
    witnesses = []
    for team, indices in sorted(team_indices.items()):
        opponent = players[indices[0]].opponent
        opponent_indices = team_indices.get(opponent, [])
        if len(indices) < sizes[0] or len(opponent_indices) < sizes[1]:
            continue
        witness = pulp.LpVariable(f'game_core_{len(witnesses)}', cat='Binary')
        model += pulp.lpSum(selected[i] for i in indices) >= sizes[0] * witness
        model += pulp.lpSum(selected[i] for i in opponent_indices) >= sizes[1] * witness
        witnesses.append(witness)
    model += pulp.lpSum(witnesses) >= 1, 'require_game_core'


def add_pair_stack(model, players, selected, pairs, bring_back):
    by_id = {player.player_id: i for i, player in enumerate(players)}
    witnesses = []
    for first, second in pairs:
        first_index, second_index = by_id[first], by_id[second]
        witness = pulp.LpVariable(f'pair_core_{len(witnesses)}', cat='Binary')
        model += witness <= selected[first_index]
        model += witness <= selected[second_index]
        if bring_back:
            player = players[first_index]
            model += pulp.lpSum(selected[i] for i, other in enumerate(players)
                                if other.team == player.opponent and other.game_id == player.game_id) >= witness
        witnesses.append(witness)
    model += pulp.lpSum(witnesses) >= 1, 'require_pair_core'


def add_stacking_constraints(model, players, selected, stacking, screened_pairs):
    if stacking == 'baseline':
        return
    if stacking in ('type_2', 'type_4'):
        add_pair_stack(model, players, selected, screened_pairs, stacking == 'type_4')
    else:
        sizes = {'type_1': (1, 1), 'type_3': (2, 1), 'type_5': (2, 2)}[stacking]
        add_game_stack(model, players, selected, sizes)
