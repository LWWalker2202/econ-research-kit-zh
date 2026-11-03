# 可复现报告

本文件由 `skills/report/templates/build_report.py` 从 `## 复现方式` 一节列出的两个冻结文件生成。下文所有数值都取自这两个文件，文件里没有的字段一律打印为 `[待填]`，不由人手补写。

## 一句话结论

`D` 的系数为 0.352，标准误为 0.143（在 id 层面聚类的标准误）；该估计基于 600 个观测、设定为 `y ~ D + x1 + x2 | id + year`。

## 主结果

从 `skills/estimation/expected/estimation-results.json` 选定的基准设定：`y ~ D + x1 + x2 | id + year`，固定效应 `id, year`；点估计 0.352，标准误 0.143，p 值 0.017，R 方 0.529，观测数 600。

下表从 `skills/tables-figures/expected/table1.tex` 原样嵌入。转换时请让代码块原样通过，以保留三线表版式与表注。

```latex
\begin{table}[htbp]
\centering
\caption{基准回归结果}
\begin{tabular}{lccc}
\toprule
\multicolumn{4}{c}{y} \\
\midrule
 & (1) & (2) & (3) \\
\midrule
Treatment & 0.503*** & 0.500*** & 0.487*** \\
 & (0.097) & (0.102) & (0.101) \\
\addlinespace[0.3ex]
Control x &  &  & 0.268*** \\
 &  &  & (0.044) \\
\addlinespace[0.3ex]
\midrule
Firm FE & --- & Yes & Yes \\
Year FE & --- & Yes & Yes \\
\addlinespace[0.3ex]
\midrule
Observations & 480 & 480 & 480 \\
$R^2$ & 0.053 & 0.188 & 0.236 \\
\bottomrule
\end{tabular}
\par\smallskip\footnotesize 注：***、**、* 分别表示在 1%、5%、10% 的水平上显著；括号内为标准误。标准误聚类在个体层面。
\end{table}
```

## 稳健性

下面每一项对同一个稳健性设定 `y ~ D + x1 + x2 | id + year` 换一种方差估计方式；点估计保持不变，因此比较的是标准误。

- 独立同分布标准误：系数 0.352，标准误 0.152，p 值 0.021。
- 在 id 层面聚类的标准误：系数 0.352，标准误 0.143，p 值 0.017，聚类数 60。
- 在 block 层面聚类的标准误：系数 0.352，标准误 0.156，p 值 0.041，聚类数 15。
- 在 year 层面聚类的标准误：系数 0.352，标准误 0.100，p 值 0.007，聚类数 10。

## 数据与口径

本节由研究者填写。生成器故意留空：两个输入文件记录的是估计结果与表图，不含样本构造过程，由机器写在这里的每一句都会是无中生有。

- 样本范围与时间跨度：`[待填]`
- 观测单位：`[待填]`
- 变量定义与数据来源：`[待填]`
- 样本剔除规则与缩尾处理：`[待填]`

## 复现方式

- 估计脚本：`[待填]`
- 随机种子：`20260315`（读自结果文件）
- 输入文件：`skills/tables-figures/expected/table1.tex` 与 `skills/estimation/expected/estimation-results.json`
- 命令：`python skills/report/templates/build_report.py --tables skills/tables-figures/expected/table1.tex --results skills/estimation/expected/estimation-results.json --lang zh --out skills/report/expected/report.md`

## 还缺什么

- 估计脚本尚未记录；传入 `--script` 之后读者才能复跑估计。
- “数据与口径”一节仍是空位，只能由研究者补齐。
- 嵌入的表里没有结果文件中的基准系数 0.352。报告流出之前，先确认两个输入文件来自同一个项目。
- 结果文件里有事件研究系数，本报告没有汇总。
- 本报告不嵌入图；图在表图阶段产出，另行插入。
