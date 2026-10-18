# 公开数据适配检查：模糊想法如何成为清晰需求

日期：2026-10-02。用户先提出“开始测试”，随后提出“看看开源数据库”。本轮按公开数据集查找和适配检查开展；没有把这句话登记为已澄清、已确认的正式需求，也没有改写既有论文主张。

已下载固定版本的 IN3、CCPE、ReqElicitGym 文本及相关说明，读取 AREAs-Lab 说明与论文。输入文件的来源、版本和 SHA-256 见 `source_manifest.json`。这轮完成数据检查与开发样本准备，**没有运行新模型对比或招募参与者**。

## 数据选择

| 数据 | 本地核对情况 | 可支持的测试 | 解释限制 |
|---|---|---|---|
| [IN3 / Tell Me More](https://github.com/OpenBMB/Tell_Me_More) | 108 个测试任务与 108 段 GPT-4 对话逐条匹配；每段有模型总结 | 追问记录到需求说明的信息保留、遗漏、推测来源 | [论文附录 E.1](https://aclanthology.org/2024.acl-long.61.pdf)介绍 8 名参与者想象自己执行给定任务；不是 108 名真实客户。训练用模拟对话与这些参与者记录必须分开。已有模型总结不是金标准 |
| [CCPE-M](https://github.com/google-research-datasets/ccpe) | 502 段访谈，11,971 条话语；6,377 条 USER、5,594 条 ASSISTANT | 从偏好、例子、犹豫和局部确认整理说明；追踪观点由谁提出 | 两名众包参与者扮演双方，讨论电影偏好；没有用户确认的最终可执行需求书，不能直接测工作任务交付 |
| [ReqElicitGym](https://github.com/jdm4pku/ReqElicitBench) | 101 个场景、10 类网站任务、632 条隐含需求、1,000 条最终用户故事 | 初始描述到预定完整要求的受控恢复 | 最终要求先经标注形成，再删减为初始描述，模型扮演用户；不是自然形成目标的记录。仓库明确未附许可，本轮只本地检查，不纳入导出样本 |
| [AREAs-Lab](https://arxiv.org/html/2608.28979v1) | 查阅论文和官方仓库说明；未下载或运行任务数据 | 同时检查材料和询问用户的相关方法与对照 | 主基准为合成任务；与当前研究问题接近，需纳入相关工作，不能以“会询问并生成需求”本身宣称创新 |

IN3 仓库根许可证为 Apache-2.0，CCPE README 标示 CC BY 4.0。原文件和许可证保存在本地 `raw/`，不将未经核对的其他仓库视作同一许可。未下载软件、音视频或模型权重。

本目录发布的 24 条改编样本适用各自的来源许可，作者、原始版本、改编方式和许可副本见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。完整原始缓存不提交到 Git。

另查阅 [ClariQ](https://github.com/aliannejadi/ClariQ)、[AMI](https://groups.inf.ed.ac.uk/ami/corpus/overview.shtml)、[PRISM](https://github.com/HannahKirk/prism-alignment) 和 [需求访谈追问数据](https://github.com/anmolsinghal98/Requirements-Elicitation-Follow-Up-Question-Generation)。本轮不扩展到这些数据的下载或实验；搜索消歧、团队设计协商、主观反馈分别有用，但不可混为需求形成的同一指标。

## 第一轮开发测试输入

从 IN3 的 108 个任务和 CCPE 的 502 段对话中，各按固定 SHA-256 排序取前 12 条，共 24 条。排序前缀为 `requirements-data-check-2026-10-02:`。样本选择不依赖模型错误或人工喜好；属于开发样本，不声称是未见测试集。

- `pilot_inputs.jsonl`：只保留记录中的角色、话语与原始轮次；IN3 最后的模型总结已移到审阅文件。公开语料是任务数据，不是对当前模型的指令。
- `review_only.jsonl`：源标注、历史模型总结和参与者计数，仅供事后审阅，不作为模型输入或完美答案。
- `data_check.json`：本地实测规模、对应关系、抽样说明和尚未运行推理的状态。
- `SAMPLE_REVIEW_zh.md`：本轮人工式逐例阅读的六个案例，属于助手探索性判断，不是独立人类标注。

CCPE 的 5,132 条话语没有 `segments` 字段。准备脚本保留该缺省状态，不把它补成“已标注且没有偏好”。已逐条复核 24 个样本的 356 条话语与原始记录完全一致，检查结果见 `pilot_verification.json`。

后续最小对照可让同一个模型在相同完整对话上分别使用普通需求总结提示、明确要求区分用户原话/已同意建议/待定信息的提示。比较用户明确要求的保留、无依据补充、否定和条件的遗漏；同时保留长度与成本。固定对话只能评估整理质量，无法评价新问题的互动收益。历史最终总结不能成为唯一正确答案，模型判断也不能代替原用户认可。

**本轮没有得出方法优于普通对话的结果，也没有证实 AI 促进了真实目标形成。** 固定对话整理如无差异，应如实报告；需求形成仍需要互动研究，不能用固定对话的结果替代。

## 复现

从仓库根目录执行；需要联网的只有首次 `fetch`，其他步骤只读本地缓存。

```powershell
& .venv/Scripts/python.exe -X utf8 research/requirements_data_check_2026-10-02/inspect_sources.py fetch
& .venv/Scripts/python.exe -X utf8 research/requirements_data_check_2026-10-02/inspect_sources.py inspect
& .venv/Scripts/python.exe -X utf8 research/requirements_data_check_2026-10-02/prepare_pilot.py
& .venv/Scripts/python.exe -X utf8 research/requirements_data_check_2026-10-02/inspect_sources.py verify
```

新克隆仓库后，`fetch` 按已经提交的 `source_manifest.json` 恢复缺失缓存，逐项核对版本、字节数和 SHA-256，保持清单原样。已有缓存若不匹配则报错，不覆盖。复查使用 `verify`。只有从未建立清单时才创建新清单。原始来源：Qian et al. (ACL 2024, IN3)；Radlinski et al. (SIGDIAL 2019, CCPE)；Jin et al. (arXiv:2602.18306, ReqElicitGym)。本目录只做公开资料开发检查，没有改动应用行为。

## 执行检查

9 个源文件的哈希检查通过。现有项目测试 `542 passed`；mock 示例在独立目录 `outputs/requirements_data_check_2026-10-02_mock` 运行成功并生成五个规定文件。这些是数据处理与工程检查，不是新方法的效果分数。辅助 Gemini 命令返回 503，本轮没有使用其研究判断，也没有新模型试验输出。

Git 发布准备补充了缓存恢复验证，并统一生成文件的 LF 换行，避免 Windows 与 Git 规范化造成样本哈希差异。原始话语和下载文件的哈希均不变；发布文件的哈希重新核对。空缓存可按固定清单恢复 9 个源文件，重新生成的两份样本文件及 `data_check.json` 与发布版本逐字节一致。新增回归测试和审阅记录见 `publication_verification.json`；原始数据检查阶段的 503 记录仍保留在 `completion.json`。
