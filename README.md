# econ-research-kit（中文镜像）

面向实证经济学的可执行工序库。八道工序，每道都有输入、产出文件与验收标准。

**版本 0.1.0** · 本仓是 [`econ-research-kit`](https://github.com/LWWalker2202/econ-research-kit)（英文主仓）的中文镜像，两仓结构由 CI 校验

---

## 为什么有这个库

关于"AI 做研究"的建议大多停在提示词。提示词产出的是段落，而一篇论文需要的是流水线：可行性判断、识别设计、干净的数据、站得住的设定、符合期刊格式的产出、能别人重跑的复现包。

本库把这条流水线拆成八道工序。每道工序回答四个问题：

1. **什么时候**进？——具体触发情形，不是"当你需要分析时"
2. **需要什么**才能进？——输入清单，以及缺了怎么办
3. **做什么**？——带可判定完成条件的步骤
4. **必须产出什么**？——有名字的文件，外加一张验收清单

文件齐了、每条验收都能回答"是"，这道工序才算完。

## 里面有什么

```
econ-research-kit-zh/
├── SKILL.md                 路由——哪种请求进哪道工序
├── skills/                  八道工序
│   ├── feasibility/         第 0 段——这事到底能不能做
│   ├── identification/      第 2 段——是什么变异在识别效应
│   ├── data-prep/           第 3 段——变量是不是我以为的那个意思
│   ├── estimation/          第 4 段——设定站不站得住
│   ├── tables-figures/      第 5 段——产出符不符合期刊格式
│   ├── report/              第 6 段——别人能不能复现
│   ├── writing/             第 7 段——文字有没有把设计讲清楚
│   └── review/              审稿回复
├── domains/                 领域知识，不含流程
│   ├── energy-env/          制度背景 · 变量构造 · 数据 · 审稿雷区
│   ├── labor/
│   └── behavioral/
├── data-dict/               CFPS · CHARLS · 工业企业库 · 污染监测
├── teaching/                本科 · 硕士 · 博士
├── index/actions.csv        动作清单（双语列，唯一数据源）
├── scripts/                 结构校验脚本
├── glossary.yaml            术语锁定表
├── VERSION
└── LICENSE
```

**分工一句话**：`skills/` 管怎么做，`domains/` 管这个领域特殊在哪，`data-dict/` 管数据长什么样。工序里不写领域事实，领域里不写流程。

## 安装

把仓库克隆到 agent 的 skills 目录。

**Codex**

```bash
git clone https://github.com/LWWalker2202/econ-research-kit-zh.git \
  ~/.codex/skills/econ-research-kit-zh
```

**Claude Code**

```bash
git clone https://github.com/LWWalker2202/econ-research-kit-zh.git \
  ~/.claude/skills/econ-research-kit-zh
```

重启 agent。验证是否加载：问一句「econ-research-kit 里 feasibility 这道工序判断什么」。答不上来就是没加载上。

没有构建步骤，除 `scripts/` 里的脚本需要 Python 3.9+ 之外没有依赖。

## 快速开始

**判断一个题目值不值得开工**

> 我手上是 2010–2019 年的企业面板，想看看中央环保督察有没有让企业减排。这个能做吗？

agent 应该进 `skills/feasibility/`，清点数据与变异，产出 `feasibility.md` 并给出明确的做/不做结论——在写任何代码之前。

**清洗面板并记录口径**

> 把企业面板和污染监测数据合起来，构造排放变量。

agent 应该进 `skills/data-prep/`，先核对跨年变量定义，产出清洗脚本与变量口径对照表。它不该手工改表。

**产出符合期刊格式的回归表**

> 把这三个设定做成一张投稿用的表。

agent 应该进 `skills/tables-figures/`，先问 Stata 还是 Python，再对齐目标期刊的格式——三线表规则、系数在上标准误在下、表注位置。

## 设计原则

1. **第 0 段是闸门，不是步骤。** 可行性不过就停。绝不替一个识别做不成的题目洗数据。
2. **产出文件优先于漂亮文字。** 每个阶段留下一个有名字的文件。段落不算产出。
3. **脚本优先于结果。** 跑脚本重现不出来的数字，等于不存在。
4. **领域知识与流程分离。** 这是唯一没法外包给通用工具的部分，所以单列一个目录。
5. **验收项必须能回答是/否。** "表看起来不错"不是验收项；"列宽不溢出正文版心"才是。

## 借用第三方工具库

表格、图形、数据清洗这些重活，开源项目早已做好。不要重写，也不要直接在原地改。

`skills/tables-figures/`（以及后续的 `skills/data-prep/`）分两层：

| 层 | 规矩 |
|---|---|
| `vendor/` | 原样复制，永不修改。每个目录带 `LICENSES.md`，记录上游仓库、commit、许可证，并写明"未修改"。 |
| `overrides/` | 我们自己的覆盖层。期刊格式、中文期刊惯例、数据怪癖的修正。只在这一层改。 |

vendor 进来的是代码与 LaTeX 模板，语言中立，因此在两个语言镜像中**逐字节相同**。只有 `overrides/` 需要翻译。

候选上游（许可证核查后再 vendor）：

| 需要什么 | 上游类型 |
|---|---|
| 多列回归表 | Stata `esttab`、R `modelsummary` / `fixest::etable` |
| 事件研究与系数图 | Stata `coefplot`、R `fixest::iplot` |
| 出版级图形主题 | Kieran Healy 的 ggplot 惯例 |
| 端到端流水线 | `codex-stata-for-economists`（面向经济学家的 Stata 管线） |
| 分析类 skill | `awesome-econ-ai-stuff` 的 Data 与 Analysis 分类 |

**目前尚未 vendor 任何内容。** vendor 需要联网拉取并逐个核查许可证。目录已预留，上面的清单就是操作步骤。不要把代码粘进来却不记 commit。

## 与中文镜像的一致性

本仓是 `econ-research-kit` 的中文镜像，同一棵树。规则：

- 路径与文件名完全一致，永不翻译。
- `scripts/` 与 `glossary.yaml` **逐字节相同**。
- 其余每个文件的标题结构、验收条目数、占位符集合都相同——只有语言不同。
- `writing` 与 `tables-figures` 是刻意的例外：英文仓写英文期刊规范，中文仓写中文期刊规范。小节相同，内容不同。

`scripts/check_parity.py` 检查以上全部。CI 每次 push 都跑。

## 参与贡献

1. 先读术语规则：方法术语必须用 `locked` 译法。
2. 新工序要有全部八节。缺什么 `scripts/lint_content.py` 会告诉你。
3. 不要在没有删掉一个的情况下加第九道工序。八道是设计，不是起点。
4. 数字、页码、政策文号一律不许编。写 `[待填]`。

## 状态

版本 0.1.0。八道工序、三个方向、四份数据字典、三档教学读法。vendor 待做。中文镜像已对齐。

## 许可证

我们自己的内容用 MIT。vendor 进来的材料保留其原有许可证，记录在各 `vendor/LICENSES.md`。
