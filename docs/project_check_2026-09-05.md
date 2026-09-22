# 2026-09-05 项目检查与整理记录

本地确定性流程可以运行。本轮完成目录归档、使用说明整理、发布测试修复和样例补齐。
声明抽取仍存在覆盖缺口；测试通过不能解释为审计有效性或发布认证。

检查基于本地分支 `codex/build-week-2026`，基准提交为
`4cb7f6c1b9114c3422a0f59a169d17cbb8462583`，加上本轮未提交的维护改动。
版本为 `0.4.0`，本地解释器为 Python `3.12.14`。

## 已完成的整理和修复

| 项目 | 处理结果 |
| --- | --- |
| 文档入口分散 | 新增 [项目目录与文档索引](project_map.md)，中英文 README 均提供入口 |
| README 重复安装和打包说明 | 合并重复段落，保留完整启动、故障处理和发布步骤 |
| 命令混用 shell 语法 | 修正 README 与演示指南中的 PowerShell 代码块和续行符，补充已有输出目录的保护规则 |
| 空的通用样例目录 | 补齐 `examples/general_demo/` 的稿件、参考说明和 CSV，使用虚构文档分流数据 |
| 发布测试日志读取失败 | 明确 UTF-8 解码并替换无法解码的诊断字节，防止 Windows 混合编码使子进程读取线程崩溃 |
| 依赖冲突被误当成离线 | 跳过发布安装检查必须有具体连接失败信息；`ResolutionImpossible` 和缺少发行版本本身不再触发跳过，新增 3 个回归用例 |
| 根目录历史临时文件过多 | 将 96 个旧 pytest 目录、4 个临时工具或预览项、1 份旧主演示结果移入本地归档，共 101 项 |

`.gitignore` 新增 `/.local/`，用于本机维护记录与归档。当前检查用的
`.pytest_tmp_project_check/` 保留在根目录；正常测试仍使用配置中的 `.pytest_tmp_run/`。

归档路径是 `.local/archive/2026-09-05-project-check/`，其中
`restore_manifest.json` 保存原路径、归档路径和状态。归档未删除文件，也不会减少磁盘占用。
旧主演示保存在该归档的 `outputs/lab_report_audit_demo_run/`，根目录 `outputs/`
下的同名目录现在是本轮新运行结果。

## 本轮验证结果

| 检查 | 结果 |
| --- | --- |
| 全量 pytest | **444 passed, 2 skipped**，退出码 0；109.16 秒 |
| 当前环境 `pip check` | `No broken requirements found` |
| AGENTS.md 指定的主审计命令 | 成功；16 条声明、3 条 supported、13 条尚未满足放行条件；5 个规定输出和其余运行记录齐全 |
| ProblemBridge 内置演示 | 成功；质量检查工作流对齐包及完成记录已生成 |
| Build Week mock 演示 | 成功；3 条能力声明分别为 supported、weakly_supported、overclaimed；`gpt_5_6_used: false` |
| 新增通用审计样例 | 成功；4 条声明，2 supported、1 unsupported、1 weakly_supported |
| 完成记录与哈希 | 4 份本轮最终演示包和 4 份已提交展示样例全部通过 `load_run_completion` 检查 |
| 原有工作区材料 | 展示图及 `release/`、`submission/`、`codex_outputs/` 中共 13 个已有文件，检查前后 SHA-256 一致 |

首轮全量测试为 441 passed、2 failed。两个失败源于发布测试的混合编码日志读取。
修复后，真实日志表明净虚拟环境安装无法连接包索引，因此这两项被明确记录为跳过。
它们分别检查解压后运行两个内置演示，以及缺少 Python 模块时拒绝发布。
**净环境安装和完整发布 ZIP 冒烟检查在本轮仍未验证。**

发布测试的 ASCII 阶段标记用于断言；对无法解码字节的替换仅用于诊断日志读取，
不用于稿件、证据或输出文件的内容处理。其余数值和文档编码流程未改变。

Gemini `gemini-3.5-flash` 对不含源码或私有文件的简短维护摘要提供了建议，
重点提示离线识别、历史路径引用和日志解码边界。这是摘要级辅助意见，未执行源码
独立复核或视觉验收。本轮没有修改工作台 UI 或原有展示图。

## 仍需优先处理的问题

1. **抽取覆盖缺口。** 现有 7 条英文合成 gold 记录中抽取了 5 条，precision 为 1.0，
   recall 为 0.714286，F1 为 0.833333。`Macro F1 was 0.88 on the synthetic benchmark.`
   和 `The model is safe for oncology triage.` 未被抽取。3 条高风险 gold 声明中漏掉 1 条，
   高风险漏检率为 0.333333。下一轮应独立处理隐式数值声明和安全表述，并验证否定、
   引述及非声明句，避免仅向关键词表添加词语就宣称覆盖完整。
2. **数值冲突解释仍不充分。** 新通用样例声称 precision 从 0.76 提高到 0.95，
   表中比较模型实际为 0.86。当前输出为 `weakly_supported`，理由是缺少表格支持，
   并未给出明确的矛盾证据 ID。该声明仍被阻止放行，但定位差异的解释需要改进。
3. **发布结果需另行生成和验证。** 本轮保留原有未提交材料，未提交 Git、重建正式 ZIP
   或进行平台提交。现存 `release/verification_report.md` 指向较早提交，应按其日期和
   哈希理解；当前源代码检查结果不能代替旧包的重新构建与检查。

本轮合成评估的 status macro-F1 为 0.866667，unsafe high-risk decision rate 为 0。
后者不能抵消漏抽高风险句子的事实。这 7 条记录只用于有限回归检查，不支持真实场景、
中文审计或临床有效性的结论。

## 复查入口

```powershell
.venv\Scripts\python.exe -m pytest -q -rs
.venv\Scripts\python.exe -m pip check
```

主审计结果位于 `outputs/lab_report_audit_demo_run/`。再次运行主演示时应使用新的
`--out` 目录，或按身份确认的生命周期规则操作。

其余本轮本地证据位于 `.local/project-check-2026-09-05/`：

- `problembridge_demo/`、`build_week_demo/`、`general_demo_verified/`
- `evaluation/evaluation_metrics.json`、`evaluation/evaluation_report.md`
- `integrity_check.json`、`preserved_files_before.json`
- `pytest.xml`

这些本机文件不随 Git 克隆分发。需要共享时，应选择对应生成物并检查内容；
不要把整个 `.local/` 归档当成发布包。
