# Project instructions

## Data stays local

- Never commit, push, upload, attach to issues or pull requests, or include in
  releases any paid datasets, source responses, projections, salaries, boxscores,
  contest exports, provider metadata, credentials, or copies of those materials.
- Keep local inputs under `data/` and generated data/results under `outputs/`.
  Keep inspection reports and provenance under these ignored directories too.
- Do not publish data-derived tables, figures, trained artifacts, or notebook
  outputs without the user's separate explicit authorization.
- Use invented fixtures for public tests. Do not copy real records into code,
  documentation, tests, commit messages, or examples.
- Do not force-add ignored files, add a data Git LFS rule, or weaken these
  exclusions as a workaround. Inspect the exact staged files and diff before
  every commit and push. `.gitignore` does not protect already tracked files.
- Do not run provider downloads, quota-consuming jobs, or account changes as
  part of setup. Existing locally authorized files can be read directly.

## Research scope

- The initial NBA baseline uses supplied projected fantasy points unchanged.
- A later experiment may replace the provider's minutes estimate with our own,
  keeping the lineup optimizer and evaluation sample fixed for comparison.
- The NBA project is separate from the sibling NHL project; keep NHL intact.
- Distinguish prediction accuracy, lineup scores/ranks, and contest returns.
- Treat projection timestamps and training cutoffs as evidence to audit, not
  proof that a historical forecast was available at lineup submission time.
- Never use future observations, postgame fields, or realized availability to
  make historical lineup decisions. Missing observations are not automatic zeros.
- Preserve applicable attribution and license notices when reusing NHL code.

## Code and explanations

- Use snake_case for functions and variables and UPPERCASE for constants.
- Organize complete scripts into concise helper functions and one main function.
- Do not delete variables to save memory unless specifically requested.
- Display mathematical formulas using LaTeX.
