# Pre-registration: two tests of multi-agent debate utility (2026-11-18)

Written before any result of either test was computed. Outcomes are reported whichever way they go.

Context: under per-technology normalization, 3-agent debate lowers run-to-run stability and gold recall
(output/analysis/debate_raw_gain_split.md, seeding_test.md). These tests check two mechanisms by which
debate could still be useful.

## Test 1: debate confidence as an uncertainty signal (existing runs, no new runs)

Hypothesis: a component's confidence better predicts whether it is reproducible when it comes from a debate
run (confidence includes multi-agent support) than from a single-agent run (self-rated).

- Data: raw run files, mapped to canonicals with the per-technology vocab
  `data/component_canonical_vocab_techscope_a.json` (pass B, `_techscope_b`, as replication). Items mapped to
  the non-primary sentinel are excluded.
- Unit: (run, technology, canonical). Score = max `component_confidence` over the raw names in that run that
  map to the canonical.
- Label (primary): the canonical appears in at least 3 of the 5 runs of that technology and configuration.
  Only technologies with exactly 5 runs in the configuration are used.
- Metric: AUC of score vs label, computed within each technology (technologies where both labels occur),
  then averaged over technologies. Ties count 0.5.
- Comparison: mean within-technology AUC of d3 minus v1, per domain. 95% CI by bootstrap over technologies
  (2,000 resamples, seed 0), resampling the technologies that have AUCs in both configurations.
- Primary dataset: post-fix session (fx{micro,biotech,pharma}_{v1v1v1,d3v1v1}). Replication: submitted
  session (v1v1v1/d3v1v1 April micro, biotech_/pharma_ May).
- PASS: d3 − v1 > 0 with the 95% CI excluding 0 in at least 2 of 3 domains in the primary dataset, with
  the same sign under vocab pass B.
- Secondary (reported, not decisive): d5 vs v1 (submitted session); the same analysis with label = present in
  all 5 runs.

## Test 2: debate under non-greedy sampling (new runs)

Hypothesis: all runs used near-greedy component sampling (temperature 0.03, top_p 0.0001), which leaves a
single agent little noise for debate to average out. At temperature 0.7, debate improves stability.

- Technologies: `data/tech_list_tau_subset.csv` (20 stratified micro + 4 gold-standard techs).
- Runs: 5 replicates each of
  - t003v1: v1v1v1 at temperature 0.03 / top_p 0.0001 (`config_tau_subset.json`)
  - fxctl (existing, 2026-10-27): d3v1v1 at temperature 0.03 / top_p 0.0001, tau 0.7, R 3
  - t07v1: v1v1v1 at component temperature 0.7 / top_p 1.0 (`config_tau_subset_t07.json`)
  - t07d3: d3v1v1 at component temperature 0.7 / top_p 1.0, tau 0.7, R 3
  Only the component-stage sampling keys differ; the metric uses components only.
- Normalization: per-technology vocab built from scratch over the raw files of all four batches together
  (`--vocab-scope technology`), two independent passes A and B.
- Metric: per-technology median pairwise Jaccard of canonical sets over the 5 runs.
- PASS if either holds in both normalization passes:
  (a) Δ(0.7) = d3 − v1 at temperature 0.7 is positive, paired Wilcoxon p < 0.05 over the 24 technologies; or
  (b) the interaction Δ(0.7) − Δ(0.03) is positive with its 95% bootstrap CI (over technologies, 2,000
      resamples, seed 0) excluding 0.
- Secondary (reported, not decisive): raw-name Jaccard; stability of v1 at 0.7 vs 0.03 (how much noise
  temperature adds).
- n = 24, so the test has limited power; a null result is weak evidence of no effect.

## Addendum (2026-11-18, after Tests 1 and 2 ran, before Test 3 and 4 results)

Test 2 found that component sampling settings were never sent to the API: every run, including t003v1 and
t07v1, used provider defaults (temperature 1, top_p 1). Test 2 is therefore not evaluable as written. The
sampling fix (STDNDependencies.sampling_settings passed as model_settings at the three component call sites)
makes the configured values take effect.

### Test 3: debate under truly near-greedy sampling

- Runs: 5 replicates each of g0v1 (v1v1v1) and g0d3 (d3v1v1, tau 0.7, R 3) on the 24-tech subset with
  `config_tau_subset.json` (component temperature 0.03, top_p 0.0001), now applied. Default-sampling
  comparators: t003v1 (v1) and fxctl (d3).
- Normalization: per-technology vocab from scratch over all four batches together, passes A and B.
- Metric: as Test 2. Δ(greedy) = d3 − v1 at near-greedy; interaction = Δ(greedy) − Δ(default).
- Reported either way. Expectation from the noise-averaging argument: debate helps less at near-greedy, so
  this test is not expected to favour debate; its main use is a correct description of sampling.
- PASS (debate helps at near-greedy): Δ(greedy) > 0 with Wilcoxon p < 0.05 in both passes.

### Test 4: judge invalid rate under per-technology normalization

- Re-run the LLM judge (scripts/judge_stage1_components_from_normalized_outputs.py, gpt-4.1) on the
  per-technology normalized outputs (output/normalized_techscope_a).
- Metric: per-technology deduped-canonical invalid rate; Δ = debate − v1 per domain, paired Wilcoxon, for
  submitted d3, post-fix d3 and d5.
- PASS (debate reduces invalid output): Δ < 0 with p < 0.05 in at least 2 of 3 domains in the post-fix data.
