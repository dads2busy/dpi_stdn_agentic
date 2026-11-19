# Convergence threshold (tau) and round cap (R) sensitivity

Metric: per-technology median pairwise Jaccard of canonical component sets across runs (the submitted stability metric), median over technologies. Component sets are taken from debate transcripts and mapped through `data/component_canonical_vocab_sensitivity.json`. *Better/worse/tied* counts technologies against the single-agent v1v1v1 baseline. *Rounds* is the mean number of debate rounds used. *Unmapped* counts component names not in the vocabulary (kept verbatim). *Δ vs v1* is a difference of medians; *Δ vs replay* is the median of per-technology differences.

`data/component_canonical_vocab_sensitivity.json` is the revision vocabulary plus technology-scoped LLM mappings for names that appear only in replayed rounds (built with `--extend-vocab`: the submitted normalization's model and prompt, each technology given its own existing canonical names). Round-2 proposals of three-round debates never went through the pipeline's final LLM normalization; through the revision vocabulary alone the R=1 replay has 1854 unmapped names and a median of 0.155. Limitation: a real stop at round 2 would normalize names before counting agent support; the replay counts support on the recorded names and maps them afterwards.

## A. Submitted microelectronics runs (d3v1v1, 60 technologies, 5 runs), replayed

Replays apply the pipeline's consensus rule (`build_adaptive_consensus_semantic` plus the confidence filter in `run_debate`) to the proposals of the round where the debate would have stopped. The replay at the actual stop reproduces the recorded final consensus exactly for every run. Round-1 proposals carry no agent id, so a debate that stops after round 1 pools them under one agent: consensus then needs support from one agent, not two of three, and keeps every proposal with confidence >= 0.7. 55 of the 293 submitted debates stopped after round 1.

| scenario | techs | median Jaccard | Δ vs v1 | better/worse/tied vs v1 | Δ vs replay (median of per-tech diffs) | rounds | unmapped |
|---|---|---|---|---|---|---|---|
| Recorded final (tau=0.7, R=3, as submitted) | 60 | 0.327 | -0.173 | 10/49/1 | +0.000 | 2.02 | 0/293 |
| Replay at actual stop (tau=0.7, R=3) | 60 | 0.327 | -0.173 | 10/49/1 | +0.000 | 2.02 | 0/293 |
| Replay R=1 (stop after round 1) | 60 | 0.483 | -0.017 | 29/29/2 | +0.122 | 1.00 | 0/293 |
| Replay R=2 | 60 | 0.334 | -0.166 | 10/49/1 | +0.000 | 1.81 | 0/293 |
| Replay tau=0.6 | 60 | 0.310 | -0.190 | 7/51/2 | +0.000 | 1.83 | 0/293 |
| Replay tau=0.5 | 60 | 0.358 | -0.142 | 8/48/4 | +0.000 | 1.62 | 0/293 |

v1v1v1 baseline median over the same technologies: 0.500

## B. Reruns on the 24-technology subset (October 2026)

Control is the r5 run (tau=0.7, R=5) from the same week as the tau reruns (26-27 October); no r5 debate went past round 3, so it is effectively tau=0.7, R=3 and isolates tau from drift since the April runs. *Better/worse/tied* and Δ are against the control.

| scenario | techs | median Jaccard | Δ vs control | better/worse/tied vs control | rounds | unmapped |
|---|---|---|---|---|---|---|
| Control: tau=0.7, R=5 (r5) | 24 | 0.334 | +0.000 | 0/0/24 | 1.85 | 1/120 |
| tau=0.85, R=3 | 24 | 0.374 | +0.039 | 11/11/2 | 2.40 | 0/120 |
| tau=0.95, R=3 | 24 | 0.302 | -0.033 | 8/15/1 | 2.50 | 1/120 |
| tau=0.95, R=5 (cap unused: no debate passed round 3) | 24 | 0.360 | +0.026 | 11/11/2 | 2.47 | 0/120 |

The two tau=0.95 rows are the same configuration in effect (the R=5 cap was never reached), so their +0.059 gap is run-to-run noise. It is as large as either tau effect, so no systematic tau effect is detectable at this sample size.


### Microelectronics techs in the subset (21), against v1 and the April runs

| scenario | techs | median Jaccard | Δ vs v1 | better/worse/tied vs v1 | rounds | unmapped |
|---|---|---|---|---|---|---|
| April submitted (tau=0.7, R=3) | 21 | 0.317 | -0.219 | 4/16/1 |  | 0/0 |
| Control: tau=0.7, R=5 (r5) | 21 | 0.332 | -0.204 | 5/15/1 |  | 0/0 |
| tau=0.85, R=3 | 21 | 0.354 | -0.182 | 6/14/1 |  | 0/0 |
| tau=0.95, R=3 | 21 | 0.300 | -0.236 | 3/17/1 |  | 0/0 |
| tau=0.95, R=5 (cap unused: no debate passed round 3) | 21 | 0.367 | -0.169 | 6/14/1 |  | 0/0 |
