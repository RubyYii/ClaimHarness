# ProblemBridge + ClaimHarness

<p align="center">
  <img src="docs/figures/github-hero-flat-comic.png" alt="ProblemBridge + ClaimHarness：本地优先的问题对齐与证据审计工作流" width="100%">
</p>

<p align="center">
  <strong>把模糊的工作感觉，变成具体问题、AI 任务边界和可审计证据。</strong><br>
  ProblemBridge 先帮你问清楚问题，ClaimHarness 再检查输出有没有证据支撑。也可以简单理解为：ProblemBridge 负责建模前的问题对齐，ClaimHarness 负责输出后的证据审计。
</p>

<p align="center">
  <img alt="本地优先" src="https://img.shields.io/badge/local--first-yes-0f766e">
  <img alt="默认不需要 API" src="https://img.shields.io/badge/default-no%20API%20key-2563eb">
  <img alt="ProblemBridge" src="https://img.shields.io/badge/ProblemBridge-problem%20alignment-c2410c">
  <img alt="ClaimHarness" src="https://img.shields.io/badge/ClaimHarness-evidence%20audit-374151">
</p>

<p align="center">
  <a href="#先看这里">先看这里</a> ·
  <a href="#本地运行">本地运行</a> ·
  <a href="#谁适合使用">谁适合使用</a> ·
  <a href="docs/static_showcase/zh-CN.html">中文静态展示</a> ·
  <a href="README.md">English</a>
</p>

**语言：**[English](README.md) | [简体中文](README.zh-CN.md)

**展示页：**[English static showcase](docs/static_showcase/en.html) | [中文静态展示](docs/static_showcase/zh-CN.html)

**开发复盘：**[开发经验整理](DEVELOPMENT_LESSONS.md)

## 先看这里

这个项目最适合这样的起点：

```text
我只是觉得某个工作流程很慢、很乱、有风险，或者很难说清楚。
我觉得 AI 可能能帮忙，但我还不知道应该问什么问题。
```

ProblemBridge 要做的第一件事，不是马上给方案，而是把这种模糊感觉变成可以和专业人士讨论的具体问题：

| 模糊感觉 | 它会帮助你追问成什么 |
| --- | --- |
| “这个审核环节太慢。” | 到底是哪一步慢？谁在判断？判断时看什么材料？ |
| “这里好像适合 AI。” | AI 应该辅助什么？哪些决定必须由人复核？什么输出才有用？ |
| “我不知道该问谁。” | 哪类专家、操作者、审核者或决策者掌握关键知识？ |
| “这个回答看起来挺合理。” | 哪些 claim 有证据支撑？哪些只是听起来流畅但证据弱或过度主张？ |

你不需要先懂模型、prompt、RAG 或 benchmark。先描述日常工作、判断材料、卡住的步骤、以及哪些决定不能交给 AI 自动完成。系统会帮助你生成问题清单、专家访谈方向、工作流说明、AI 任务规格、证据边界和审计结果。

## 项目一眼看懂

| 重点 | 说明 |
| --- | --- |
| **从模糊感觉开始** | 把“我觉得这里不太对”转成具体问题、该问的人、证据需求和复核边界。 |
| **默认不需要 API** | 首轮测试使用本地 deterministic mock mode，不调用外部模型。 |
| **引导式工作流** | 从文档摄取到问题发现、工作流对齐、AI 任务检查和结果查看，逐步继承上下文。 |
| **ProblemBridge** | 把领域工作流转成 AI 任务规格、证据契约、评价协议和人工复核边界。 |
| **ClaimHarness** | 检查文本或系统输出中的 claims 是否有证据支撑，并保留审计 trace。 |

<p align="center">
  <img src="docs/figures/github-workflow.svg" alt="从文档摄取到证据审计的引导式工作流" width="100%">
</p>

## 项目定位

ProblemBridge + ClaimHarness 是一个本地优先的跨学科 AI 原型。它不是普通写作工具，不是 STORM 复刻，也不是通用 RAG 报告生成器。它关注的是 AI 进入其他领域时最容易出错的两件事：

1. **建模前的问题对齐。**ProblemBridge 帮助团队从真实工作流、判断材料、痛点和人工复核边界出发，生成 AI 任务规格、证据契约、评价协议和风险报告。
2. **输出后的证据审计。**ClaimHarness 检查科研文本或 AI 生成内容中的 claims 是否被已有正文、表格或参考材料支持，并标记弱证据、过度主张和需要人工复核的地方。

默认演示使用 deterministic mock mode，不需要 API key，不调用外部模型，只使用合成样例。

## 文档摄取层

文档摄取层用于在问题发现或证据审计之前，把本地文件先转成可检查的文本和表格输出。这个步骤默认本地运行，不需要 API，也不会调用外部模型。

当前支持：

- `.docx` Word 文档，包括基础 Word 批注、高亮文本和字体颜色标记
- `.doc` 旧版 Word 文件会给出本地转换提示
- `.pdf` 文字版 PDF，并尽量提取 PDF 批注
- `.html` / `.htm` 保存下来的网页
- 本地 UI 中输入的公开静态 `http(s)` 网页 URL
- 图片文件（`.png`、`.jpg`、`.jpeg`、`.tif`、`.tiff`、`.bmp`），需要手动启用可选本地 OCR
- `.txt`
- `.md`
- `.csv`

输出包括：

- `extracted_text.md`
- `extracted_tables/`
- `annotation_map.json`
- `highlighted_spans.csv`
- `comment_threads.md`
- `priority_marks.md`
- `source_manifest.json`
- `extraction_warnings.md`
- `problem_seed.md`

在本地网页工作台里，文档摄取完成后会保留最近一次提取结果，并显示 `Continue to Question discovery` 按钮。点击后会把 `problem_seed.md` 自动带入问题发现表单，下一步不是空白开始，而是从已提取材料继续追问。

Word 批注、PDF 批注、高亮和字体颜色会被当作“用户注意力信号”保留下来，用于后续追问；系统不会自动推断某种颜色一定代表“高风险”或“已通过”。

边界很重要：OCR 是可选本地能力，不是默认依赖；URL 摄取只读取公开静态网页；不支持登录网页、JavaScript 执行、站点爬取、图片理解、figure 解释、手写标注意图识别或专业判断。它只负责提取文本、简单表格、链接和基础标注信号，不验证专业结论，也不能替代领域专家复核。

OCR 图文安装说明见 [OCR_SETUP.md](OCR_SETUP.md)，也可以直接打开本地网页 [docs/ocr_setup.html](docs/ocr_setup.html)。
## 问题发现层

ProblemBridge 不假设用户一开始就知道真正的问题。问题发现层用于先提出问题、识别该问谁，并列出进入方案讨论前必须验证的未知项。

这个功能适合这样的状态：你只知道“这个工作流很慢”“这个环节好像适合 AI”“我想找专业领域的人问，但不知道该问谁、问什么”。它会在本地生成一个小型专家沟通包：

- `question_brief.md`
- `stakeholder_map.md`
- `expert_interview_guide.md`
- `unknowns_to_validate.md`
- `discussion_plan.md`

边界也很明确：先不要提出方案。先把值得问的问题、应该访问的人、需要验证的未知项梳理清楚，再进入引导式访谈或 ProblemBridge 对齐包生成。

在本地网页工作台里，问题发现完成后会显示 `Continue to Domain practitioner wizard` 按钮。它会把问题发现 seed 带入领域工作流表单的上下文里，让用户从“应该问什么”自然进入“应该重建哪段工作流”，不需要手动复制文件。

后续链路也会继续传递上下文：领域工作流向导生成对齐包后，可以点击 `Continue to AI practitioner wizard`，把 `ai_task_spec.yaml`、`evidence_contract.yaml`、`evaluation_protocol.md` 和人工复核边界带入 AI 任务检查；AI 对齐检查完成后，可以点击 `Continue to View generated outputs`，直接查看、导出或分享结果包。

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
- `project_record.json`
- `project_summary_log.md`
- 首次记录修订后生成的 `revision_history.jsonl`

### ClaimHarness

ClaimHarness 用在文本或系统输出之后，输出一个 evidence audit package：

- `claim_table.csv`
- `evidence_map.json`
- `audit_report.md`
- `revision_suggestions.md`
- `agent_trace.jsonl`
- `run_manifest.json`
- `project_summary_log.md`
- 可选静态报告 `index.html`

本地网页工作台还可以把任意生成结果目录导出为 `export_report.docx` 和 `export_report.pdf`。导出内容来自输出目录里已有的 Markdown、CSV、YAML、JSON 和 trace 文件，在本地生成，不需要 API key，也不会调用远程模型。

## 本地运行

如果你没有 AI 或编程基础，推荐直接运行本地网页 App：

```powershell
.\RUN_PROBLEMBRIDGE_WINDOWS.bat
```

本地网页 UI 支持中英双语界面。页面顶部可以选择 `English` 或 `中文`，语言会同步到 URL：`?lang=zh` 直接打开中文界面，`?lang=en` 直接打开英文界面。

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
ProblemBridge-ClaimHarness-v0.3.3-local-webapp.zip
```

对方解压后双击：

```text
RUN_PROBLEMBRIDGE_WINDOWS.bat
```

第一次运行会创建 `.venv` 并安装依赖，然后在本地浏览器打开 UI。它不是在线服务，也不是 `.exe`。

## 合成样例

当前仓库包含几个合成样例：

- Quality inspection review alignment：质检审核场景，强调视觉检测不等于最终通过/不通过判断。
- Cultural archive interpretation alignment：文化档案场景，强调识别物体不等于专家解释。
- Training policy response alignment：培训政策场景，强调流畅回答不等于有来源依据的政策对齐。
- ClaimHarness lab report audit demo：通用实验报告 claim-evidence 审计样例。

可以打开中文静态展示页查看：[`docs/static_showcase/zh-CN.html`](docs/static_showcase/zh-CN.html)。

## API 和模型

本地网页 UI 只运行确定性的 `mock` 工作流，不需要 API key，也不提供 provider、model、base URL 或 API-key 输入控件。远程模型提供商是可选的 advisory review，只能通过 ClaimHarness CLI 配置和运行。当前 CLI 支持 OpenAI-compatible、Qwen / DashScope、DeepSeek、Groq、Mistral、OpenRouter、xAI、Ollama、Gemini 和 Anthropic。

使用远程模型前要确认：你输入的内容会发送给外部服务。不要上传真实患者数据、机密论文、未公开项目材料、API key 或任何敏感信息。

本地网页 UI 不接收、收集或保存 API key。侧边栏的 `显示工作台记忆` 只保存草稿字段和最近输出目录，文件位于 `outputs/ui_memory/workbench_memory.json`。分享文件夹或 zip 前，如果草稿里有敏感工作流信息，请先清除本地记忆。

Qwen / DashScope 可以使用 `qwen` provider：设置 `DASHSCOPE_API_KEY`，可选设置 `QWEN_BASE_URL` 和 `QWEN_MODEL`。

## 三轮修订治理

ProblemBridge 输出包现在包含 `project_record.json` 和 `project_summary_log.md`。可以用 `problem-bridge record-revision` 把每轮修改追加到 `revision_history.jsonl`。同一个稳定 target 最多修订三轮：第三轮仍未解决时必须升级为结构、规格或证据问题；在完成整合前，不允许继续打第四个局部补丁。

ClaimHarness 每次审计都会生成 `run_manifest.json` 和 `project_summary_log.md`。manifest 记录 run ID、工具版本、时间、provider 状态，以及输入/输出文件名、大小和 SHA-256，不暴露本地绝对路径；Markdown 摘要只是导航和 provenance 辅助，不是科学证据或批准记录。

## 安全边界

- 这是原型，不是临床、法律或教育政策决策系统。
- 不保证事实正确性。
- 只检查你提供的材料。
- biomedical 或高风险 claims 仍然需要人工复核。
- Results 章节中的自述不会自动成为该 claim 的强证据；强表格证据必须有可核验的指标/数值关系。
- mock mode 是确定性的演示模式，不等于完整语义理解。
- 不要输入真实患者数据、机密论文、未公开项目材料、API key 或任何敏感内容。

## 路线图

- v0.1：ClaimHarness 科研 claim-evidence audit demo。
- v0.2：ProblemBridge 问题对齐 MVP。
- v0.3：Guided Interaction Layer，让非 AI 背景用户从工作流开始描述问题。
- v0.4：让 ProblemBridge 生成的 evidence contract 更直接地进入 ClaimHarness。
- v0.5：进行 human review study，评估它是否真的提升问题清晰度、任务定义和评价设计。
