* make_table.do -- Stata counterpart of templates/panel_ols.py
*
* Produces the same three specifications and the same three-line table.
* The numbers will not be identical to the Python fixture (different random
* draws), but the *shape* of the table must be: same rows, same order, same
* FE rows, same note. That shape is what expected/table1.tex pins down.
*
* Requires: reghdfe, ftools, estout. Install once with
*   ssc install reghdfe
*   ssc install ftools
*   ssc install estout
*
* Do not edit the esttab options casually: the point is that the output is
* comparable across languages and across years. If a journal needs a different
* layout, copy this file into the project and change the copy.

version 16
clear all
set more off
set seed 20260101

* ---- synthetic panel, same design as the Python fixture -------------------
local n_firm = 60
local n_year = 8
set obs `=`n_firm' * `n_year''
gen long firm = floor((_n - 1) / `n_year') + 1
gen int  year = 2015 + mod(_n - 1, `n_year')
gen double x     = rnormal()
gen byte   treated = runiform() < 0.4
gen double y     = 1 + 0.5 * treated + 0.3 * x + rnormal()

* ---- three specifications -------------------------------------------------
eststo clear
eststo m1: regress y treated, vce(robust)
eststo m2: reghdfe y treated, absorb(firm year) vce(cluster firm)
eststo m3: reghdfe y treated x, absorb(firm year) vce(cluster firm)

* ---- the table ------------------------------------------------------------
* ind("   ") keeps the standard errors under the coefficient instead of
* putting them in the same cell; that is the layout expected/table1.tex uses.
esttab m1 m2 m3 using "output/table1_stata.tex", replace ///
    booktabs ///
    b(3) se(3) ///
    star(* 0.10 ** 0.05 *** 0.01) ///
    keep(treated x) ///
    coeflabels(treated "Treatment" x "Control x") ///
    order(treated x) ///
    indicate("Firm FE = *.firm" "Year FE = *.year") ///
    stats(N r2, labels("Observations" "R-squared") fmt(0 3)) ///
    mtitles("(1)" "(2)" "(3)") ///
    nonotes ///
    addnotes("Note: ***, ** and * denote significance at the 1%, 5% and 10% levels; standard errors are in parentheses. Standard errors are clustered at the firm level.")

* esttab writes the note only when it is told to; with nonotes + addnotes the
* output keeps a single note line, which is what the layout check compares.
