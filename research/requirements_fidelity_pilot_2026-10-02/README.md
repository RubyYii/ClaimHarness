# 公开对话整理测试：结果与复核

24 段公开对话、72 份整理输出、24 次匿名自动评分。三组在 99 个可用内容检查点上均为 99/99，未观察到专门的来源/确认状态提示优于普通整理。评分、参考更正和 Codex 来源复核的限制见 [完整结果](RESULTS_zh.md)。

- [冻结的实验方案](PROTOCOL_zh.md)与[原执行说明](README_zh.md)
- [原始自动评分](scored_outputs.json)、[来源复核与参考更正](source_audit.json)、[更正后汇总](corrected_summary.json)
- `runs/`：96 次调用的实际提示、原始返回、事件日志、结构化结果和用量
- [公开数据来源及许可](../requirements_data_check_2026-10-02/THIRD_PARTY_NOTICES.md)

从新克隆仓库的根目录复核已发布结果，无需模型、API、额外下载或本机 mock 缓存：

```powershell
python research/requirements_fidelity_pilot_2026-10-02/verify_results.py --published
```

需要 Python 3.10+，只用标准库。Windows 本项目环境可使用 `.venv/Scripts/python.exe -X utf8`。此命令核对冻结文件、源对话、实际提示、前序哈希、96 个独立会话、原始输出、评分引用和更正分母，不改写结果。

原 `study.py verify/analyze` 保留运行当时的工作区保护检查，包括未发布的作者主张文件；`verify_results.py` 不带参数还会核对本机 mock 产物。新克隆应使用上面的 `--published` 模式：只允许该非实验输入的作者文件缺失，并明确报告未检查这一保护项；其他缺失或不匹配仍失败。旧模型可执行路径和临时目录仅保留为运行记录，不要求复核者拥有这些路径。

发布包保留原始字节，局部 `.gitattributes` 禁止自动换行转换。冻结的协议、脚本和全部原始评分均未修改；`--published` 是事后增加的发布核验入口。失败的 Gemini 方案请求只在 `advisory_status.json` 中记录；空输出文件和运行锁不发布。

`verification.json` 中 547 项回归与 mock 结果来自实验执行时的本地工作区，不代表本次新克隆重新跑过完整应用测试。发布核验不调用模型，也不把工程通过当成研究效果。
