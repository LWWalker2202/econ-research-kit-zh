# Report template: a runnable builder

`build_report.py` turns a frozen LaTeX table and a frozen estimation result into a
Markdown report of six fixed sections. It uses only the Python standard library,
so the template runs on a plain machine with no renderer installed.

## Why a Python builder instead of Quarto

The skill itself documents a Quarto project skeleton, and that skeleton is the
right shape for a project where Quarto is installed. This repository also
promises that every stage can be run and checked on the machine at hand, and no
Quarto, R, or pandoc is installed here. A template that cannot be executed cannot
be checked, so the shipped builder is a small Python program instead.

The contract does not change. The report body reads tables and numbers from
frozen files, never types a number by hand, and rebuilds identically on a second
run. A project that migrates to Quarto keeps the same directory contract and the
same distinction between the frozen inputs and the prose.

## What the builder reads and writes

| Flag | Required | What it does |
|---|---|---|
| `--tables` | yes | LaTeX table file, embedded verbatim inside a fenced block |
| `--results` | yes | JSON file written by the estimation stage, the only source of numbers |
| `--lang` | no | `en` or `zh`; changes prose only, never a number |
| `--out` | yes | destination Markdown file; parent directories are created |
| `--script` | no | estimation script path printed in the reproduction section; left open when omitted |

`--lang` defaults to `en`. The table is embedded exactly as it stands in the file
named by `--tables`, so the booktabs-style rules, the coefficient-over-standard-error
layout, the significance stars, and the table note all survive the embedding
without being rebuilt.

## What the output contains

The generated report has one H1 title and six fixed sections:

1. One-line conclusion: the benchmark coefficient, its standard error, the
   clustering level, and the number of observations in a single sentence.
2. Main results: the same estimate with its p-value and R-squared, a pointer to
   the table file, and the table itself inside a fenced block.
3. Robustness: one line per variance estimator recorded in the results file.
4. Data and definitions: four placeholders, written by the researcher.
5. How to reproduce: the estimation script, the random seed, the two input
   paths, and the exact command that produced the file.
6. What is still missing: items generated from the inputs themselves.

## How the builder picks the baseline

Among the specifications listed in the results file, the baseline is the last one
whose variance estimator is clustered at some level; if no specification is
clustered, the last specification is used. The reported coefficient is the term
the results file names as its robustness coefficient; if that term is not present,
the first coefficient of the selected specification is used.

Every number is copied and rounded to three decimals, printed as text. The
builder does not recompute a standard error, does not convert a t statistic into
a p-value, and does not infer a significance star.

## How to connect it to your own project

1. Freeze the estimate file first. Point `--results` at it, and check that the
   seed and the observation count it records are the ones you intend to report.
2. Point `--tables` at the table file produced by the tables-figures stage, not
   at a hand-edited copy of the table.
3. Fill the data section by extending the builder with a third input: a small
   JSON file holding the sample frame, the unit of observation, and the variable
   definitions, read the same way as `--results`. Editing the generated Markdown
   by hand breaks the guarantee that the report can be rebuilt.
4. Keep the generated file out of the manuscript: the manuscript includes the
   table, and the report is the record that the numbers and the table agree.

## What the builder will not do

- It does not estimate anything. It reads what the estimation stage wrote.
- It does not read Stata logs, and it does not embed figures.
- It does not fill a missing field. A field the inputs do not contain becomes a
  placeholder, never a plausible value.
- It does not verify that the table file and the estimate file come from the same
  project. It can only report that the benchmark coefficient is absent from the
  embedded table, and that sentence is a warning, not a proof.

## Checking that it still works

From the repository root, run the builder twice into two files with the same
arguments and compare the two hashes: identical bytes mean the output is
deterministic. Then run the content lint over the repository and confirm that the
generated Markdown passes, placeholders included.

The two repositories ship byte-identical copies of this file and of the builder.
The only difference between their generated reports is the language of the prose
and the table file each repository embeds; the numbers are identical.
