# Fantasy NBA Python

Local NBA daily fantasy research using unchanged provider fantasy-point forecasts
and sequential integer programming with PuLP/CBC. The baseline and all five
stacking types are implemented. Paid data is not included or uploaded.

## Strategies

All stacks specify **minimum cores**: additional players from the same teams or
game are allowed within the roster rules. The optimizer chooses the core and
fills the remaining slots to maximize the same projected-points objective.
Configurations can produce identical lineups when the baseline naturally stacks.

| Configuration | Required core | Intuition |
|---|---|---|
| `baseline` | No forced stacking | Establish the highest-projection legal lineup; natural stacks are allowed. |
| `type_1` | At least one player from each side of one game | Test shared game conditions with only two committed roster spots. |
| `type_2` | At least one screened teammate pair | Select teammates whose historical forecast errors provide evidence of positive association. |
| `type_3` | At least two players from one team and one from its opponent | Concentrate three roster spots in a potentially favorable game. |
| `type_4` | A screened teammate pair plus at least one opponent in that same game | Test whether empirical pair screening improves the generic three-player stack. |
| `type_5` | At least two players from each side of one game | Test whether greater game concentration compensates for reduced lineup flexibility. |

Types 2 and 4 use empirical pair screening, not a blanket point-guard/center rule.
Complementary basketball roles motivate the idea, but the current implementation
does not infer passing relationships or label creator/finisher roles.

The objective for every configuration is

\[
\max \sum_i \widehat{\mu}_i x_i,
\]

where the supplied fantasy-point forecast is unchanged. Explicit slot assignment
prevents multi-position players from occupying more than one slot. Salary limits,
team limits, minimum team count, and the chosen stack are enforced. Further
lineups are solved sequentially, with a player-overlap cap against **each** earlier
lineup. A roster assigned to different slots still counts as the same player set.
This is greedy sequential optimization, not joint portfolio optimization or direct
maximization of tournament win probability. Correlation does not itself increase
expected points, and forcing a stack may lower the projected lineup total.

## Setup and invented demonstration

Requires Python 3.11 or later. Create the environment inside this NBA checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest -v
.venv/bin/python synthetic_demo.py
```

The demo creates a fresh ignored `outputs/synthetic_demo_*/` directory with
invented players, invented history, explicit rules, and three lineups for each of
the six configurations. It exercises the real command line and CBC solver.
It does not read paid inputs, enter contests, or measure historical performance.

## Contest rules are explicit

The CLI requires a JSON rule file. The demo uses the traditional nine-slot
FanDuel classic structure shown below; **verify the actual contest and period**
before using this configuration on historical or current inputs.

```json
{
  "salary_cap": 60000,
  "slots": ["PG1", "PG2", "SG1", "SG2", "SF1", "SF2", "PF1", "PF2", "C"],
  "max_players_per_team": 4,
  "min_teams": 3
}
```

Slot names must be unique. Supported slot bases are `PG`, `SG`, `SF`, `PF`, `C`,
`G`, `F`, `G/F`, `F/C`, and `UTIL`; numeric suffixes distinguish repeated slots.
Player eligibility always uses the five base positions. Flexible slots are
supported so an explicit contest configuration can be represented; no roster
format or historical rule change is inferred from a date.

[FanDuel's official rules](https://www.fanduel.com/rules) describe team limits,
scoring, and contest-dependent lock rules. Those current rules do not establish
that a historical contest used a particular configuration. The optimizer sums
already-projected fantasy points; it does not implement scoring multipliers,
drop-lowest scoring, late swap, postseason-specific behavior, or payout rules.
The initial research scope remains regular-season classic contests.

## Local input interface

The interface is normalized CSV plus explicit rule JSON. It is **not an automatic
adapter for the paid archive**. Prepare authorized local inputs under `data/`,
checking stable identifiers, operator-specific eligibility/scoring, complete player
coverage, and historical provenance. Never silently drop unmatched players.

Player CSV requires exactly these columns (order is flexible):

```csv
player_id,name,team,opponent,game_id,positions,salary,projected_points,projection_time,game_time
```

- IDs are text, including numeric-looking IDs with leading zeros.
- Positions use slash-separated base positions, such as `PG/SG`.
- Salary is a positive integer; projected points must be finite and are not adjusted.
- One file describes one slate: a team has one opponent/game, and player IDs are unique.
- Times use ISO 8601 with an explicit timezone, such as `2025-02-01T19:00:00Z`.
- Every forecast must be at or before `--cutoff`, and every game must start after
  that cutoff. One late forecast rejects the entire input pool; it is not dropped.

Example baseline command, after preparing the normalized files:

```bash
.venv/bin/python nba_optimizer.py \
  --players data/players.csv \
  --rules data/rules.json \
  --cutoff 2025-02-01T19:00:00Z \
  --stacking baseline \
  --num-lineups 10 \
  --max-overlap 7 \
  --output outputs/baseline.csv
```

Replace `baseline` with any of the five named types. Types 2 and 4 additionally
require `--history data/history.csv`. No eligible pair is an explicit error;
the program never substitutes an arbitrary pair or relaxes the stack.

The default is one lineup, with maximum overlap one below the roster size.
CBC gets 60 seconds per solve by default (`--time-limit`). Only a proven optimal
solution is accepted. Infeasibility or an unproven solution stops the request;
no partial lineup CSV is exported. CBC model/solution scratch files also stay
under ignored `outputs/` and are cleaned up on ordinary success or exceptions
(an abrupt process kill may leave an ignored scratch directory). Export is atomic, stays under ignored
`outputs/`, and refuses to overwrite an existing file. Use a new filename per run.
The CSV is a **research export**, not a FanDuel upload template. It contains slot
assignments, total salary/projection, and run settings including the screened
pairs. Those outputs remain local.

## Historical pair screening

History CSV requires exactly:

```csv
player_id,team,game_id,game_time,projection_time,decision_time,observed_at,projected_points,actual_points
```

`decision_time` is the historical pre-slate cutoff for that forecast, not today's
cutoff. `observed_at` is when the result became available; do not invent an earlier
timestamp from the game's start. Each historical player/game occurs once.
Forecasts must satisfy

\[
\text{projection_time} \leq \text{decision_time}
< \text{game_time} < \text{observed_at}.
\]

Only games before the current cutoff whose results were available by that cutoff
are used. Future observations remain excluded even when present in the file.
For each current teammate pair, historical records must also belong to their
current team. Shared game IDs align the observations. Define

\[
e_{i,t}=y_{i,t}-\widehat{\mu}_{i,t}, \qquad
r_{ij}^{\mathrm{shrunk}}=\frac{n_{ij}}{n_{ij}+k}
\operatorname{Corr}(e_{i,t},e_{j,t}).
\]

Default screening requires 20 shared games, uses shrinkage strength 20, and keeps
pairs with shrunk correlation at least 0.10. These are **untuned research defaults**,
not statistically established profitability thresholds. Configure them with
`--min-shared-games`, `--shrinkage-games`, and `--min-correlation`. Constant residuals
have undefined correlation and are excluded. Choose thresholds using earlier
training/validation periods, never the held-out evaluation results. Shrinkage
reduces small-sample enthusiasm; it is not a significance test or proof of joint
upper-tail performance. Trades, role changes, and multiple comparisons remain
research limitations. The low-level Python API also accepts an explicitly
prequalified pair list; callers own its provenance and timing.

Timestamp checks are necessary but cannot establish that the player universe was
complete, the source was genuinely available then, or provider training excluded
future information. A run passing them is still an optimizer run, **not a validated
historical backtest**. See the [baseline design](docs/superpowers/specs/2026-11-08-nba-provider-baseline-design.md).

## Validation and research results

The current automated suite has 14 tests and uses invented fixtures only. It checks all six configurations
against exhaustive enumeration, binding stacking examples, multi-position and
flexible-slot assignment, sequential overlap, infeasibility, timestamp leakage,
pair screening, protected exports, solver-failure cleanup, and an end-to-end CLI demonstration.
These checks establish implementation behavior on tested cases, not profitability.

| Research stage | Status |
|---|---|
| Baseline and five stacking types | Implemented; synthetic correctness checks included |
| Historical lineup score comparison | Local timing-screened pilot completed for runnable configurations; full six-way comparison remains blocked |
| Historical contest ranks and returns | Preliminary local cash-cutoff and limited rank checks completed; exact portfolio returns remain blocked by incomplete standings, payout schedules, and settled-score coverage |
| Provider forecasts versus our own minutes adjustment | Deferred |
| Additional compatible stacking combinations | Deferred |

The local historical pilot found limited pre-lock forecast coverage and too little
time-admissible history for the screened-pair types. It therefore does not establish
a winning stacking strategy or profitability. Detailed timing audits, selected
lineups, scores, and reproducibility scripts remain under the ignored
`outputs/historical_comparison_*/` directories, with a local `REPORT.txt` summary.
Follow-up contest checks have their own local report. Crossing a reported cash
cutoff is a provisional score comparison, not a confirmed payout or positive return.
Source records and detailed results are not published in this README.

Later, add a concise tested-results summary here: evaluation dates and number of
slates, rule/scoring version, forecast cutoff/provenance, fixed entry count and
overlap, screening settings, held-out design, projection cost, lineup metrics,
and uncertainty. Returns additionally require complete contest fields, entry
fees, payouts, ties, and entry limits. Keep prediction accuracy, lineup scores,
and contest returns distinct. Do not infer returns from a winner-only sample.
Raw inputs, detailed results, and paid-data-derived artifacts remain local;
publish only an explicitly authorized aggregate summary without source records.

## Files and future work

- `nba_models.py`: player/rule/lineup records and validation.
- `nba_stacking.py`: game-core and screened-pair constraint helpers.
- `nba_optimizer.py`: model, sequential solver, and command line.
- `nba_screening.py`: past-only residual screening.
- `nba_io.py`: normalized local inputs and protected exports.
- `synthetic_demo.py`: fully invented end-to-end example.
- `test_nba_optimizer.py`: independent oracle and regression tests.

The constraint helpers separate game cores and pair requirements so compatible
combinations can be added later. This release exposes only the six agreed
configurations, without searching or automatically combining additional rules.

## Data boundaries and attribution

Keep authorized inputs under ignored `data/` and generated artifacts under
ignored `outputs/`. Do not upload paid inputs, provider metadata, or their copies
through Git, releases, issues, or pull requests. Public examples and tests use
invented data. The allowlist `.gitignore` is unchanged; review staged content
before publishing because ignore rules do not protect data embedded in source.
The sibling NHL project is separate and unchanged.

The NBA implementation is newly written and takes methodological inspiration from
Hunter, Vielma, and Zaman,
[*Picking Winners in Daily Fantasy Sports Using Integer Programming*](https://arxiv.org/abs/1604.01455v3).
No NHL implementation code is copied. Any future reuse of the NHL/MPL-2.0 source
must preserve its applicable attribution and license notices.

Stacking motivation also draws on
[FantasyLabs' player-correlation analysis](https://www.fantasylabs.com/articles/daily-fantasy-nba-player-correlations/),
[Establish The Run's selective game-stacking discussion](https://establishtherun.com/game-stacking-in-nba-dfs/),
and [Alex Baker's caution about forcing NBA stacks](https://www.stokastic.com/articles/nba-dfs/nba-dfs-strategy-guide).
These sources motivate hypotheses, not a claim that our configurations have
historically profitable returns.
