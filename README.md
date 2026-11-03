# econ-research-kit（中文镜像）

面向实证经济学的工作台：**八道工序、十二个领域**，每一道工序要么有能跑的模板加金样可供比对，要么有一个读你产出的检查器。

**版本 0.3.1** · 本仓是 [`econ-research-kit`](https://github.com/LWWalker2202/econ-research-kit)（英文主仓）的中文镜像，两仓结构由 CI 校验

## 为什么要做这个

让模型帮忙做研究时，出问题的通常不是"模型不够聪明"，而是另外三件事。

1. **每次都从头解释一遍。** 课题设定活在一段会滚没的对话里，所以第一百次提问和第一次一样，什么都不知道。
2. **代码看着对，但你判断不了它到底对不对。** 一张"看着像那么回事"的表不是表。对话里没有任何东西会去检查聚类层级和处理分配对不对得上。
3. **组里每个人做法都不一样。** 交接一个课题等于交接一段对话，接手的人看不到哪些路试过、哪些被否了。

这个库押的是相反的注：**把工序写成文件，只写一次，让模型读的和读的是同一份东西。** 文件可以被检查、被版本化、被质疑、被替换；对话不能。

## 里面有什么

| 层 | 装什么 | 它回答什么 |
|---|---|---|
| `skills/` | 八道工序的规程 | 这一步到底怎么做？ |
| `domains/` | 十二个领域包，每包五份文件 | 我这个领域在这里特殊在哪？ |
| `data-dict/` | 中国微观数据源 | 这个变量到底叫什么？ |
| `index/actions.csv` | 四十九个动作，双语列 | 我现在到底想干什么？ |
| `scripts/` | 四个校验脚本 | 仓库还是不是一致的？ |
| `book/` | 配套用书 | 为什么长成这样？ |

一句话：`skills/` 管**怎么做**，`domains/` 管**这领域特殊在哪**，`data-dict/` 管**变量叫什么**。

## 五分钟

不用装任何东西。Python 3.11 以上，只用标准库。

```bash
# 1. 内容干不干净
python scripts/lint_content.py .

# 2. 两版还对得上吗
python scripts/check_parity.py

# 3. 生成一张表，与金样比
cd skills/tables-figures
python templates/panel_ols.py --lang zh
diff output/table1.tex expected/table1.tex
```

第三条命令如果没有输出，说明你刚从固定种子复现出一张出版级三线表。这才是重点：重要的不是表出来了，而是**你能判断它对不对**。

## 八道工序

| # | 工序 | 目录 | 它回答什么 |
|---|---|---|---|
| 0 | 可行性闸门 | `skills/feasibility/` | 手上的数据和变异，到底能不能做？ |
| 1 | 问题与文献 | `skills/feasibility/`（第二部分） | 这个空白是真的吗，值得写成一篇吗？ |
| 2 | 识别设计 | `skills/identification/` | 靠什么变异识别效应，什么会把它推翻？ |
| 3 | 数据 | `skills/data-prep/` | 变量是不是我以为的那个意思？ |
| 4 | 估计 | `skills/estimation/` | 设定站得住吗，每一项稳健性在防什么？ |
| 5 | 表与图 | `skills/tables-figures/` | 产出合不合刊物格式？ |
| 6 | 报告 | `skills/report/` | 别人能不能照着我的文件复现？ |
| 7 | 写作与投稿 | `skills/writing/` | 文字有没有把识别故事讲出来？ |
| - | 审稿回复 | `skills/review/` | 怎么回应，又不该让的地方没让？ |

**第 0 段是闸门，不是步骤。** 它不过就停。别给一个识别根本做不成的课题去清洗数据，一年就是这么没的。

## 十二个领域

| 目录 | 领域 |
|---|---|
| `domains/energy-env/` | 能源与环境经济学 |
| `domains/labor/` | 劳动经济学 |
| `domains/education/` | 教育经济学 |
| `domains/health/` | 健康经济学 |
| `domains/behavioral/` | 行为与实验经济学 |
| `domains/development/` | 发展经济学与田野实验 |
| `domains/public/` | 公共经济学与政策评估 |
| `domains/industrial-organization/` | 产业组织与规制 |
| `domains/trade-spatial/` | 国际贸易与空间经济 |
| `domains/macro-finance/` | 宏观经济学与金融 |
| `domains/economic-history/` | 经济史与史料 |
| `domains/theory/` | 理论建模与机制设计 |

每个领域包有五份文件：`institutional.md`（制度背景、时间线、可以直接粘进论文的段落）、`measures.md`（处理变量怎么构造、每种定义各自假设什么）、`data.md`（数据来源、变量名、覆盖范围、已知问题）、`pitfalls.md`（审稿人会问什么、怎么回应）、`route.md`（八道工序里该看哪几段、在那里要确认什么）。

**领域是筛子，不是漏斗。** 一篇关于环境规制与企业投资的论文，同时踩在能源环境、公共经济学和产业组织上。需要的包都看，不要挑一个就住进去。

## 哪些工序真的能跑

三道工序自己产出东西，五道工序读你产出的东西。没有一道是"提醒你小心点"的空话。

| 工序 | 给了什么 | 怎么验 |
|---|---|---|
| 可行性 | `check_memo.py`、填好的备忘录、六项机检 | `python skills/feasibility/templates/check_memo.py skills/feasibility/expected/feasibility-memo.md` |
| 识别 | `check_design.py`、填好的备忘录、六项机检 | `python skills/identification/templates/check_design.py skills/identification/expected/identification-memo.md` |
| 数据 | `clean_panel.py` 与 Stata 对照版，清洗日志作金样 | 连跑两遍，哈希不许变 |
| 估计 | `estimate_main.py` 与 Stata 对照版，五步设定链 | `python skills/estimation/templates/estimate_main.py --lang zh` |
| 表图 | `latex_table.py`、`panel_ols.py`，`table1.tex` 作金样 | 与 `expected/table1.tex` 比 |
| 报告 | `build_report.py`，把产出文件变成一份报告 | 数值只从输入文件来，一次也不许猜 |
| 写作 | `check_abstract.py`，七项机检 | `python skills/writing/templates/check_abstract.py skills/writing/expected/abstract-zh.md` |
| 审稿 | `check_response.py`，五项机检 | `python skills/review/templates/check_response.py skills/review/expected/response-letter-zh.md` |

这些背后是两个习惯：**固定种子的夹具**（哈希一变，说明你动了东西），以及**每个生成器都配一份金样**（某次库升级偷偷改了格式，下次一跑就现形）。

## 配套用书

`book/` 里放着 LW Walker 以及朋友们、家人们写的《经济学提示词工程指南》：208 页、六十个模板，写给本科、硕士、博士三个层次同时看。书解释工序为什么长这样，这个仓库是能跑的那一版。该读哪一份、哪一章配哪一道工序，见 `book/README.md`。

它的那句主张也是这个库的主张：**不可验收的提示词不是规格，是许愿。** 如果只读一章，读第三章——经济学问题描述的八个要素——然后打开 `skills/identification/SKILL.md`，看同一个想法变成文件是什么样子。

## 设计原则

1. **第 0 段是闸门，不是步骤。** 可行性不过的课题，不配得到干净的数据。
2. **产出文件优先于漂亮文字。** 每一道工序都要留下文件。一次只产出了一段漂亮回答的对话，什么也没产出。
3. **脚本优先于结果。** 没有脚本的数字只是传闻。始终生成脚本，而不只是给出结果。
4. **领域知识与工序分开。** `skills/` 讲怎么做，`domains/` 讲这里特殊在哪。混在一起，两边都会很快过期。
5. **一条答不了是或否的验收项，就是写坏了的验收项。** 重写它，不要把它说软。
6. **能机检的绝不靠脑子记。** 机器晚上十一点不会犯困。

## 常见误解

- **这不是提示词合集。** 六十个模板在书里。这里是八道工序，各有输入、步骤、产出文件和验收清单。
- **它不替你做完研究。** 它阻止你在一个根本做不成的事情上花三个月，并在事后让你做过的事站得住。
- **十二个领域不是十二个 skill。** 领域回答"我这行特殊在哪"，工序回答"这一步怎么做"。两者是故意正交的。
- **金样不是数据。** 每一份夹具都是合成的。永远不要引用 `expected` 目录里的数字。
- **中文仓不是翻译仓。** 真正需要不同的地方是投稿规范：摘要字数、JEL 分类号还是中图分类号、表注写法、线上附录。所以 `writing` 与 `tables-figures` 两版不同，其余逐字对齐。

## 装法

四条路，挑一条。

```bash
# Codex
git clone https://github.com/LWWalker2202/econ-research-kit-zh.git ~/.codex/skills/econ-research-kit

# Claude Code
git clone https://github.com/LWWalker2202/econ-research-kit-zh.git ~/.claude/skills/econ-research-kit

# DSH：共用目录 DSH 和其它工具都会读；第二个目录只给 DSH
git clone https://github.com/LWWalker2202/econ-research-kit-zh.git ~/.agents/skills/econ-research-kit
git clone https://github.com/LWWalker2202/econ-research-kit-zh.git ~/.dsh/skills/econ-research-kit
```

Windows 上同样这几个位置是 `%USERPROFILE%\.codex\skills\`、`%USERPROFILE%\.agents\skills\` 等等。第四条路根本不需要 agent：打开 `SKILL.md`，按路由表走，打开它指向的文件。这个仓库是当文档用也成立的。

## 验证装上了

问 agent 三句话。如果第一句答得含糊，说明没加载。

1. "可行性那道工序到底在判断什么，不过会怎样？"
2. "构造环境规制的处理变量之前，我该先读哪个文件？"
3. "识别检查器那六项检查分别是什么？"

## 接着往下加

- **加一个领域。** 复制任意 `domains/<领域>/` 目录，五份文件名不变，`route.md` 最后写。然后跑两个校验。
- **加一道工序。** 建 `skills/<名字>/SKILL.md`，八个固定节，再把动作加到 `index/actions.csv`。那张表是双语列，就是为了一个文件同时服务两版、且逐字节相同。
- **vendor 上游。** 逐字节复制到 `skills/<名字>/vendor/<上游>/`，许可证与 NOTICE 摆在旁边，commit 与复制日期记进 `LICENSES.md`，**永远不要改 `vendor/` 里面的东西**。上游没有许可证的仓库，一律不 vendor。
- **任何改动之后**，先跑 `lint_content.py`，再跑 `check_parity.py`，先推英文仓再推镜像。两版不会漂成两个项目，全靠这道对齐检查。

## 状态与许可

版本 0.3.1。八道工序、十二个领域包、四份数据字典、三档教学读法、十二个 vendor 上游、两套从真实期刊实测出来的规范，以及每一道工序都能跑的产出或检查器。

库本身是 MIT 许可：Copyright (c) 2026 LW Walker, with dear friends and lovely family。vendor 进来的材料各自保留自己的许可证，许可证、NOTICE 与 commit 记在它旁边的 `LICENSES.md` 里。配套用书是工作讲义，供参考与教学使用，署名同上。
