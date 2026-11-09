# NBA baseline and stacking implementation plan

> **For agentic workers:** Use superpowers:executing-plans. Execute inline; user has approved implementation.

**Goal:** Implement the provider-forecast baseline and five agreed stacking types, with local-only inputs and outputs.

**Architecture:** Separate validated player/rule records, historical pair screening, linear stacking constraints, and solver/CLI helpers. Require explicit contest rules instead of assuming one roster format applies to every season. All stacks are minimum cores, not exclusive lineup shapes.

**Tech Stack:** Python 3.11+, PuLP 3.3.0/CBC, standard-library CSV/JSON/unittest.

**Spec:** Prior baseline design plus the user's approved six configurations in this chat. This plan supersedes the earlier deferral of NBA stacking, not its data or timing requirements.

## Global constraints

- Paid inputs stay under ignored data/; generated artifacts stay under ignored outputs/.
- NHL remains untouched. Write NBA code independently; retain research attribution.
- Provider fantasy-point forecasts remain unchanged. No trained minutes model, backtest, payout analysis, or strategy-combination search in this change.
- snake_case functions/variables, UPPERCASE constants, helper functions and main for executable scripts.
- Baseline allows natural stacks. Types 1/3/5 require 1+1/2+1/2+2 within one game. Type 2 requires a screened teammate pair. Type 4 requires that pair and its opponent in the SAME game.
- Reject invalid pools, nonfinite numbers, duplicate player IDs, ambiguous games, late forecasts, unsupported rules, and infeasible requests explicitly. Never silently drop players or relax constraints.

## Review focus

- Multi-position players must occupy exactly one eligible slot.
- Type 4 must not combine a screened pair with an unrelated game stack.
- Pair screening must exclude future games/results, reject late historical forecasts, and handle constant residuals and small samples.
- Sequential overlap applies against every previous lineup, including equal player sets assigned to different slots.
- CSV and CLI failures must not overwrite inputs or leave apparently complete partial exports.

## Task 1: Core optimizer

Files: nba_models.py, nba_stacking.py, nba_optimizer.py, test_nba_optimizer.py, requirements.txt.
Interface: Player, ContestRules, Lineup; generate_lineups(players, rules, stacking, screened_pairs, num_lineups, max_overlap).
- [x] Write failing synthetic enumeration/slot/stack/overlap/invalid-input tests.
- [x] Implement binary slot assignment, salary/team limits, six stacking configurations, and sequential optimal solves.
- [x] Run all unittest tests; compare against exhaustive enumeration using an independent predicate.

## Task 2: Local inputs, screening, and command line

Files: nba_io.py, nba_screening.py, nba_optimizer.py, synthetic_demo.py, test_nba_optimizer.py.
Interface: read_players, read_rules, read_history, screen_pairs, write_lineups; CLI uses normalized local CSV and explicit JSON rules.
- [x] Write failing temporal leakage, residual-correlation, CSV validation, and CLI tests.
- [x] Implement training-only residual screening with minimum sample and shrinkage; expose tunable unvalidated thresholds.
- [x] Implement local CSV/JSON CLI and an invented end-to-end demo for all six configurations.
- [x] Run full suite and synthetic demo, inspect exports.

## Task 3: Documentation and final review

Files: README.md, baseline design, this plan.
- [x] Document exact strategy semantics/intuition, rules, input schemas, commands, limitations, and current correctness checks.
- [x] Reserve a results section for later experiments; no invented historical performance.
- [x] Obtain independent whole-change code review, fix material findings, run final suite.
- [x] Verify ignored data/output paths and unchanged NHL hashes. Review exact Git diff; leave changes on a local feature branch without uploading data.

## Execution notes

- Native managed-worktree creation did not return; continued on dedicated codex/nba-stacking branch in the existing clean NBA checkout. No NHL changes or data copies are required.
- Normalized local CSV is an explicit interface, not an automatic adapter for the paid archive. Timestamps are necessary checks, not proof of provider training provenance or a complete historical player universe.


## Completion evidence

- Full `python -m unittest -v`: 14 passing tests. All six configurations match an independent exhaustive oracle; an additional constructed pool makes each rule binding.
- End-to-end invented demo: three lineups per configuration, 18 exported lineups independently checked for slots, uniqueness, team/salary rules, stack cores, totals, and pairwise overlap.
- Independent read-only review found one material issue: CBC scratch files defaulted outside outputs/. Reproduced with an interrupted solver, fixed with an outputs-local temporary-directory context, and verified RED-to-GREEN plus the full suite.
- NHL HEAD, clean status, and all 11 tracked-file hashes match the pre-work snapshot.
- No historical paid-data run or profitability claim. Normalized CSV adapter boundary and empirical (not role-labeled) pair screening are documented.
- Local feature branch retained; no remote upload is part of this implementation.
