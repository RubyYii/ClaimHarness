# 项目目录与文档索引

ClaimHarness 当前仓库版本为 **0.4.1**，同时包含 ProblemBridge 和 ClaimHarness。
ProblemBridge 帮助用户说清实际需求，生成给跨专业合作者和大模型的两份说明；
ClaimHarness 对已有文字中的声明进行确定性证据筛查。网页工作台提供需求引导、
交付和可选核查，CLI 保留更完整的审计参数。

## 从哪里开始

| 目的 | 入口 |
| --- | --- |
| 首次了解和运行 | [中文 README](../README.zh-CN.md)、[英文 README](../README.md#run-locally) |
| 查阅完整用法与命令 | [中文参考](reference.zh-CN.md)、[English reference](reference.md) |
| 使用网页工作台 | 根目录 `RUN_PROBLEMBRIDGE_WINDOWS.bat`；[非 AI 用户指南](../NON_AI_USER_GUIDE.md) |
| 检查稿件与结果表 | [审计演示步骤](demo_walkthrough.md)；`python -m claim_harness run` |
| 了解当前代码职责 | [架构](architecture.md)、[v0.4 升级说明](v0.4_upgrade.md) |
| 判断输出能说明什么 | [能力限制](limitations.md)、[外部审查问题对照](external_review_reconciliation.md) |
| 查看最近界面检查 | [2026-09-22 布局调整](layout_polish_2026-09-22.md)、[跨专业交付验证](cross_disciplinary_verification.md) |
| 查看维护历史 | [2026-09-05 本地检查记录](project_check_2026-09-05.md) |

所有命令从仓库根目录运行。默认 `mock` 不需要 API key。重复运行时指定新的
`--out` 目录；需要恢复或替换时，遵循 [运行身份检查](v0.4_upgrade.md#safe-output-lifecycle)。

## 代码和数据放在哪里

| 路径 | 当前职责 |
| --- | --- |
| `claim_harness/` | 输入加载、声明抽取、证据检索、规则验证、报告、可选模型适配 |
| `problem_bridge/` | 文档摄取、问题发现、访谈、任务对齐、证据合同、运行与修订记录 |
| `apps/problem_bridge_wizard.py` | Streamlit 工作台入口 |
| `tests/` | 流程、证据边界、输入输出安全、UI 交接和发布脚本测试 |
| `examples/lab_report_audit_demo/` | 主审计合成样例；项目完成条件指定的输入 |
| `examples/general_demo/` | 小型文档分流合成样例，包含数值矛盾与缺少证据的声明 |
| `examples/problem_bridge/` | 质量检查、文化档案和培训政策的合成工作流 |
| `claim_harness/demo_data/`、`problem_bridge/demo_data/` | 安装包内置样例资源，与根目录样例承担不同打包职责 |
| `claim_harness/eval_data/` | 小型、版本化的英文合成回归集 |
| `scripts/` | Windows 安装和启动、合成评估、发布打包与检查 |
| `requirements/constraints.txt` | 固定的依赖版本；与 `pyproject.toml` 一起维护 |
| `docs/sample_outputs/` | 纳入版本控制、可复核完成记录的展示样例 |
| `outputs/` | 本地运行生成的结果，默认不纳入 Git |
| `dist/` | 发布构建产物，默认不纳入 Git；已有 ZIP 不随源码自动更新 |
| `.local/` | 本机维护记录和归档，默认不纳入 Git |

根目录的 `release/`、`submission/`、`codex_outputs/` 是此工作区已有的本地材料，
本轮保持原位和内容。它们当前未纳入 Git，也不代表已经完成平台提交。

## 文档按用途阅读

| 用途 | 文档 |
| --- | --- |
| 产品介绍与演示 | [Portfolio brief](../PORTFOLIO_BRIEF.md)、[三分钟演示](../DEMO_SCRIPT_3MIN.md)、[静态中文展示](static_showcase/zh-CN.html) |
| 输入和模型配置 | [OCR 安装](../OCR_SETUP.md)、[模型提供方说明](../MODEL_PROVIDER_GUIDE.md) |
| 本地分享和打包 | [发布包指南](../RELEASE_PACKAGE_GUIDE.md) |
| Build Week 材料 | [评委入口](../JUDGE_START_HERE.md)、[增量说明](../BUILD_WEEK_DELTA.md)、[提交说明](../BUILD_WEEK_SUBMISSION.md) |
| 维护和后续工作 | [路线图](../ROADMAP.md)、[开发经验](../DEVELOPMENT_LESSONS.md)、[可用性测试计划](../USABILITY_TEST_PLAN.md) |
| 历史设计与验证 | `docs/superpowers/`、`docs/project_records/`；按日期和对应版本理解 |

历史验证记录说明当时检查过什么。判断当前行为，应以当前代码、对应测试和新运行
结果为依据。主版本由 `pyproject.toml` 与两个 Python 包的 `__version__` 共同核对。

## 日常维护

```powershell
.venv\Scripts\python.exe -m pytest -q -rs
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe scripts/evaluate_gold_set.py --out outputs/synthetic_evaluation
```

默认 pytest 使用固定的 `.pytest_tmp_run/`。日常运行复用这个位置，避免每轮另建一个
永久留在根目录的测试目录。不要在测试运行中移动其临时目录。

2026-09-05 的历史临时目录与旧主演示结果归档在
`.local/archive/2026-09-05-project-check/`，每项原路径、归档路径和状态保存在
`restore_manifest.json`。恢复时先查看对应条目，确认原路径空闲，再移回；
原路径已有新结果时先另外保存新结果。归档只迁移本机文件，不代表释放磁盘空间。

发布脚本要求干净的 Git 工作区，并从提交构建。先审阅并提交需要发布的改动，再运行
发布包检查。真实远程模型调用、外部使用者验证和最终平台提交各需独立证据。
