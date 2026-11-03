---
name: report
description: 搭一条可复现的报告流水线：从原始数据到中间产物、到表与图、再到渲染出的文档，配固定目录契约、Quarto 骨架，以及共用同一套数字来源的中英双语版本。当报告被手工改、合作者需要一条命令重建、或者同一批结果要出两种语言时进入本 skill。Covers the chain from raw data to intermediate files to exhibits to the rendered document, a fixed directory contract, and bilingual sources driven by one numeric file. 触发词：可复现报告、流水线、目录结构、双语报告、一键重建、数据溯源、reproducible report、build pipeline、Quarto、one-command rebuild。
---

# 可复现报告

## 什么时候进这里

- 合作者改了文档里的一个数字，表就和回归结果对不上了。
- 要给编辑部一份换台机器也能一条命令从原始数据重建的报告。
- 同一批结果要同时出中文报告和英文报告，而且数字必须一致。
- 审稿人问基准表由哪个数据快照、哪次代码提交生成。
- 要把一堆散脚本整理成新助教第一天就能跑起来的目录结构。

## 输入

| 需要什么 | 从哪来 | 缺了怎么办 |
|---|---|---|
| 只读的原始数据 | 数据提供方，放在 `data/raw/` 下，原地永不修改 | 先修数据来源再写流水线代码 |
| 清洗后的中间数据 | `data-prep` 产出的 `data/interim/` | 先跑 `data-prep`；报告不直接读 `data/raw/` |
| 已生成的表与图 | `tables-figures` 产出的 `output/tables/` 与 `output/figures/` | 先建表图；在报告里重画等于把出图代码写两遍 |
| 正文要引用的数字 | `output/estimates/` 下的 JSON 或 CSV | 先抽成 `report/values.json`，再写引用数字的句子 |
| 期刊或模板要求 | 目标刊物的格式说明 | 先用本 skill 的骨架，差异处标 `[待填]` |

## 步骤

目录契约先定下来：`data/raw/` 只读，`data/interim/` 放清洗结果，`output/tables/` 与 `output/figures/` 放生成的表图，`report/` 放文档源文件，`code/` 放脚本，`manifests/` 放溯源信息。

1. 写 `manifests/directory_contract.md`，逐个目录写明负责人、构建时是否写入。完成条件：构建触及的每条路径都出现在契约里，构建不会在契约外新建目录。
2. 写入口 `Makefile`，目标分 `data`、`tables`、`figures`、`numbers`、`report`、`all` 六个，每个目标依赖输入而不是依赖假定的执行顺序。完成条件：`make -n all` 打印出整条链，没有漏掉的手工步骤。
3. 把正文要引用的每个数字抽进 `report/values.json`，一个数字一个稳定键名，来源只读冻结的估计文件。完成条件：在报告源文件里搜三位小数的字面数字，一条都搜不到。
4. 配置 `report/_quarto.yml`：项目类型、输出格式、`execute: freeze`、参考文献路径、模板需要的过滤器。完成条件：清空 `output/` 后渲染一次成功，且零警告。
5. 写英文源文件 `report/report_en.qmd`，只搭小节骨架，表用 include 引入，数字用内联引用指向 `values.json`。完成条件：源文件里没有粘贴的表，也没有手打的数字。
6. 加中文源文件 `report/report_zh.qmd`，与英文源共用 `values.json`、同一批 include、同一批图路径；随语言变化的字符串放进 `report/i18n/en.yaml` 与 `report/i18n/zh.yaml`。完成条件：两次渲染里每个共同数字取值相同。
7. 加 `manifests/provenance.json`，记录数据快照日期、代码提交、以及由锁文件解析出的软件环境。完成条件：每次构建自动重写该文件，无需手工编辑。
8. 做一次干净重建：删掉 `output/`，跑一条命令，与已审阅的产物比对。完成条件：表、图、两份报告全部复现，比对结果无内容差异。

报告必须由脚本生成、不许人手改：手改过的报告是结果的第二份隐形副本。模型之后每改一次，就多出一版真相，而送到编辑手上的那一版恰好是谁也重建不出来的那一版。

## 输出（artifacts）

| 文件名 | 内容 | 给谁用 |
|---|---|---|
| `Makefile` | 构建入口，一个阶段一个目标 | 作者，复现包 |
| `manifests/directory_contract.md` | 目录地图，含负责人与写入规则 | 新助教，审稿人 |
| `report/_quarto.yml` | Quarto 项目配置，执行结果冻结 | 报告构建 |
| `report/report_en.qmd` | 英文报告源文件：骨架、include、内联数字 | 英文报告 |
| `report/report_zh.qmd` | 中文报告源文件，共用同一批数字与表图 | 中文报告 |
| `report/values.json` | 正文引用的全部数字，按名检索 | 两份报告源文件 |
| `manifests/provenance.json` | 数据快照、代码提交、软件环境 | 编辑，审稿人 |
| `build/build.log` | 最近一次完整构建的时间戳日志 | 排错 |

## 验收

- [ ] 从干净检出出发，一条命令重建中间数据、表、图与两份报告，无手工步骤。
- [ ] 报告正文里没有直接手打的数字，每个引用值都能从 `report/values.json` 解析。
- [ ] 构建前后 `data/raw/` 下文件的哈希不变。
- [ ] 中英两份报告里每个共同表图的取值相同。
- [ ] 清空 `output/` 后渲染，零警告通过。
- [ ] `manifests/provenance.json` 写明数据快照日期、代码提交、软件环境。
- [ ] 重建出的表图与已审阅版本一致，若有差异，每条都在 `build/build.log` 里解释。

## 常见失败模式

| 模式 | 表现 | 纠正 |
|---|---|---|
| 数字直接写进报告源文件 | 下次重跑后报告与表对不上 | 数字移进 `values.json`，正文引用键名 |
| 脚本往 `data/raw/` 里写 | 原始快照无法重新下载，已被覆盖 | 原始目录只读，所有改动落进 `data/interim/` |
| 报告与论文各一条出图代码 | 两份产物悄悄分叉 | 报告 include 表文件，绝不重画 |
| 双语版当两份独立文档维护 | 一种语言改了，另一种忘了 | 共用数字与 include，语言字符串放 `i18n/` |
| 构建依赖交互式会话 | 换台机器就重建不出来 | 入口是一条命令，中途不提问 |

## 与其它 skill 的接口

- 上游：`data-prep` 交来 `data/interim/`；`estimation` 交来 `output/estimates/`；`tables-figures` 交来 `output/tables/` 与 `output/figures/`。
- 下游：`writing` 从这里取数字与表图写进稿件；`review` 用溯源文件回答可复现性追问。

## 领域细节去哪查

- 能源与环境：`domains/energy-env/data.md` 查报告必须写明的覆盖年份，以及需要加脚注的数据断点。
- 劳动：`domains/labor/data.md` 查调查轮次与报告必须交代的样本限制。
- 行为：`domains/behavioral/measures.md` 查报告设计小节必须交代的处理变量定义。
