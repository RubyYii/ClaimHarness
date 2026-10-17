# 已确认要求的交接与验收 / Requirement traceability

这条本地流程把用户明确选取的原话、确认版本、交接位置和验收记录连起来。它不自动抽取完整需求，不判断研究价值，也不验证任意专业输出。四份交接说明会带上已选要求。除下方 CLI 外，现在也可在“[双向交接 → 样例与检查](two_way_handoff.md)”中选取、重新确认或撤回要求，并记录小样例检查。

## 完整合成示例

从仓库根目录运行，输出目录必须尚不存在：

```bash
python -m problem_bridge requirements-demo --out outputs/requirements_demo
```

打开 `outputs/requirements_demo/workspace/review/requirement_trace.md`。样例选取三个要求，定位四份双语交接说明中的相应片段，实际生成两种平均方式的 CSV，并保存两次注明来源的验收记录。每个传感器等权时 North 的平均值为 22；按观测次数加权则为 18。其他两个要求保留 `not_checked`。

样例全部是合成材料，验收记录由脚本填写并注明来源，没有模型调用或真人评估。它演示记录机制，不证明系统能自动判定任意要求，也不证明真实协作收益。

## 选取已确认原话

先在现有工作台确认需求。下列 `PROJECT`、`RUN` 和修订号须替换为实际记录值；`RUN` 是 `outputs/ui_runs` 下的一次已完成运行目录名。

```bash
python -m problem_bridge requirement-sources --workspace outputs/ui_runs --run outputs/ui_runs/RUN --project-id PROJECT
```

命令打印当前需求修订号和可选原话，包括目标、期望结果、边界、材料、术语和最近一轮已确认回答。未采纳的合作者或模型建议不在来源清单内。

把选取结果保存为 UTF-8 JSON，例如 `outputs/requirement_selection.json`：

```json
{
  "select": [
    {
      "source_key": "desired_change",
      "quote": "每个传感器等权计算平均值。",
      "acceptance": "对一个记录次数不同的小样例手算，再对照交付结果。"
    }
  ]
}
```

`quote` 必须逐字出现在指定来源中。重复文字需增加 `start`，填写从 0 开始的字符偏移，针对 `requirement-sources` 返回的字符串。不会通过模糊匹配替用户选择。验收方法尚未知时可留空。

```bash
python -m problem_bridge confirm-requirements --workspace outputs/ui_runs --run outputs/ui_runs/RUN --project-id PROJECT --changes outputs/requirement_selection.json --expected-revision 1 --confirm
```

这里的修订号是**需求记录修订号**。`--confirm` 表示用户确认本次选取；没有该参数不会生成新版本。命令返回新运行目录，旧目录保持不变。

新目录包含四份交接说明，以及：

- `requirement_trace.json`：要求 ID、精确原话、来源版本与偏移、来源记录哈希、验收方法、四份交接文件的行号和哈希。
- `requirement_trace.md`：同一记录的可读版本。

标识只表示已选要求，不代表全部需求已被发现。新原话获得新 ID，相同原话的重新确认沿用旧 ID。

## 记录验收并导出

把交付文件放在工作区内，例如 `outputs/ui_runs/deliverable.csv`，选择新版本中的实际要求 ID：

```bash
python -m problem_bridge record-requirement-check --workspace outputs/ui_runs --run outputs/ui_runs/NEW_RUN --project-id PROJECT --requirement-id R-0123456789ab --result met --actor "需求方" --method "对照手算结果" --note "检查指定样例的平均口径" --artifact deliverable.csv --location "North 行的 mean 列" --expected-revision 0
python -m problem_bridge export-requirements --workspace outputs/ui_runs --run outputs/ui_runs/NEW_RUN --project-id PROJECT --out outputs/ui_runs/requirement_review
```

这里的修订号是**验收日志修订号**，独立于需求修订号，首次为 0；提交后返回新号。旧号提交会被拒绝。导出目录必须是工作区内尚不存在的直接子目录。

`met` / `not_met` 必须带本地证据文件和明确位置。`not_checked` 表示尚未检查，可不带文件。每次记录填写者、方法和说明；填写者身份、专业资格、所填位置及判断本身不经过自动验证。文件哈希只标识材料版本。单个证据文件上限 10 MB，不接受工作区外路径或链接路径。

追加记录存于工作区的 `.continuity/`，不会改动旧交接包、CSV 或 ClaimHarness 判断。导出 JSON 包含完整验收历史，Markdown 展示每条要求的最新记录。再次导出会检查证据文件：改变、缺失或不可读时，旧结果仍可见，但 `applicable` 为 false。

## 需求变化与撤回

- 目标、条件、术语或已确认讨论变化后，原来确认的要求保留并标为 `needs_reconfirmation`。
- 重新选取相同原话并附上 `requirement_id`，才能恢复为 `confirmed`；同时重写本次验收方法，或显式留空为未知。
- 原话变化时，明确撤回旧 ID 并选取新原话，不能借旧 ID 悄悄替换文字。
- 未出现在本次选取列表中的既有要求继续保留。撤回必须有理由，例如：

```json
{
  "retire": {"R-0123456789ab": "用户改变了输出范围，此要求不再适用。"},
  "select": [{"source_key": "desired_change", "quote": "新的已确认原话。"}]
}
```

验收日志绑定具体运行、需求修订和内容哈希。即使下一版文字相同，也不会自动继承旧版验收结论。可以在历史版本上补充记录，但它们仍属于那个版本。单纯执行已有核查不会自动验证已选要求。

## 提问方式

交给模型的提示要求先查可访问材料并注明位置，再对前提已经明确的未决选择提出最多三个问题，说明答案如何影响结果。推荐答案仍是建议，未知和暂缓继续有效。这是交接指令，当前没有新增自动问题依赖图或自动访谈能力。

## English summary

Select exact spans from a confirmed ProblemBridge record with explicit confirmation. Version 4 retains stable requirement IDs, source locations and hashes, acceptance notes, and actual line locations in all four handoffs. Versions 1–3 remain readable without changing their framing digests.

Attributed checks are stored separately and bound to one exact run and revision. Evidence hashes detect changed materials; neither hashes nor a reported `met` result establish professional validity. Changed framing requires reconfirmation. Retirement is explicit and does not count as satisfying a requirement. Coverage remains unknown and ClaimHarness verdicts stay independent.
