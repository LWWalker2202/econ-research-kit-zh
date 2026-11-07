# The two-sided review of data and regression

Every review has two sides. The machine side is cheap and must run every time; the
human side is what catches the things a machine cannot see.

**Machine side (run before the next stage and before delivery)**

- `python scripts/verify_chain.py` - the number chain: cleaning arithmetic, estimation N
  against the cleaned row count, and every decimal in the report against the results file.
- `python scripts/crosscheck.py` - a second implementation recomputes the gold coefficients;
  a coefficient that moves by more than 1e-6, or a standard error outside the 0.75-1.35 band,
  means one of the two implementations is wrong, not that the number "changed".
- `python scripts/coverage.py` - the 15-point self-check of a research project.

**Human side (a second reader, a colleague or a reviewing agent)**

1. Read the cleaning log, then the cleaning code: does every filter the log names exist in
   the code, and does every filter in the code appear in the log? A filter that runs but is
   not logged is the worst case - the N changes and nobody knows why.
2. Open the raw file and look at three rows by hand: the first row, one duplicate, one row
   that should be dropped. If the dropped row survived, the join key is wrong.
3. Recompute one coefficient in a different tool (Stata or R) from the cleaned data. If it
   disagrees, check degrees of freedom and clustering before believing either number.
4. Compare the table in the paper with the results file term by term: same variable names,
   same sample size, same stars. A table that "looks right" is the most common failure.
5. Ask what the result would look like if the main filter were wrong: if the conclusion
   survives a plausible error, the paper is safer than if it hinges on one line of code.

Record what you checked in `.econ-kit/review.md` (one line per item: what, how, result) and
`gate.py pass --extra "复核：..."` so the ledger carries the evidence.
