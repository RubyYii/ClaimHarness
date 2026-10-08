# 反馈讨论与连续复查 / Continuous review

本轮实现对应任务说明 PB-01–06、CH-01–06。全部流程在本地运行，默认无模型调用。现有提取器和核查范围保持不变。

## 升级与原有流程

原启动入口、依赖、需求说明流程和核查命令继续使用。旧 schema 1/2 需求记录和已完成核查可由新版读取，更新程序不会自动改写这些历史文件。未使用反馈续谈的需求记录继续保存原字段格式；只有明确确认反馈续谈，才生成 schema 3 新版本。

新核查会额外保存 `audit_snapshot.json`，比较、补标和反馈记录使用新增入口。旧报告没有快照时仅支持有限比较。尚未升级的旧程序不支持 schema 3 续谈记录，也不支持带新增快照的核查包；接收这类新记录的人需要一起升级。旧版的严格字段/文件白名单检查保持有效。

## ProblemBridge：带回反馈

在仓库根目录启动现有工作台：

```bash
python -m streamlit run apps/problem_bridge_wizard.py
```

1. 在“带走说明”中选择“带回反馈继续讨论”。填写反馈来源、对方看到的确认版本和完整反馈原文。普通文本可以选“未知版本”。
2. 选择原文片段，另写自己的理解，并选择目标理解、术语、缺少条件、方法建议或新目标提议。点击“保存反馈，保留当前需求”。这一步不会更改确认需求。
3. 在“讨论并确认”中选择一个问题。候选解释可留空；有实际分歧时可填两种或更多解释。可以选择解释、自己回答、表示“都不准确”、保留未知或暂缓。没有预览也能继续。
4. 已有回答使用“更正先前回答”，填写更正原因。达到本轮回答次数上限后，未回答事项仍在记录里；不会自动采用某种解释。
5. 选择补充信息、更正回答或改变目标，填写依据与接收方下一步。只有“我确认本次更新”才建立新需求版本。改变目标必须明确填写新目标，不用补充说明替换原目标。
6. 两份双语说明都读取这一确认版本，附上本轮回答、未决问题、版本变化和下一步。可单独下载研究讨论输入交给 AWT；系统不会发送。

讨论在运行目录旁的 `.continuity/` 中保存。刷新、退出后可从原需求继续；可下载完整讨论 JSON，包括反馈原文及其目标版本。界面保留提交时看到的修订号；另一个页面写入新记录后，旧页面提交会被拒绝，需要载入新记录再决定。

内置“平均口径示例”实际执行已有的合成数据适配器，显示输入、执行方式及输出。它用于解释差异，不是用户材料的预览。普通反馈中的后果判断标为尚未验证。`Preview.kind` 区分 `execution`、`example`、`inference`；示例与推测不进入实际执行差异计算。执行失败、缺少执行或无法比较继续保留未知，样例结果相同不证明两种理解等价。没有新增任意代码执行接口。

## ClaimHarness：修改后复查

先完整重跑核查，再到“处理核查发现”的“比较两次核查”选择上一轮和当前轮，明确勾选属于同一任务。也可以独立启动，无需先建立 ProblemBridge 需求：

```bash
python -m streamlit run apps/claim_compare.py
```

选择包含核查子目录的目录，如 `outputs` 或 `outputs/continuity_demo/runs`。

- **可比性**：检查完成标记、运行身份和文件哈希。缺失或损坏的受管记录阻止正常比较。无生命周期记录的旧报告仅有限展示，身份与完成性标为未验证。
- **声明对应**：只将有原文依据的唯一相同句子自动对应；允许空白排版变化，不删除数字、单位、否定或限定词。同句重复时使用唯一相邻上下文，仍有歧义则留待确认。
- **改写与拆合**：在两边各选一条或多条声明，写明对应依据后保存；可清空手工对应，历史仍保留。没有模糊匹配自动接受。
- **变化原因**：原句不再逐字出现（删除或改写待对应）、原句仍在但未被提取、材料变化和规则变化分别呈现。CSV 给出行列坐标及旧新值；重排后的行不被推断为同一实体。删除或未再提取都不表示证据缺口修复。
- **原文补标**：对照带行号的保存原文和已提取位置，粘贴遗漏原文，重复片段需指定出现次序，填写人工问题及候选证据。中文和当前范围外内容保存为 `not_evaluated` / `needs_human_review`，不自动验证。
- **逐条处理**：程序结果、用户计划/行动、注明来源的人工意见分开显示和保存。可以关联已完成的新一轮核查，显示对应声明及新判断供用户对照。此处不核验复核者身份或资格。
- **切换版本**：未保存的补标和处理表单会清空，避免把上一版的文字或计划写入另一版。先保存需要保留的记录，再切换核查。
- **导出**：`audit_changes.md`、`audit_changes.json`、`pending_questions.md`；可选 `research_questions.md`。手工记录另存于 `.continuity/`，下载比较时可附带，不修改原始报告。

新运行增加 `audit_snapshot.json`：原文、CSV、参考文字、原始输入哈希与核查组件代码哈希。保存文本采用 UTF-8 解码和统一换行；原始文件哈希、文本哈希及换行规则分别记录。标注偏移针对快照中的文本。旧报告缺少快照时，不反推删除、不伪造新增字段。提取位置列表不代表全文覆盖率，零提取也不表示全文通过。

## CLI

所有命令在仓库根目录运行，输出目录须是新目录。

```bash
python -m claim_harness compare --previous outputs/before --current outputs/after --same-task --out outputs/comparison --research-questions --workspace outputs
```

`--same-task` 是用户对比较任务与文档延续关系的明确确认。缺少此确认或运行无效时，仍导出阻止比较的原因并以非零码退出。材料变化与核查代码、证据要求变化分别记录。`--workspace` 可选，包含该工作区中针对这些运行的补标和处理历史。

改写或拆合对应使用 `--mappings mappings.json`，每项格式为：

```json
[
  {"previous_ids": ["C001"], "current_ids": ["C002", "C003"], "reason": "用户确认原句被拆成两句，并说明具体依据"}
]
```

ID 只在各自运行内有效；每个声明只能属于一组手工关系。无效、重复或有重叠的映射会被拒绝。

```bash
python -m claim_harness annotate --run outputs/after --workspace outputs --start 10 --end 30 --question "这段文字需要什么证据？" --expected-revision 0
python -m claim_harness record-action --run outputs/after --workspace outputs --claim-id C001 --note "向材料提供者确认表格版本" --action planned --expected-revision 1
```

`start` 从 0 开始，`end` 不包含在片段内；偏移是 `audit_snapshot.json` 的 `manuscript.text` 字符位置。人工意见另加 `--layer human_review --actor 姓名 --source 来源与材料版本`。处理完成使用 `--action done` 只保存用户陈述。关联重跑结果可加 `--rerun outputs/new_run --same-task`。修改使用当前 journal 修订号，旧号不覆盖新记录。

## 合成示例

```bash
python scripts/run_continuity_demo.py --out outputs/continuity_demo
```

示例包含反馈选段、明确回答、确认新版说明、两次真实 mock 核查、文首插入、数值改写、删除过强表述、证据单元格变化、中文遗漏补标、用户处理记录及可选 AWT 输入。重跑时选择新目录。

ProblemBridge → AWT 的输入保留原始问题、当前目标、条件、未知项、决定与版本。ClaimHarness → AWT / ProblemBridge 的输入保留具体声明、证据缺口、原文位置、核查范围及需要向材料提供者确认的问题。普通反馈文本不要求带项目标识；没有的信息保持未知。没有常驻同步、自动联系或自动全文科学验证。

## Engineering boundary

Synthetic regression, integrity checks and UI screenshots verify implemented behaviour only. They do not establish reduced real-world misunderstanding, better scientific review, reviewer qualification, clinical validity or research value. `.continuity` contains user-authored records: keep it with the workspace for continuation, and inspect it before sharing.
