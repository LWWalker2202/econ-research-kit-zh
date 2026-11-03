---
name: mgmt-paper-journal-figures
description: 面向管理学、经济学、金融学和跨学科期刊的投稿级图表生成与审查 Skill。按目标期刊生成图表规格，支持 Nature / Management Science / Journal of Finance / 管理世界等风格，强调矢量 PDF、字体嵌入、色盲友好、黑白可读、多面板布局、图注和可复现脚本。当用户需要特定期刊图表、Nature 级图形质量、或 Codex/Claude 协同生成和审查图表时调用。
tags: [figures, journal, nature, management-science, matplotlib, stata, python, codex, claude]
version: 0.1.0
author: MGMT-Paper-Skills Contributors
license: Apache-2.0
display_name: "MGMT - Paper - Journal Figures"
---

# MGMT - Paper - Journal Figures — 期刊级图表工作室

## 核心原则

图表不是装饰。投稿级图表必须让审稿人更快理解研究设计、识别策略、机制或主要发现。

## 工作流

1. 明确目标期刊和图表目的。
   - 目标期刊：Nature / Management Science / Journal of Finance / 管理世界 / 经济研究等。
   - 图表功能：研究设计、主结果、机制、稳健性、理论框架、Graphical Abstract。
2. 读取 `references/journal-profiles.md` 和 `references/nature-level-checklist.md`。
3. 选择生成路径。
   - 数据图：优先 Python/matplotlib，必要时 Stata/R 输出数据再由 Python 统一排版。
   - 回归图：Stata `coefplot` / Python `matplotlib` 双路线。
   - 概念图：先 Mermaid 草图，再 Python/TikZ 定稿。
4. 生成可复现脚本和矢量 PDF。
5. 做质量门检查：灰度可读、色盲友好、字体嵌入、线宽、字号、图注、面板标识、无视觉欺骗。

## Codex + Claude 协同

- Claude：提出图表叙事、panel 设计、图注草稿。
- Codex：生成脚本、运行本地 Python/Stata、导出 PDF/SVG、检查文件。
- 双方都不能编造数据；缺数据时只生成模板或 mock 示例，并明确标注。

## 输出

返回：

1. 目标期刊图表规格。
2. 图表类型和面板结构。
3. Python/Stata/R 生成路径。
4. 可复现脚本位置。
5. 图表质量门结果。
6. 审稿人可能质疑点。
