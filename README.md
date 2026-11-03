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
│   └── _catalog.md          指向外部上千个数据源的目录
├── teaching/                本科 · 硕士 · 博士
├── index/actions.csv        动作清单（双语列，唯一数据源）
├── scripts/                 结构校验脚本、数据源查询
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

**DSH（DeepSeek Harness）**

DSH 读两个技能目录，一个是多个 agent 共用的，一个是它自己的：

```bash
# 共用目录，推荐
git clone https://github.com/LWWalker2202/econ-research-kit-zh.git \
  ~/.agents/skills/econ-research-kit-zh

# 或只给 DSH 用
git clone https://github.com/LWWalker2202/econ-research-kit-zh.git \
  ~/.dsh/skills/econ-research-kit-zh
```

Windows 下这两个目录是 `%USERPROFILE%\.agents\skills\` 与 `%USERPROFILE%\.dsh\skills\`。一个技能就是一个含 `SKILL.md` 的目录，不需要另外注册；DSH 已经在跑的话，开一个新会话让它重新读技能列表。

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

`skills/tables-figures/` 与 `skills/data-prep/` 各分两层：

| 层 | 规矩 |
|---|---|
| `vendor/` | 原样复制，永不修改。每个目录带 `LICENSES.md`，记录上游仓库、commit、许可证，并写明"未修改"。 |
| `overrides/` | 我们自己的覆盖层。期刊格式、中文期刊惯例、数据怪癖的修正。只在这一层改。 |

vendor 进来的是代码与 LaTeX 模板，语言中立，因此在两个语言镜像中**逐字节相同**。只有 `overrides/` 需要翻译。

已 vendor 的项目（两批）：

| 目录 | 上游 | Commit | 许可证 |
|---|---|---|---|
| `skills/tables-figures/vendor/stata-schemepack/` | asjadnaqvi/Stata-schemes（包名 `schemepack`） | `580187ca3cd1101a17da6518a258b8ac533f7c5e` | MIT |
| `skills/tables-figures/vendor/awesome-econ-ai-stuff/` | meleantonio/awesome-econ-ai-stuff | `dd890d51c789fb8f8e316a2d7e4ed5d4bd793c50` | CC0 1.0 Universal |
| `skills/tables-figures/vendor/mgmt-paper-skills/` | HaonanAlex/mgmt-paper-skills | `971d2f510dc849b3fbf55836f78f6f2847203a1f` | Apache-2.0，`LICENSE` 与 `NOTICE` 随材料一并转发 |
| `skills/tables-figures/vendor/tex4econ-tab/` | FanWangEcon/Tex4Econ | `8f7a254656b98ce5c152ea3b5ed1f2833cca496e` | MIT |
| `skills/data-prep/vendor/awesome-econ-ai-stuff/` | meleantonio/awesome-econ-ai-stuff | `dd890d51c789fb8f8e316a2d7e4ed5d4bd793c50` | CC0 1.0 Universal |

五个 vendor 目录、103 个文件、约 350 KB。内容分四类：

- 十套 Stata 图形方案：白底整套配色加一套色盲友好配色。
- 三份带完整骨架的提示词规范：三线表、`ggplot2` 图形、Stata 清洗 do 文件。
- `mgmt-paper-skills/` 整目录引入三个子目录、一字未改：`mgmt-paper-tables/` 给出《经济研究》《管理世界》与 Journal of Finance、Management Science 四种刊的表格式，显著性约定、标准误选择，以及 Stata、R、Python 三套模板与测试；`mgmt-paper-publication-figures/` 是中文刊配图与三线表规范，含七类 matplotlib 模板；`mgmt-paper-journal-figures/` 是 UTD 24 种商科期刊的图表规格档。
- `Tex4Econ` 的 `_tab/` 取五段 LaTeX 表片段：估计结果表、多面板表、正文表，只取 `.tex` 源码。

许可证核查结果：

- `codex-stata-for-economists` 内容有用，但整个仓库没有 `LICENSE`、`LICENCE` 或 `COPYING` 文件，各 markdown 里也没有任何许可证声明。没有许可证就没有授权，故不 vendor。
- `EthanDeng/Chinese-ERJ`（`8cd9523ae8f34c3d272e5369a66a341317bc6c96`）许可是 LPPL 1.3c。LPPL 允许原样转发，与"原样复制"并不冲突；但材料只是《经济研究》一个刊的文档类（`chinese-erj.cls`），还依赖外部 `biblatex-gb7714-2015` 宏包，适用面太窄，故不引入。
- `esttab`、`coefplot`、`modelsummary`、`fixest` 仍是做表和系数图的正解，但它们由用户自己的 Stata 或 R 安装，不必把代码抄进本仓。
- 没有 MIT、BSD-2、BSD-3、Apache-2.0、CC-BY 或 CC0 明文授权的候选一律否决。"GitHub 上公开"不等于许可证。

三个规矩对所有 vendor 目录生效：原样复制、永不修改；每个目录必须有 `LICENSES.md`，写明仓库地址、commit、被复制的具体文件、许可证、许可证文件在哪、复制日期；不用 git submodule，保证直接 clone 就完整。每个 `vendor/` 根目录另有一份索引 `LICENSES.md` 列出其中上游与被否候选。期刊格式惯例放 `overrides/`。不要把代码粘进来却不记 commit。

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
5. 找数据源？`scripts/lookup_source.py CFPS --lang zh` 可以查外部上千个源的目录。查到只是线索；真开始用了，再在 `data-dict/` 写一篇编号条目。

## 状态

版本 0.1.0。八道工序、三个方向、四份数据字典、三档教学读法。vendor 分两批完成：图形方案、提示词规范、三套经管期刊表图 skill 目录、LaTeX 表片段，许可证记在 `skills/*/vendor/` 下。中文镜像已对齐。

## 许可证

我们自己的内容用 MIT。vendor 进来的材料保留其原有许可证，记录在各 `vendor/LICENSES.md`。
