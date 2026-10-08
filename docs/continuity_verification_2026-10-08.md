# 连续反馈与复查：实现及验收记录

日期：2026-10-08。验收基线 HEAD：`836b24c4a`。以下记录对应本轮功能提交前的本地检查；最终代码身份以收录此文件的 Git 提交为准。保留了开始工作前已有的无关修改和研究文件。

## 已实现的路径

| 范围 | 实现入口 | 验证依据 |
|---|---|---|
| PB-01–02 | `problem_bridge/feedback.py`、`feedback_ui.py`，复用 `clarification.py` | 原文与选段、来源、目标版本、未知/暂缓、开放问题、刷新后继续、旧修订拒绝 |
| PB-03 | `Preview.kind` 与现有合成平均适配器 | 示例和推测不参与实际执行差异；相同样例结果不关闭问题 |
| PB-04–05 | `confirm_discussion`、`workbench.py`、`handoff.py` | 更正历史、明确目标变化、不可变新版本、双语双交接、可选研究输入 |
| CH-01–03 | `run_records.py`、`comparison.py`、`apps/claim_compare.py` | 完整性/身份/规则快照、唯一原句及上下文匹配、显式改写与拆合、输入和单元格变化 |
| CH-04–06 | `handling.py`、`continuity_ui.py`、CLI、报告查看器 | 保存原文位置、中文遗漏补标、分层处理记录、关联重跑、Markdown/JSON/待办导出 |

使用步骤见 [continuous_review.md](continuous_review.md)。首版复用现有核查范围，没有扩大自动学科验证范围。

## 测试结果

- 完整回归记录：`.local/continuity_final_suite.log`，**561 passed, 3 failed**。这不是全绿结果。
- 其中两个发布 ZIP 测试的临时虚拟环境位于仓库内，被既有隔离检查判为源码泄漏。使用新的系统临时目录重新运行原测试，**2 passed**：`.local/continuity_release_recheck.log`。未修改测试断言或发布脚本。
- 最终源代码的新增回归：`tests/test_audit_continuity.py`、`tests/test_feedback_continuity.py`、`tests/test_continuity_ui.py`，**18 passed in 28.66s**：`.local/continuity_final_confirmed.log`。使用新的系统临时目录，避免本机仓库内临时目录偶发的 Windows 重命名拒绝；未放宽产品写入或版本检查。
- UI 测试实际操作反馈录入、关闭后重开、更正、语言切换、新版确认、遗漏补标、处理记录及核查版本切换。额外检查页面没有显示保存错误，切换运行后不携带未保存的补标/处理表单，声明标题绑定当前运行。
- 仍存在的整仓失败：`test_no_secrets_or_absolute_local_paths_in_project_text`。97 个命中文件均与 HEAD 内容相同，匹配在 HEAD 中已经存在。已保留原检查和历史文件，没有扩大豁免。只记录文件名、匹配类别和哈希，不复制匹配内容：`.local/continuity_existing_release_failure.json`。

因此本轮新增流程的定向检查通过，整仓发布门禁仍有上述既有失败，不能声称全部 pytest 已通过。

## 可运行的合成交付

```bash
python scripts/run_continuity_demo.py --out outputs/continuity_demo_new
```

已生成的实例位于 `outputs/continuity_demo/`。其 `demo_result.json` 记录零外部模型调用、两轮真实 mock 核查及可比较状态。四份双语交接说明和研究输入从确认记录生成；比较包包含 `audit_changes.md`、`audit_changes.json`、`pending_questions.md`、`research_questions.md`。原运行保持完整，不靠修改旧报告生成差异。

标准 lab-report mock 命令也已运行于新目录 `outputs/continuity_lab_report_audit_demo_run/`，包含五个规定输出及新增 `audit_snapshot.json`。已有 `outputs/lab_report_audit_demo_run/` 未被覆盖。

## 浏览器与独立建议

实际浏览器验证使用本地合成数据。ClaimHarness 使用真实独立应用；ProblemBridge 截图使用调用真实 `render_feedback` 的合成组件预览，完整工作台流程另外由 AppTest 验证。

- 截图在 `.local/continuity_screenshots/`，包含前后声明、数值差异、旧反馈版本提示、未知影响和明确确认表单。
- 浏览器实际保存了示例的旧 C001 → 新 C002 改写对应，再次打开后能够读取。位置插入不被当作声明身份。
- Gemini 3.5 Flash 给出了设计草案、计划/代码建议和截图审查。设计与计划结果保存在 `.gemini-agent/continuity-*.json`；设计目录为 `.gemini-agent/design/20261008T134100522Z-0srj9b5b/`。
- 已落实确认失败保留与重试、运行切换后的控件身份、元数据可读性和确认输入示例。代码审查提出的 CSV 行号类型问题，经当前证据映射覆盖逻辑和重复原句上下文测试核对，不适用于当前实现。
- Gemini 只收到通用需求、限定的非敏感应用代码和合成界面图；没有发送已有研究目录、私密材料或凭据。建议、截图检查和哈希检查均不等于科学结论、真实用户验证或复核者资格认证。

最终截图审查结果另见 `.gemini-agent/continuity-visual-claim-final.json` 和 `.gemini-agent/continuity-visual-feedback-final.json`。

两份最终 Gemini 截图建议均为 `caution`，不是视觉全通过证书。针对它提示的元数据/提示条对比度，读取最终浏览器 DOM 的实际颜色并计算得 12.01:1 与 6.26:1；结果保存于 `.local/continuity_screenshots/contrast_observation.json`。正常滚动后已看到全部三个下载按钮，证据为 `claim_compare_footer.jpg`。红绿差异区域仍使用 Streamlit 原生配色，同时保留 `-`/`+` 标记和上方完整旧新原句，不仅依赖颜色传达变化。这些检查覆盖所截桌面界面，没有宣称完整无障碍或全设备认证。

最终 `git diff --check` 通过。源代码、日志、截图与本记录的哈希清单保存于 `.local/continuity_delivery_manifest.json`；它用于本地交接身份核对，不替代上述测试和未通过事项。

## Git 交付内容

提交收录功能源码、必要的澄清模块与适配器、配套测试、合成示例输入和使用文档。合成界面截图与可移植验收摘要位于 [continuity_evidence_2026-10-08](continuity_evidence_2026-10-08/README.md)。原始本地日志、模型建议、运行目录及无关研究资料不随本轮提交上传；上文的本地路径是原验收记录的位置，不表示它们包含在 Git 中。可使用文档中的命令重新生成示例输出。

上传前从 Git 暂存区导出独立源码副本，运行连续流程、澄清依赖、交接说明和工作台回归：**55 passed in 156.72s**。标准 lab-report mock 命令和连续流程合成示例均在该副本内重新执行成功，规定输出齐全；日志为 `.local/continuity_staged_validation.log`。限定范围的暂存差异扫描未发现新增密钥或本机路径匹配，Gemini 提交前代码审查为 `pass`；它保留了对并发和保守原句匹配的普通建议，没有要求扩展语义匹配。该独立副本检查不替代上文仍失败的整仓检查。
