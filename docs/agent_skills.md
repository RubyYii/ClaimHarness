# Use from Codex or Claude Code / 接入现有助手

The repository now ships two additive, portable Skills. **ProblemBridge** clarifies a task, creates bilingual briefs and continues after feedback. **ClaimHarness** runs the existing evidence checker, inspects source-bound findings, compares revisions and records actions. The web UI and its existing commands remain available.

适用于能读取本地文件和运行 Python 命令的 **Codex、Claude Code**。聊天模型负责讨论，两份 Skill 调用本地 Python 内核保存记录和执行检查。不需要再配置一份模型 API key；这不代表宿主聊天本身离线，也不代表普通 Claude/ChatGPT 网页聊天会自动加载本地 Skill。

## Install / 安装

Clone or download the latest repository first. Keep this backend checkout after installation: the Skills are small adapters, not a copy of the full engine. Python 3.10–3.13 is recommended. From its root:

```powershell
# Windows PowerShell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -c requirements/constraints.txt -e .
.venv\Scripts\python.exe scripts/install_agent_skills.py --client both --scope user --dry-run
.venv\Scripts\python.exe scripts/install_agent_skills.py --client both --scope user
```

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -c requirements/constraints.txt -e .
.venv/bin/python scripts/install_agent_skills.py --client both --scope user
```

Use `--client codex` or `--client claude` to install for only one client. No Streamlit/UI dependency is needed. The user-level destinations are:

| Client | Destination |
|---|---|
| Codex | `~/.agents/skills/problem-bridge` and `~/.agents/skills/claim-harness` |
| Claude Code | `~/.claude/skills/problem-bridge` and `~/.claude/skills/claim-harness` |

For one project only, pass an existing project directory instead:

```text
python scripts/install_agent_skills.py --client both --scope project --project "path/to/my project"
```

This writes `.agents/skills` and/or `.claude/skills` in that project. Run the installer with the backend's installed Python, or pass its absolute path with `--python`. Each installed package has a generated `references/runtime.json` pointing to that interpreter and backend. No credentials are stored. These bindings are machine-specific; do not commit generated installations or copy their runtime files to another machine. Share this repository and run the installer there instead.

安装器默认不覆盖已有目录。`--upgrade` 只更新此前由本安装器管理且内容未改动的 Skill；遇到同名自建 Skill、改动或符号链接/Windows junction 会停止。先保留和处理自己的修改，再重新安装。替换按单个 Skill 暂存并切换，失败时恢复该 Skill 的旧目录；若多个目标中途发生系统错误，已成功安装的目标会在输出中列出，可用 `--upgrade` 重试。`--dry-run` 检查环境与目标，不安装文件。

## Start using it / 开始使用

Open a new client session after installation if the Skills are not listed. In Codex select the Skill or mention `$problem-bridge` / `$claim-harness`; in Claude Code use `/problem-bridge` / `/claim-harness`. Natural-language requests can also match their descriptions. Availability still depends on the client's skill settings and local execution permissions.

Try:

> 用 problem-bridge 帮我澄清这项任务。目标是解释差异，先不要把它改成预测问题。确认后生成给合作者和 AI 的两份说明。

> 对方给了这些反馈。请保留原文，把我选中的部分带回上一版继续讨论，未知的问题先保留。

> 用 claim-harness 检查 manuscript.md 和 tables/，把结果保存为 audits/v1。修改后再跑 v2，说明哪些变化有证据、哪些仍需我判断。

The host should resolve the installed Skill's own `scripts/run.py` and first execute it with `--check`. Paths supplied to the runner resolve from the user's project, even though the backend subprocess runs from its repository root. Always quote paths containing spaces. See the complete schemas and command examples in [ProblemBridge commands](../skills/problem-bridge/references/commands.md) and [ClaimHarness commands](../skills/claim-harness/references/commands.md).

## Synthetic end-to-end check / 合成样例

From the backend root:

```text
python scripts/run_agent_skills_demo.py --out outputs/agent_skills_demo
```

Use a new output directory on each run. The script installs project-scoped Skills into a separate demo project, then invokes the installed runners from that project: create a confirmed problem → save feedback → answer → confirm a new version → audit two result versions → inspect → annotate → compare → record an action. It also runs a standalone ClaimHarness audit. All material and confirmation assertions in this script are synthetic, not actual user approval. It writes `demo_summary.json` with artifact paths, plus the saved immutable runs, journals and comparison. It makes no external model calls.

This proves the installed adapters can execute the workflow. It does not by itself prove native discovery by every Codex/Claude client version. The package format and destinations follow the official [Codex Skills documentation](https://learn.chatgpt.com/docs/build-skills) and [Claude Code Skills documentation](https://code.claude.com/docs/en/skills). The included `agents/openai.yaml` supplies Codex display metadata; the shared `SKILL.md` uses common `name` and `description` frontmatter.

## Continue and update / 继续使用与更新

Save the returned workspace, project ID and `run_name`. The next session reads `show` or `inspect` before writing. Completed runs are immutable; feedback and manual handling live in separate journals. Writes use the observed journal revision and reject stale requests. Supplement/correction/goal change stay distinct. Existing explicit approval for the exact wording is reused; otherwise the host asks before saving a changed meaning. `--confirmed` records the caller's assertion, not verified human identity.

For an existing Git checkout with a clean main branch:

```text
git pull --ff-only
python -m pip install -c requirements/constraints.txt -e .
python scripts/install_agent_skills.py --client both --scope user --upgrade
```

Use the same backend Python and the same scope/project options as at installation. A moved backend or deleted virtual environment requires reinstalling the bindings. Updating the backend does not automatically refresh the copied Skill instructions; run the installer with `--upgrade`.

Current checks mainly cover recognized English numerical statements against CSV tables. Missing findings do not establish coverage, scientific correctness or readiness for submission. User actions and attributed human opinions never overwrite program verdicts. Use public or synthetic material; do not introduce patient data or confidential manuscripts. These Skills do not send briefs to collaborators automatically or bypass host permissions.
