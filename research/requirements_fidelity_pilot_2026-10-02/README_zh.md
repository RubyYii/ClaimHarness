# 需求整理忠实性测试

固定 24 段公开对话，运行普通整理、来源/确认状态提醒、普通整理加复核三个方式。问题、评价边界和调用预算见 [PROTOCOL_zh.md](PROTOCOL_zh.md)。这是静态对话开发测试，不能评价真实交互需求形成；自动评分及 Codex 来源复核均不是独立人类标注。

来源使用已发布的 [公开数据适配包](../requirements_data_check_2026-10-02/README_zh.md)，许可和改编说明沿用该包的 [THIRD_PARTY_NOTICES.md](../requirements_data_check_2026-10-02/THIRD_PARTY_NOTICES.md)。不使用无许可的 ReqElicitGym 场景或历史模型总结。检查点来自生成前的 Codex 原文阅读。

从仓库根目录执行（Windows 可将 python 换为 `.venv/Scripts/python.exe -X utf8`）：

```powershell
python research/requirements_fidelity_pilot_2026-10-02/study.py prepare
python -m pytest -q research/requirements_fidelity_pilot_2026-10-02/test_study.py
python research/requirements_fidelity_pilot_2026-10-02/study.py freeze
python research/requirements_fidelity_pilot_2026-10-02/study.py run --executable <installed-codex-executable> --workers 4 --limit 4
python research/requirements_fidelity_pilot_2026-10-02/study.py run --executable <same-codex-executable> --workers 8
python research/requirements_fidelity_pilot_2026-10-02/study.py analyze
```

`prepare`、`freeze` 拒绝覆盖旧输入。`run` 只执行未尝试任务，保留失败、无自动重试。`analyze` 重建全部提示并核对输入、前序输出、会话和引用。`scored_outputs.json` 是自动评分，`audit_packet.json` 包含所有被报错/遗漏/不确定的案例及预定六例；最终来源复核另存，不覆盖原始评分。最多 96 次调用，均使用独立隔离会话，无工具操作。

本目录为独立研究脚本，不改变应用行为。工程回归使用仓库 pytest；mock 示例仍按根 README 的命令执行，并在本轮单独的输出目录保存五个规定文件。工程通过不表示研究效果。
