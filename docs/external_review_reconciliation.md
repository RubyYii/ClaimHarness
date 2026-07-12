# 外部审查问题对照与当前实现边界

本页把一次完整仓库审查提出的 14 类问题，与当前 v0.4.0 源码逐项对照。它是能力声明校准记录，不是算法有效性证明，也不把计划中的功能写成已经实现。

状态含义：

- **已完成**：审查指出的具体缺陷已有代码、测试或明确产品措辞支撑。
- **部分完成**：已有可运行的受限实现，但审查要求的完整闭环尚未实现。
- **未完成**：当前仓库没有足够实现或验证证据。
- **明确延期**：边界已公开，只有达到后续版本的验收门槛才会启用。

## 产品真相

- ProblemBridge 是确定性的 profile/template workflow-alignment baseline，会继承引导表单字段，但不会自动理解或重建任意领域工作流。
- ClaimHarness 是 English-first 的 rule-based claim-evidence screening baseline。检索结合词法候选与表格实体、指标、数值关系；验证是保守的 contract-aware 规则筛查，不是事实或语义证明。
- 远程 LLM 只在确定性审计后生成可选 advisory summary，不参与 claim extraction、evidence retrieval 或最终状态判定。
- 中英双语界面是展示与引导能力，不代表中文 claim 审计已经验证。
- 所有专业结论仍由合格人员负责；`human_review_queue.json` 只是 pending work，不是批准记录。

## 14 类问题逐项对照

| # | 审查问题 | 当前状态 | 代码或文档证据 | 当前边界与剩余工作 |
| --- | --- | --- | --- | --- |
| 1 | 产品描述领先于实际算法 | **已完成** | [`pyproject.toml`](../pyproject.toml)、[`README.md`](../README.md)、[`README.zh-CN.md`](../README.zh-CN.md)、[`problem_bridge/generator.py`](../problem_bridge/generator.py)、[`claim_harness/claim_extractor.py`](../claim_harness/claim_extractor.py) | 包元数据和双语 README 现在明确写成 deterministic workflow alignment 与 rule-based screening；仍是 portfolio prototype，不声称科学验证系统。 |
| 2 | ProblemBridge 与 ClaimHarness 没有真正契约闭环 | **部分完成** | [`problem_bridge/writer.py`](../problem_bridge/writer.py)、[`claim_harness/evidence_contract.py`](../claim_harness/evidence_contract.py)、[`claim_harness/cli.py`](../claim_harness/cli.py)、[`claim_harness/verifier.py`](../claim_harness/verifier.py)、[`apps/problem_bridge_wizard.py`](../apps/problem_bridge_wizard.py) | CLI 已可用 `--evidence-contract` 读取、校验并执行 schema-v2 契约，也会保存规范化快照；Streamlit 工作台仍只能查看既有审计包，不能直接运行 ClaimHarness。 |
| 3 | claim 可能被同一句 Results 文本自我支持，表格关系过宽 | **已完成** | [`claim_harness/evidence_retriever.py`](../claim_harness/evidence_retriever.py)、[`claim_harness/verifier.py`](../claim_harness/verifier.py)、[`tests/test_core_integrity.py`](../tests/test_core_integrity.py)、[`tests/test_audit_enhancements.py`](../tests/test_audit_enhancements.py) | 相同文本以及同一来源位置的近重复 claim span 被排除，不会误删同一行的独立句子；Discussion 普通叙述被标为 narrative assertion；强表格支持需要可验证的实体/指标/数值关系。规则仍不等同于完整语义、研究设计或因果判断。 |
| 4 | `requires_evidence`、风险、人工复核与发布边界没有进入判定 | **已完成** | [`claim_harness/schemas.py`](../claim_harness/schemas.py)、[`claim_harness/verifier.py`](../claim_harness/verifier.py)、[`claim_harness/report_generator.py`](../claim_harness/report_generator.py)、[`claim_harness/review_queue.py`](../claim_harness/review_queue.py)、[`claim_harness/diagnostics.py`](../claim_harness/diagnostics.py) | 验证器执行内置或契约要求，并把 `human_review_required` 与 `release_allowed` 作为独立字段输出；schema 级不变量阻止 high-risk 或待复核结果自动放行，诊断与队列语义版本已升级。系统不能确认人员资质或记录正式批准。 |
| 5 | 中文界面与 English-first 核心算法不一致 | **明确延期** | [`apps/problem_bridge_wizard.py`](../apps/problem_bridge_wizard.py)、[`claim_harness/claim_extractor.py`](../claim_harness/claim_extractor.py)、[`claim_harness/evidence_retriever.py`](../claim_harness/evidence_retriever.py)、[`claim_harness/eval_data/gold_claims.jsonl`](../claim_harness/eval_data/gold_claims.jsonl)、[`README.zh-CN.md`](../README.zh-CN.md) | UI 已双语，OCR 可调用本地中文语言包；profile detection、claim cues、token matching 与 gold set 仍以英文为主。中文审计只有在版本化中文 gold set 达到明确门槛后才计划进入 v0.6。 |
| 6 | UI 的 provider 选择容易让人误以为会改变 ProblemBridge/验证 | **已完成** | [`apps/problem_bridge_wizard.py`](../apps/problem_bridge_wizard.py)、[`claim_harness/cli.py`](../claim_harness/cli.py)、[`claim_harness/llm.py`](../claim_harness/llm.py)、[`MODEL_PROVIDER_GUIDE.md`](../MODEL_PROVIDER_GUIDE.md) | 工作台明确为 deterministic mock-only，不提供远程 provider 设置；远程 provider 仅属于 ClaimHarness CLI 的 advisory summary，不能改变确定性结果。 |
| 7 | API key 被写入进程环境，不能准确称为 session-only | **已完成** | [`apps/problem_bridge_wizard.py`](../apps/problem_bridge_wizard.py)、[`problem_bridge/ui_memory.py`](../problem_bridge/ui_memory.py)、[`tests/test_ui_memory.py`](../tests/test_ui_memory.py)、[`claim_harness/cli.py`](../claim_harness/cli.py) | 当前工作台不接收 API key，也不会写入 `os.environ` 或本地记忆。CLI 可从启动环境读取 provider 凭据，但项目不支持多用户 hosted deployment；如未来托管，需重新设计每请求的 secret 隔离。 |
| 8 | URL intake 的 SSRF/MIME 边界与文件资源限制不足 | **部分完成** | [`problem_bridge/document_intake.py`](../problem_bridge/document_intake.py)、[`tests/test_document_intake.py`](../tests/test_document_intake.py)、[`docs/limitations.md`](limitations.md) | URL 已限制公共 HTTP(S)、拒绝凭据与非公网地址、固定已校验 IP、逐次检查 redirect、禁止 HTTPS 降级、限制响应大小并检查最终 MIME；可分享 provenance 只保留最终来源 origin，不保存路径/query/fragment。OCR 有字节/页数/像素/时间限制；通用上传大小、DOCX 解压预算、非 OCR PDF 页数预算以及 URL 获取的全局 deadline/IP fan-out 上限仍未形成完整沙箱。 |
| 9 | 产品命名、Python 包版本与发布 ZIP 版本不一致 | **已完成** | [`pyproject.toml`](../pyproject.toml)、[`claim_harness/__init__.py`](../claim_harness/__init__.py)、[`problem_bridge/__init__.py`](../problem_bridge/__init__.py)、[`scripts/build_release_zip_powershell.ps1`](../scripts/build_release_zip_powershell.ps1)、[`scripts/test_release_zip_powershell.ps1`](../scripts/test_release_zip_powershell.ps1) | 产品名统一展示为 ProblemBridge + ClaimHarness，版本为 0.4.0，发布脚本从 `pyproject.toml` 推导版本。Python distribution name 有意保留为 `claim-harness`，未进行破坏性改名。 |
| 10 | trace 不足以支撑完整可重放审计 | **部分完成** | [`claim_harness/audit_logger.py`](../claim_harness/audit_logger.py)、[`claim_harness/run_records.py`](../claim_harness/run_records.py)、[`claim_harness/report_generator.py`](../claim_harness/report_generator.py)、[`problem_bridge/project_lifecycle.py`](../problem_bridge/project_lifecycle.py) | 现有记录包含时间、run/project ID、工具版本、输入/输出哈希、provider 公共信息、run-spec 哈希、契约身份，以及每项 verdict 的 reason、修订建议和证据 ID；claim/evidence 关联原因保存在 evidence map。尚未固定 git commit、独立 rule-set version，也没有把每个候选关系的全部结构化判定特征记录成可执行 replay。 |
| 11 | CI、release smoke test 与 YAML 校验覆盖薄弱 | **部分完成** | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)、[`scripts/build_and_test_release_powershell.ps1`](../scripts/build_and_test_release_powershell.ps1)、[`scripts/test_release_zip_powershell.ps1`](../scripts/test_release_zip_powershell.ps1)、[`problem_bridge/writer.py`](../problem_bridge/writer.py) | CI 已覆盖 Ubuntu 3.10/3.12、Windows 3.12、`.[dev,ui]`、wheel 和 Windows ZIP clean-environment demo。仍缺 Python 3.11、lint/type/coverage/dependency-audit 门；ProblemBridge YAML 仍由受测的本地 serializer 生成，尚未迁移到标准 YAML serializer + schema round-trip。 |
| 12 | 缺少算法有效性与真实用户有效性证据 | **部分完成** | [`claim_harness/evaluation.py`](../claim_harness/evaluation.py)、[`claim_harness/eval_data/gold_claims.jsonl`](../claim_harness/eval_data/gold_claims.jsonl)、[`tests/test_evaluation.py`](../tests/test_evaluation.py)、[`USABILITY_TEST_PLAN.md`](../USABILITY_TEST_PLAN.md) | 已有小型、版本化、离线 English-first synthetic regression gate，报告 extraction、retrieval、status、high-risk 和 abstention 指标。没有完成中文/跨领域 gold benchmark、真实用户对照研究、临床或现实有效性验证。 |
| 13 | README 同时承担过多职责 | **部分完成** | [`README.md`](../README.md)、[`README.zh-CN.md`](../README.zh-CN.md)、[`docs/architecture.md`](architecture.md)、[`docs/limitations.md`](limitations.md)、本页 | 双语 README 已加入首屏能力真相表，并链接架构、限制、升级与审查对照文档。本轮不大拆 README；getting-started、provider、release、安全与 evaluation 的进一步信息架构拆分仍可后续进行。 |
| 14 | P0/P1/P2 优先级需要转成可验收路线 | **部分完成** | [`docs/v0.4_upgrade.md`](v0.4_upgrade.md)、[`README.md`](../README.md)、[`README.zh-CN.md`](../README.zh-CN.md)、[`ROADMAP.md`](../ROADMAP.md) | v0.4 已覆盖版本统一、能力措辞、契约执行、自我支持阻断、高风险/发布边界、manifest、Windows release gate 与部分 URL 安全。直接 UI audit、中文核心审计、完整 validity study 和 reviewer-decision workflow 尚未完成；更多 provider、托管、复杂 RAG 与自动文献检索继续延期。 |

## 本轮边界

本轮只接受能够由当前源码和定向测试支撑的表述。以下内容不得从 README、展示页或发布说明中推断：

1. 不得把 bilingual UI 写成 bilingual claim-audit algorithm。
2. 不得把 contract-aware rule screening 写成语义蕴含、事实核验或科学有效性证明。
3. 不得声称 Streamlit 工作台会直接运行 ClaimHarness；当前执行入口仍是 CLI。
4. 不得把 remote LLM advisory summary 写成核心 verification 或 verdict override。
5. 不得把 pending human-review queue 写成人工批准、身份核验或 release authorization。
6. 不得把 synthetic English-first regression metrics 写成现实、跨领域、中文或临床有效性。

对外最准确的一句话是：

> **ProblemBridge + ClaimHarness is a local-first prototype for deterministic workflow alignment and conservative, rule-based claim-evidence screening, with inspectable artifacts and explicit human-review boundaries.**
