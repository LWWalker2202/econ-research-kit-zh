* clean_panel.do -- Stata counterpart of templates/clean_panel.py
*
* Runs the same six cleaning steps on the same synthetic design: 40 firms,
* 2018-2023, with the same failures injected at the same row positions
* (duplicates, missing key fields, an unbalanced panel, outliers, mixed units,
* and a definition change in 2020).
*
* The numbers will not match the Python fixture value for value: Stata and
* numpy draw different random numbers from the same seed. What has to match is
* the shape -- which rows are dropped, which cells stay empty, which variable
* is trimmed, which rows are tagged -- because that shape is what
* expected/cleaning-log.md pins down for the Python side. Run both, compare
* the counts each prints, and only then point the pipeline at real data.
*
* Requires: winsor2 (install once with `ssc install winsor2`). Everything else
* is built in. The Markdown log is written by the Python script; this file
* prints the same counts to the console, in the same order.
*
* Do not change the winsor cuts or the 2020 definition switch casually: those
* are the parts the log is about. If a project needs different ones, copy this
* file into the project and change the copy.

version 16
clear all
set more off
set seed 20261103
capture mkdir output

* ---- fixture: 40 firms x 2018-2023 ---------------------------------------
* Same generator as the Python script, same seed, different random draws.
local n_firm = 40
local n_year = 6
set obs `=`n_firm' * `n_year''
gen long firm = floor((_n - 1) / `n_year') + 1
gen int  year = 2018 + mod(_n - 1, `n_year')
gen double u           = rnormal()
bysort firm: gen double size = exp(log(50000) + 0.8 * u[1])
gen double assets      = size * exp(rnormal(0, 0.1))
gen double revenue_wan = assets * runiform(0.5, 1.6)
gen double roa         = 0.03 + 0.05 * rnormal() + 0.03 * (year >= 2020)
gen double leverage    = max(0, 0.55 + 0.25 * rnormal())

* Mixed units: yuan before 2020, ten-thousand yuan from 2020 on.
gen double revenue = cond(year <= 2019, round(revenue_wan * 10000), round(revenue_wan, 0.01))
drop revenue_wan

* Inject the failures at fixed row positions (1-based; the Python script uses
* 0-based indices, so a Python index i is row i + 1 here).
* Missing key fields: revenue in rows 12, 58, 119, 177; roa in 34, 96, 211.
foreach r of numlist 12 58 119 177 {
    replace revenue = . in `r'
}
foreach r of numlist 34 96 211 {
    replace roa = . in `r'
}
* Missing non-key field: leverage in rows 71, 141, 206.
foreach r of numlist 71 141 206 {
    replace leverage = . in `r'
}
* Outliers: roa in rows 8, 62, 151; leverage in rows 23, 181.
replace roa      =  1.85 in 8
replace roa      =  2.40 in 62
replace roa      = -1.10 in 151
replace leverage =  9.70 in 23
replace leverage = 12.40 in 181

* Exact duplicate rows: five copies appended at the end of the file.
* (This is fixture construction, not cleaning; step 1 removes them again.)
tempfile base extra
save `base', replace
use `base', clear
keep if inlist(_n, 6, 43, 91, 134, 202)
save `extra', replace
use `base', clear
append using `extra'

* ---- step 1: duplicates ---------------------------------------------------
* A duplicate is an exact copy on the full row. Log the count before dropping.
local n_before = c(N)
quietly duplicates drop
local n_after = c(N)
local n_removed = `n_before' - `n_after'
display as text "step 1  rows before: `n_before'  removed: `n_removed'  rows after: `n_after'"

* ---- step 2: missing values in key fields --------------------------------
* Rate first, then the drop. revenue and roa are key fields; leverage is not,
* so its gaps stay and only the specification using it loses those rows.
misstable summarize revenue roa leverage, all
quietly count if missing(revenue) | missing(roa)
display as text "step 2  rows dropped on a missing key field: " r(N)
drop if missing(revenue) | missing(roa)
quietly count
display as text "step 2  rows remaining: " r(N)

* ---- step 3: panel balance ----------------------------------------------
* Report the gaps; do not interpolate them and do not drop firms to make the
* table look rectangular.
xtset firm year
xtdescribe
bysort year: gen int n_cells = _N
egen byte _tag = tag(year)
display as text "step 3  cells present per year (the balanced panel would be 40):"
list year n_cells if _tag, noobs
drop n_cells _tag

* ---- step 4: winsorize the ratios ---------------------------------------
* 1st and 99th percentiles. The level variable revenue is left out on purpose:
* its unit is still mixed at this step (see step 5).
winsor2 roa leverage, cuts(1 99) replace
tabstat roa leverage, statistics(min max p1 p99 n) columns(statistics) format(%9.4f)

* ---- step 5: unit harmonization -----------------------------------------
* Convert in code, never in a spreadsheet cell, and put the unit into the
* variable name so it travels with the column.
replace revenue = revenue / 10000 if year <= 2019
rename revenue revenue_wan

* ---- step 6: definition drift -------------------------------------------
* The codebook says roa changes definition in 2020 (net profit before,
* operating profit after). Tag the rows; do not pool the two periods.
gen byte roa_vintage = cond(year <= 2019, 1, 2)
bysort roa_vintage: summarize roa
display as error "WARNING: roa is not one variable across the sample: net profit / total assets in 2018-2019, operating profit / total assets in 2020-2023. Rows are tagged in roa_vintage; do not pool the two periods without saying so."

* ---- write the clean panel ----------------------------------------------
compress
sort firm year
order firm year revenue_wan roa leverage roa_vintage
label variable revenue_wan  "Revenue, ten-thousand yuan"
label variable roa          "Return on assets, two definitions, see roa_vintage"
label variable leverage     "Leverage, winsorized at the 1st and 99th percentiles"
label variable roa_vintage  "1 net profit definition, 2 operating profit definition"
export delimited firm year revenue_wan roa leverage roa_vintage ///
    using "output/clean_panel_stata.csv", replace
* Stata's CSV writer is not byte-stable across versions, so the golden file is
* the Python one; this export is for a side-by-side check of the shape.
display as text "wrote output/clean_panel_stata.csv"
