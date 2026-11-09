# NBA provider-forecast baseline

Date: November 8, 2026

Status: Initial design retained for research context. The baseline and five NBA
stacking types were subsequently authorized and implemented; see README.md and
../plans/2026-11-09-nba-stacking.md for current interfaces and scope. No validated
historical backtest or profitability result is claimed.

## Intent and agreed approach

Build an NBA daily fantasy research project separate from the existing NHL
project. Start with supplied projected fantasy points. Later compare those
forecasts with estimates adjusted using our own predicted minutes.

Paid inputs, provider metadata, derived outputs, and credentials remain local.
Public code and documentation must not reproduce those materials.

## Approaches considered

1. Use supplied fantasy-point forecasts unchanged. Selected for the initial
   baseline: it keeps the first experiment focused on lineup construction.
2. Retain a provider-implied production rate and replace projected minutes with
   our own estimates. Selected as a later comparison, after the baseline works.
3. Estimate both production and minutes from historical game logs. Deferred
   because it introduces a broader forecasting project before establishing the
   optimizer baseline.

## Proposed first implementation

- Python with PuLP and CBC, following the existing NHL modeling approach.
- FanDuel classic regular-season contests initially. Verify the historical
  salary cap, roster slots, eligibility, team limits, scoring, and lock rules for
  the evaluation period before implementing them. Single-game, preseason, and
  late-swap strategies are outside the initial scope.
- Build one lineup by maximizing the sum of supplied expected fantasy points,
  subject to the verified salary and roster constraints. Assign eligible players
  to explicit roster slots so multi-position eligibility cannot double-count a
  player. Each player can occupy at most one slot.
- Generate additional lineups sequentially, constraining player overlap with
  every previous lineup. Keep entry count and overlap cap explicit configuration
  choices; do not claim they are tuned or optimal without evaluation.
- Original baseline proposal: begin without forced stacking. Subsequently, add
  the five explicitly approved NBA configurations as experimental variants;
  retain no-forced-stacking as the control. Hockey stacking is not transplanted.
- Keep input validation, model construction, solving, and export in concise
  helper functions, connected by one main function.
- Use stable player identifiers as text, explicit missing values, and timezone-
  aware timestamps. Reject unsupported formats and ambiguous joins.

These implementation choices are proposals rather than additional user decisions.

## Historical information cutoff

The baseline should represent decisions made before the slate's initial start.
Provider forecasts must be available by that cutoff, with their source timestamp
and historical model provenance assessed. Per-game updates after slate start do
not establish that the same values were known when the initial lineup was chosen.

Do not silently discard late-updated players and optimize the reduced pool: that
changes the decision universe and can bias the evaluation. Prefer an earlier
snapshot of the complete relevant pool. Otherwise exclude the affected slate
from a historical performance claim, or label an optimizer run as a demonstration
using supplied inputs rather than a valid pre-slate backtest.

An earlier timestamp by itself does not prove that the provider's training data
or historical reconstruction excluded future information. Record unresolved
provenance locally. Do not use outcomes to choose which forecasts are admissible.

## Evaluation

1. Verify the optimizer with invented small player pools, including exhaustive
   enumeration, legal slot assignment, salary limits, and sequential overlap.
2. Evaluate lineup scores/ranks only on a clearly defined, time-valid sample.
   Distinguish reconstructed scores from operator-settled scores; investigate
   discrepancies, missing boxscores, and nonappearances explicitly.
3. Evaluate contest returns only where full field, entry fee, payout, and tie
   information support the calculation. Preserve contest entry limits and a
   declared total entry budget. Do not generalize a small selected sample into
   a profitability claim.
4. For the later minutes experiment, use the same dates, players, optimizer
   settings, and entry budget for both projection methods. Report minutes and
   fantasy-point error separately from lineup and return metrics.

## Deferred minutes model

For positive, compatible provider minute estimates, a possible adjustment is

\[
\widehat{f}_{\mathrm{adjusted}}
=\frac{\widehat{f}_{\mathrm{provider}}}
{\widehat{m}_{\mathrm{provider}}}
\widehat{m}_{\mathrm{ours}}.
\]

The ratio is an implied rate, not necessarily a provider's separately estimated
production parameter. Check conditional versus unconditional minutes, play
probability, and changes in productivity with role. Define a policy for zero or
missing minute forecasts before comparison. Fit our estimates using only
information available before each prediction cutoff.

## Remaining decisions before implementation

- Verify historical contest rules and identify a suitable evaluation period.
- Determine whether complete forecasts exist before the chosen cutoff; if not,
  separate the optimizer demonstration from any historical evaluation.
- Choose an initial entry count and overlap cap for the baseline, then specify
  a held-out comparison if studying diversification.

## Acceptance criteria

- No paid data or derived results are tracked or uploaded.
- NHL files and repository history remain unchanged.
- The baseline uses supplied projected points without minutes adjustments.
- NBA rules and input semantics are explicit and tested on invented data.
- Historical results are reported only with an appropriate information cutoff
  and clearly separated prediction, lineup, and return metrics.
