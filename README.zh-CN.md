# ProblemBridge + ClaimHarness

<p align="center">
  <strong>一个面向跨学科 AI 项目的双阶段 Harness。</strong><br>
  ProblemBridge 负责建模前的问题对齐，ClaimHarness 负责输出后的证据审计。
</p>

<p align="center">
  <img alt="本地优先" src="https://img.shields.io/badge/local--first-yes-0f766e">
  <img alt="默认不需要 API" src="https://img.shields.io/badge/default-no%20API%20key-2563eb">
  <img alt="ProblemBridge" src="https://img.shields.io/badge/ProblemBridge-problem%20alignment-c2410c">
  <img alt="ClaimHarness" src="https://img.shields.io/badge/ClaimHarness-evidence%20audit-374151">
</p>

**语言：**[English](README.md) | [简体中文](README.zh-CN.md)
**展示页：**[English static showcase](docs/static_showcase/en.html) | [中文静态展示](docs/static_showcase/zh-CN.html)

## 项目定位

ProblemBridge + ClaimHarness 是一个本地优先的跨学科 AI 原型。它不是普通写作工具，不是 STORM 复刻，也不是通用 RAG 报告生成器。它关注的是 AI 进入其他领域时最容易出错的两件事：

1. **建模前的问题对齐。**ProblemBridge 帮助团队从真实工作流、判断材料、痛点和人工复核边界出发，生成 AI 任务规格、证据契约、评价协议和风险报告。
2. **输出后的证据审计。**ClaimHarness 检查科研文本或 AI 生成内容中的 claims 是否被已有正文、表格或参考材料支持，并标记弱证据、过度主张和需要人工复核的地方。

默认演示使用 deterministic mock mode，不需要 API key，不调用外部模型，只使用合成样例。

## 文档摄取层

文档摄取层用于在问题发现或证据审计之前，把本地文件先转成可检查的文本和表格输出。这个步骤默认本地运行，不需要 API，也不会调用外部模型。

当前支持：

- `.docx` Word 文档
- `.pdf` 文字版 PDF
- `.txt`
- `.md`
- `.csv`

输出包括：

- `extracted_text.md`
- `extracted_tables/`
- `source_manifest.json`
- `extraction_warnings.md`
- `problem_seed.md`

边界很重要：只支持文字版 PDF，不做 OCR，不理解扫描版 PDF，不做图片理解，也不解释 figure。它只负责提取文本和表格，不验证专业结论，也不能替代领域专家复核。
## 问题发现层

ProblemBridge 不假设用户一开始就知道真正的问题。问题发现层用于先提出问题、识别该问谁，并列出进入方案讨论前必须验证的未知项。

这个功能适合这样的状态：你只知道“这个工作流很慢”“这个环节好像适合 AI”“我想找专业领域的人问，但不知道该问谁、问什么”。它会在本地生成一个小型专家沟通包：

- `question_brief.md`
- `stakeholder_map.md`
- `expert_interview_guide.md`
- `unknowns_to_validate.md`
- `discussion_plan.md`

边界也很明确：先不要提出方案。先把值得问的问题、应该访问的人、需要验证的未知项梳理清楚，再进入引导式访谈或 ProblemBridge 对齐包生成。

## 引导式访谈引擎

ProblemBridge 的重点不是像普通聊天机器人一样马上回答，而是先通过引导式追问理解用户。系统会一次只问一个问题，维护当前的理解状态，显示已经理解的内容、还缺失的信息，以及当前完整度。

这也是它和常见大模型的差异：它会把用户从“我想要一个 AI”拉回到真实工作流，逐步还原判断材料、痛点、人工复核边界和可能的 AI 支持方式，然后再生成 AI 任务规格、证据契约和评价协议。

## 为什么需要它

很多跨学科 AI 项目并不是因为模型太弱而失败，而是在建模前就已经把领域问题压缩成了错误的 AI 任务：评价指标不对、证据边界不清、人工复核位置缺失，最后输出看起来流畅却不一定可靠。

这个项目的目标是给跨学科团队一个轻量 Harness：

```text
领域工作流
  ↓
ProblemBridge：问题对齐 / 工作流挖掘 / AI 任务规格化
  ↓
AI / researcher / team 进行建模、写作、系统设计
  ↓
ClaimHarness：claim-evidence 审计 / 风险路由 / trace logging
```

一句话概括：**ProblemBridge 负责开始之前不跑偏；ClaimHarness 负责输出之后不越界。**

## 谁适合使用

- **非 AI 背景的领域用户。**例如医生、教育者、文化研究者、政策研究者。你不需要先懂模型、prompt 或指标，只需要描述日常工作、判断材料、反复卡住的地方，以及哪些决定必须由人确认。
- **AI / 科研用户。**适合需要把领域问题转成任务规格、证据标准、评价协议和人工复核路线的人。
- **外部测试者。**适合先看合成样例，再用一个非敏感工作流测试本地网页 App。

## 功能概览

### ProblemBridge

ProblemBridge 用在 AI 工作开始之前，输出一个 Problem Alignment Package：

- 工作流图
- 痛点和机会矩阵
- 概念对齐表
- AI 任务规格
- 证据契约
- 评价协议
- 错位风险报告
- 人工复核计划
- 实施路线
- 对齐过程 trace

### ClaimHarness

ClaimHarness 用在文本或系统输出之后，输出一个 evidence audit package：

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`
- 可选静态报告 `index.html`

## 本地运行

如果你没有 AI 或编程基础，推荐直接运行本地网页 App：

```powershell
.\RUN_PROBLEMBRIDGE_WINDOWS.bat
```

如果你是从 GitHub clone：

```powershell
git clone https://github.com/RubyYii/ClaimHarness.git
cd ClaimHarness
.\scripts\run_problembridge_ui_powershell.ps1
```

浏览器打开后，建议顺序是：

1. 先看 `Explore examples`。
2. 生成一个合成样例。
3. 阅读 friendly summary。
4. 再进入 `Domain practitioner wizard`。
5. 描述一个非敏感、可重复的真实工作流。

CLI 用户可以运行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev,ui]"
.venv\Scripts\python.exe -m problem_bridge demo
.venv\Scripts\python.exe -m claim_harness demo
```

## 可分享包

如果要分享给别人测试，可以发送本地压缩包：

```text
ProblemBridge-ClaimHarness-v0.3.2-local-webapp.zip
```

对方解压后双击：

```text
RUN_PROBLEMBRIDGE_WINDOWS.bat
```

第一次运行会创建 `.venv` 并安装依赖，然后在本地浏览器打开 UI。它不是在线服务，也不是 `.exe`。

## 合成样例

当前仓库包含几个合成样例：

- HSG evidence-ready support：医学影像支持场景，强调可视化输出不等于临床结论。
- Chinese painting / VULCA：文化解释场景，强调识别物体不等于文化解释。
- Political education risk evaluation：教育风险场景，强调流畅回答不等于价值敏感的教育对齐。
- ClaimHarness oocyte demo：科研 claim-evidence 审计样例。

可以打开中文静态展示页查看：[`docs/static_showcase/zh-CN.html`](docs/static_showcase/zh-CN.html)。

## API 和模型

默认使用 `mock`，不需要 API key。远程模型提供商是可选的，只用于 advisory review。当前 ClaimHarness 已准备常见接口，包括 OpenAI-compatible、Qwen / DashScope、DeepSeek、Groq、Mistral、OpenRouter、xAI、Ollama、Gemini 和 Anthropic。

使用远程模型前要确认：你输入的内容会发送给外部服务。不要上传真实患者数据、机密论文、未公开项目材料、API key 或任何敏感信息。

本地网页 UI 的侧边栏现在包含 `Workspace Memory` 和 `API Settings`。你可以保存 provider、base URL、model、最近输出目录，以及 Question discovery、Domain wizard、AI wizard 的草稿字段。保存文件位于 `outputs/ui_memory/workbench_memory.json`。

API key 不会默认保存。网页里的 API key 输入框是 session-only，只在当前 Streamlit 进程中临时使用；保存记忆时会过滤 `api_key`、`token`、`secret`、`password` 等敏感字段。

Qwen / DashScope 可以使用 `qwen` provider：设置 `DASHSCOPE_API_KEY`，可选设置 `QWEN_BASE_URL` 和 `QWEN_MODEL`。

## 安全边界

- 这是原型，不是临床、法律或教育政策决策系统。
- 不保证事实正确性。
- 只检查你提供的材料。
- biomedical 或高风险 claims 仍然需要人工复核。
- mock mode 是确定性的演示模式，不等于完整语义理解。
- 不要输入真实患者数据、机密论文、未公开项目材料、API key 或任何敏感内容。

## 路线图

- v0.1：ClaimHarness 科研 claim-evidence audit demo。
- v0.2：ProblemBridge 问题对齐 MVP。
- v0.3：Guided Interaction Layer，让非 AI 背景用户从工作流开始描述问题。
- v0.4：让 ProblemBridge 生成的 evidence contract 更直接地进入 ClaimHarness。
- v0.5：进行 human review study，评估它是否真的提升问题清晰度、任务定义和评价设计。