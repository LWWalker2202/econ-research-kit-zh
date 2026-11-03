* estimate_main.do -- Stata counterpart of templates/estimate_main.py
*
* The Python script generates a synthetic panel from a fixed seed, runs five
* steps, and writes output/estimation-results.md and output/estimation-results.json.
* This file repeats the same five steps so the two versions can be read side by
* side. Block letters below match the step order in the Python file:
*
*   make_panel()            A. fixture
*   step 1, model m1        B. reghdfe, absorb(id year), vce(unadjusted)
*   step 2, model m2        C. add the two controls
*   step 3, model m3        D. vce(cluster id)
*   step 4, event study     E. relative-period dummies, base period -1
*   step 5, robustness      F. vce(cluster block) and vce(cluster year)
*   render_md, build_json   G. esttab export
*
* Requires reghdfe, ftools, and estout: ssc install reghdfe, ssc install ftools,
* ssc install estout. Run from the repository root:
*     stata -b do skills/estimation/templates/estimate_main.do
*
* Stata and numpy draw different random numbers, so the values here differ from
* the pinned report. What is meant to match is the structure: the same five
* steps, the same fixed effects, the same clustering levels, and the same base
* period.

version 16
clear all
set more off
set seed 20260315
capture mkdir output

* ---------------------------------------------------------------------------
* A. Fixture: 60 individuals over 2010-2019, cohorts 2014 and 2016, and 20
*    never-treated individuals coded as cohort 0.
* ---------------------------------------------------------------------------
local n_id = 60
local first_year = 2010
local n_year = 10

set obs `=`n_id' * `n_year''
gen int id = int((_n - 1) / `n_year')
gen int year = `first_year' + mod(_n - 1, `n_year')
gen int cohort = cond(id < 20, 2014, cond(id < 40, 2016, 0))
gen byte block = int(id / 4)
gen byte D = (cohort > 0) & (year >= cohort)

* One individual effect per individual, filled down the individual's years, and
* a linear year effect: the two components that the fixed effects absorb.
bysort id (year): gen double id_effect = rnormal(0, 0.8) if _n == 1
bysort id (year): replace id_effect = id_effect[1]
gen double year_effect = 0.05 * (year - `first_year')

gen double x1 = rnormal(0, 1)
gen double x2 = rnormal(0.2, 1)
gen double y = 0.45 * D + 0.30 * x1 - 0.20 * x2 + id_effect + year_effect + rnormal(0, 1)

label variable id "individual id"
label variable year "year"
label variable D "treated from the cohort year onward"
label variable x1 "first control"
label variable x2 "second control"
label variable y "outcome"
label variable block "individual-level cluster block"
label variable cohort "first treated year, 0 if never treated"

xtset id year

* ---------------------------------------------------------------------------
* B. Step 1: two-way fixed effects, no controls, homoskedastic standard errors.
*    This is the Python model m1: "y ~ D | id + year" with vcov="iid".
* ---------------------------------------------------------------------------
reghdfe y D, absorb(id year) vce(unadjusted)
estimates store m1

* ---------------------------------------------------------------------------
* C. Step 2: the same specification plus the two time-varying controls.
*    Python model m2: "y ~ D + x1 + x2 | id + year" with vcov="iid".
* ---------------------------------------------------------------------------
reghdfe y D x1 x2, absorb(id year) vce(unadjusted)
estimates store m2

* ---------------------------------------------------------------------------
* D. Step 3: the column (2) coefficients with standard errors clustered at the
*    individual level. Python model m3 uses vcov={"CRV1": "id"}.
* ---------------------------------------------------------------------------
reghdfe y D x1 x2, absorb(id year) vce(cluster id)
estimates store m3

* ---------------------------------------------------------------------------
* E. Step 4: event study. Two leads and two lags around the cohort year, base
*    period -1 omitted, and one binned endpoint on each side so that periods
*    outside the window do not fall into the base period. Controls and both
*    fixed effects stay in.
* ---------------------------------------------------------------------------
gen int rel = cond(cohort > 0, year - cohort, .)
gen byte rel_le_m3 = (rel <= -3) & !missing(rel)
gen byte rel_m2 = rel == -2
gen byte rel_p0 = rel == 0
gen byte rel_p1 = rel == 1
gen byte rel_p2 = rel == 2
gen byte rel_ge_p3 = (rel >= 3) & !missing(rel)

label variable rel "years since the cohort year, missing if never treated"
label variable rel_le_m3 "binned endpoint: three or more years before"
label variable rel_m2 "lead: two years before"
label variable rel_p0 "contemporaneous"
label variable rel_p1 "lag: one year after"
label variable rel_p2 "lag: two years after"
label variable rel_ge_p3 "binned endpoint: three or more years after"

reghdfe y rel_le_m3 rel_m2 rel_p0 rel_p1 rel_p2 rel_ge_p3 x1 x2, absorb(id year) vce(cluster id)
estimates store m4

* The omitted period is -1. Reghdfe drops nothing here, but the test below makes
* the base period explicit in the log instead of leaving it implicit.
display as text "base period: -1 (rel_m1 is not in the model)"
count if rel == -1
display as text "cells in the base period: " r(N)

* ---------------------------------------------------------------------------
* F. Step 5: robustness. The specification is held at column (2) and only the
*    cluster level changes, so the coefficient on D is identical across the
*    three rows and only the standard error moves.
* ---------------------------------------------------------------------------
reghdfe y D x1 x2, absorb(id year) vce(cluster block)
estimates store m5

reghdfe y D x1 x2, absorb(id year) vce(cluster year)
estimates store m6
display as error "note: only ten year clusters; the asymptotic standard error is optimistic, pair the row with a wild cluster bootstrap"

* ---------------------------------------------------------------------------
* G. Export. The Python version writes the Markdown and JSON reports; this file
*    writes the coefficient table in a form that can be diffed against them step
*    by step.
* ---------------------------------------------------------------------------
esttab m1 m2 m3 m4 m5 m6 using "output/estimation-results_stata.csv", replace ///
    b(4) se(4) ///
    keep(D x1 x2 rel_le_m3 rel_m2 rel_p0 rel_p1 rel_p2 rel_ge_p3) ///
    stats(N r2, labels("Observations" "R-squared")) ///
    title("estimation results, five steps") csv

estimates restore m4
estimates table rel_le_m3 rel_m2 rel_p0 rel_p1 rel_p2 rel_ge_p3, b(%9.4f) se(%9.4f)

display as text "wrote output/estimation-results_stata.csv"
