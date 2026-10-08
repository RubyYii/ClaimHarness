# ProblemBridge 工作台

[English](README.md) · [简体中文](README.zh-CN.md)

**把你的需求，说给其他专业的合作者和 AI 听。**

从一件具体工作开始，逐步说清困难、预期结果和专业词语，再带走两份说明：一份给合作伙伴，一份给大模型。

本地运行 · 中英双语 · 开始时无需 API key

![流程插图：从模糊需求到共同理解，再形成给合作者和 AI 的两份说明](docs/figures/github-hero-workbench-v2.png)

## 三步开始使用

1. **说说你的工作。** 一次回答一个问题，暂时说不清的可以跳过。
2. **确认符合你的意思。** 修改表述、解释专业词语，写清怎样判断结果有用。
3. **带走两份说明。** 复制或下载，由你决定交给哪位合作者、放进哪个 AI。

有结果后，可按需使用 **ClaimHarness**，对照 CSV 表格核查可识别的英文数值表述。

## 收到反馈或修改材料后继续

在已确认说明旁选择“带回反馈继续讨论”，记录分歧、回答与更正，再由你确认新版说明。修改材料并重新核查后，可以比较两轮结果、补标遗漏表述，并分别保存程序结果、用户行动和人工意见。

运行完整合成示例：`python scripts/run_continuity_demo.py --out outputs/continuity_demo`。独立使用 ClaimHarness：`python -m streamlit run apps/claim_compare.py`。[使用流程、CLI 与记录格式](docs/continuous_review.md)

## 在 Codex 或 Claude Code 中使用

已有本地编程助手，可以安装 `problem-bridge` 和 `claim-harness` 两份 Skill，在聊天中澄清需求、继续处理反馈、核查并比较版本。复用现有 Python 内核，无须再配置模型 API key 或启动网页界面。[安装、更新与使用示例](docs/agent_skills.md)。

## 本地运行

**Windows：** [下载源码 ZIP](https://github.com/RubyYii/ClaimHarness/archive/refs/heads/main.zip)，解压后双击 `RUN_PROBLEMBRIDGE_WINDOWS.bat`。

需要 Python 3.10–3.13。首次运行会安装依赖，并在浏览器打开本地页面 `http://127.0.0.1:8501`。

<details>
<summary>从终端安装与启动</summary>

在已激活的 Python 环境中，从仓库根目录运行：

```bash
python -m pip install -c requirements/constraints.txt -e ".[dev,ui]"
python -m streamlit run apps/problem_bridge_wizard.py
```

[环境设置与启动帮助](docs/reference.zh-CN.md#本地运行)

</details>

## 可执行的需求澄清示例

运行 `python -m problem_bridge clarify-demo --out outputs/clarification_demo --answer sensors`，查看合成需求如何经过执行预览、追问答复和任务修订，生成交接说明与 CSV 结果。加上 `--correct-to observations` 可演示用户显式修改要求。此本地示例没有模型调用或真人参与。

[机制说明、输出文件与 Python API](docs/clarification_mechanism.md)

## 使用边界

网页界面使用本地预设问题引导，由你确认专业含义；说明不会自动发送给他人或大模型。证据核查有明确范围，不能证明事实正确，也不能代替专业人员判断。

请先用公开或合成材料。不要输入真实患者数据、机密文稿或敏感未公开材料；分享项目文件夹前，请清除本地记忆。

## 进一步了解

- **使用工作台：** [中文指南](docs/reference.zh-CN.md) · [English guide](docs/reference.md)
- **了解能力范围：** [功能与限制](docs/limitations.md)
- **配置可选工具：** [模型设置](MODEL_PROVIDER_GUIDE.md) · [OCR](OCR_SETUP.md)
- **开发与项目资料：** [架构](docs/architecture.md) · [文档索引](docs/project_map.md)

<details>
<summary>命令行证据核查示例</summary>

安装后，在仓库根目录通过 PowerShell 运行：

```powershell
.venv\Scripts\python.exe -m claim_harness run `
  --manuscript examples/lab_report_audit_demo/manuscript.md `
  --tables examples/lab_report_audit_demo/tables `
  --references examples/lab_report_audit_demo/references.md `
  --out outputs/lab_report_audit_demo_run `
  --llm mock
```

主要输出：`claim_table.csv`、`evidence_map.json`、`audit_report.md`、`revision_suggestions.md`、`agent_trace.jsonl`。

重复运行时，请为 `--out` 指定新的文件夹。[核查演示](docs/demo_walkthrough.md) · [使用与技术参考](docs/reference.zh-CN.md)

</details>
