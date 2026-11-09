# Fantasy NBA Python

NBA daily fantasy research using supplied player forecasts and integer programming.

## Research direction

The first baseline will use the provider's projected fantasy points unchanged.
It will construct legal NBA lineups and, for multiple entries, restrict player
overlap with previously selected lineups. The proposed initial scope is FanDuel
classic contests during the regular season.

A later experiment will compare that baseline with forecasts adjusted using our
own estimate of playing time. Both methods will use the same optimizer, eligible
sample, information cutoff, and entry count so that the projection change can be
evaluated separately.

See the [baseline design](docs/superpowers/specs/2026-11-08-nba-provider-baseline-design.md)
for the proposed first implementation and remaining timing questions.

## Status

Repository setup and research design only. No NBA optimizer or validated
historical backtest has been implemented, and no profitability is claimed.

## Local data

Paid source data is not distributed with this repository. Obtain authorized
inputs independently and keep them under the ignored `data/` directory.
Generated lineups, analysis outputs, reports, and private provenance also stay
local. Do not upload these materials through Git, releases, issues, pull requests,
or other public artifacts. Public examples and tests must use invented data.

The `.gitignore` uses an allowlist for source and documentation and excludes local
data/results directories. Review staged content before committing; ignore rules
alone do not prevent intentional force-adds or data embedded inside source files.

## Research reference

Hunter, Vielma, and Zaman,
[*Picking Winners in Daily Fantasy Sports Using Integer Programming*](https://arxiv.org/abs/1604.01455v3).
The NBA project will adapt the sequential lineup construction idea. NBA rules
must be implemented separately, and hockey stacking constraints are not assumed
to apply. Reused implementation code must retain its applicable license notices.
