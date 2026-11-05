# 0002 期刊分层表怎么来的、能信到什么程度

- 日期：2026-11-05
- 状态：生效
- 相关文件：`skills/literature/journals.json`、`_work/verify_journals.py`、`_work/journal_verify.csv`

## 解决什么问题

`litsearch.py` 的 `--min-tier` 要靠刊名判层级（`tier_of()` 拿 Crossref 的 `container-title`
去比对 `journals.json` 里的名字）。这里有两个独立的坑：

1. **名字写错一个字符就判不出来**。`"Economic Journal"` 与 Crossref 实际写法 `"The Economic Journal"`
   不相等，于是《Economic Journal》的文章会被当成 C 级，而它是综合顶刊。
2. **层级本身是价值判断**，没有任何机器能替你判定“这本是不是领域顶刊”。

## 备选方案

| 方案 | 为什么没选 |
|---|---|
| 按名字模糊匹配（相似度阈值） | 会把《Industrial Relations》错配到《Industrial Relations Journal》、把《The World Economy》错配到《Japan and the World Economy》；错配比判不出更糟，因为错配是静默的 |
| 引第三方排名（RePEc、SJR、ABS/AJG） | 都要联网抓取或买数据，且它们的口径与本库“读者投什么刊”未必一致；一旦离线就全失效 |
| 只用 ISSN | 最准，但要人工先给每个刊找 ISSN；而且 `tier_of()` 面对的输入只有刊名，没有 ISSN |
| 名字按 Crossref 官方写法固化，再加机器复核 | **选这个**：离线可用、可复跑、错配会被核出来 |

## 怎么做的

1. `_work/verify_journals.py` 把 `journals.json` 里全部 **142 个刊名**逐个丢给 Crossref
   `GET /journals?query=<名字>&rows=5`，按归一化后的标题比对（转小写、把 `&` 当成 `and`、去标点）：
   完全相等记 `exact`，包含关系记 `fuzzy`，其余记 `nomatch`，结果写 `_work/journal_verify.csv`。
2. `fuzzy` 的逐个人工判断“是不是同一本刊”：是同一本就改写法，不是就留原样（宁可判不出来，
   也不能错配）。**被否掉的三个错配**是：`Industrial Relations` 被错配成 `Industrial Relations Journal`、
   `The World Economy` 被错配成 `Japan and the World Economy`、
   `Economic History Review` 被错配成 `Australian Economic History Review`。
3. 名字搜索仍有 7 个查不到（Crossref 的期刊检索对 `&`、对带 `The` 的短名不友好），
   改用 **ISSN 直接取期刊记录** `GET /journals/<issn>` 确认官方写法：
   `The Economic Journal`（0013-0133）、`Journal of Economic Behavior & Organization`（0167-2681）、
   `Journal of Banking & Finance`（0378-4266）、`Social Science & Medicine`（0277-9536）、
   `Journal of Economics & Management Strategy`（1058-6407）、
   `Journal of Competition Law & Economics`（1744-6414）。
4. `Papers in Regional Science` 特殊：Crossref 的期刊记录保留的是旧名
   `Papers of the Regional Science Association`，但**每条论文的 `container-title` 都是
   `Papers in Regional Science`**（抽查 1978、1993、1996、1999、2011 五条 DOI 全部如此）。
   `tier_of()` 比对的是论文的 `container-title`，所以这里必须写 `Papers in Regional Science`。
5. 最终改了 **16 个写法**：12 个补上 `The`；`The World Economy` 改成 `World Economy`；
   `Industrial Relations` 改成 `Industrial Relations: A Journal of Economy and Society`；
   `B.E. Journal of Theoretical Economics` 改成 `The B E Journal of Theoretical Economics`；
   `Economics of Education` 改成 `Economics of Education Review`。
   去重后仍是 142 个刊名，`journals.json` 版本升到 `2`，两仓逐字节相同。

**结果：135 个名字搜到完全一致，7 个用 ISSN 核过（其中 1 个按论文 `container-title` 确认），
错配 0 个。**

## 能信到什么程度

- **刊名写法**：可以信。每一条都有 Crossref 的机器证据，随时可复跑。
- **A/B 分层本身**：**不能当权威**。它是“综合顶刊加领域主力刊”的人工起点，
  写在这里的作用是给排序加权（A 加 2.0、B 加 1.0、WP 加 0.4），不是给人当评级看。
  换一个系、换一个方向，A/B 名单都会不一样，**改它只需要改 JSON，不用改代码**。
- 名单是否够全：需要各方向的人看一眼（缺口 G6 只关掉了一半：写法可核，分层待议）。

## 代价

- 每加一个新刊，最好跑一次 `python _work/verify_journals.py` 复核；不跑也能用，只是那个刊会被判成 C。
- 只覆盖英文刊。中文刊（《经济研究》《管理世界》《经济学（季刊）》《数量经济技术经济研究》等）
  在 Crossref 里元数据不可靠，本表不含中文刊；中文写作的规范另走
  `skills/tables-figures/overrides/journal-cn.md` 与
  `skills/estimation/overrides/identification-reporting-cn.md`。

## 怎么复跑

```powershell
cd "F:\Deepseek\DocBNU\2026-11-03_经济学科研skill仓库"
python _work\verify_journals.py
```

`--fix` 参数会按“包含关系”自动改名，**不要直接用**：那一步会把上面三个错配写进去。
