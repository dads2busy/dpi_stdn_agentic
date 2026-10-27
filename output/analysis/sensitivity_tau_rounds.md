# Convergence threshold (tau) and round cap (R) sensitivity

Metric: per-technology median pairwise Jaccard of canonical component sets across runs (the submitted stability metric), median over technologies. Component sets are taken from debate transcripts and mapped through `data/component_canonical_vocab_sensitivity.json`. *Better/worse/tied* counts technologies against the single-agent v1v1v1 baseline. *Rounds* is the mean number of debate rounds used. *Unmapped* counts component names not in the vocabulary (kept verbatim).

`data/component_canonical_vocab_sensitivity.json` is the revision vocabulary plus LLM mappings for names that appear only in replayed early rounds (built with `--extend-vocab`, using the submitted normalization's model, prompt and technology context). Without it those names stay unnormalized and early-stop stability is understated: the stop-after-round-1 median falls from 0.288 to 0.144 with 1,797 unmapped names.

## A. Submitted microelectronics runs (d3v1v1, 60 technologies, 5 runs), replayed

Replays apply the pipeline's consensus rule to the proposals of the round where the debate would have stopped. The replay at the actual stop reproduces the recorded final consensus exactly for most runs; the rest differ by the post-debate LLM normalization pass, so replayed scenarios are compared against the replay at the actual stop (Δ vs replay).

| scenario | techs | median Jaccard | Δ vs v1 | better/worse/tied vs v1 | Δ vs replay (median of per-tech diffs) | rounds | unmapped |
|---|---|---|---|---|---|---|---|
| Recorded final (tau=0.7, R=3, as submitted) | 60 | 0.327 | -0.173 | 10/49/1 | +0.000 | 2.02 | 0/293 |
| Replay at actual stop (tau=0.7, R=3) | 60 | 0.313 | -0.187 | 10/49/1 | +0.000 | 2.02 | 0/293 |
| Replay R=1 (stop after round 1) | 60 | 0.288 | -0.212 | 9/49/2 | -0.021 | 1.00 | 0/293 |
| Replay R=2 | 60 | 0.286 | -0.214 | 8/51/1 | +0.000 | 1.81 | 0/293 |
| Replay tau=0.6 | 60 | 0.284 | -0.216 | 7/52/1 | -0.006 | 1.83 | 0/293 |
| Replay tau=0.5 | 60 | 0.250 | -0.250 | 5/54/1 | -0.046 | 1.62 | 0/293 |

v1v1v1 baseline median over the same technologies: 0.500

## B. Reruns on the 24-technology subset (October 2026)

Control is the same-session r5 run (tau=0.7, R=5); no r5 debate went past round 3, so it is effectively tau=0.7, R=3 and isolates tau from drift since the April runs. *Better/worse/tied* and Δ are against the control.

| scenario | techs | median Jaccard | Δ vs control | better/worse/tied vs control | rounds | unmapped |
|---|---|---|---|---|---|---|
| Control: tau=0.7, R=5 (r5) | 24 | 0.334 | +0.000 | 0/0/24 | 1.85 | 1/120 |
| tau=0.85, R=3 | 24 | 0.374 | +0.039 | 11/11/2 | 2.40 | 0/120 |
| tau=0.95, R=3 | 24 | 0.302 | -0.033 | 8/15/1 | 2.50 | 1/120 |
| tau=0.95, R=5 | 24 | 0.360 | +0.026 | 11/11/2 | 2.47 | 0/120 |

### Microelectronics techs in the subset (21), against v1 and the April runs

| scenario | techs | median Jaccard | Δ vs v1 | better/worse/tied vs v1 | rounds | unmapped |
|---|---|---|---|---|---|---|
| April submitted (tau=0.7, R=3) | 21 | 0.317 | -0.219 | 4/16/1 |  | 0/0 |
| Control: tau=0.7, R=5 (r5) | 21 | 0.332 | -0.204 | 5/15/1 |  | 0/0 |
| tau=0.85, R=3 | 21 | 0.354 | -0.182 | 6/14/1 |  | 0/0 |
| tau=0.95, R=3 | 21 | 0.300 | -0.236 | 3/17/1 |  | 0/0 |
| tau=0.95, R=5 | 21 | 0.367 | -0.169 | 6/14/1 |  | 0/0 |
