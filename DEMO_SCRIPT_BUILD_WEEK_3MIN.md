# OpenAI Build Week Demo Script — Under 3 Minutes

## 0:00-0:20 — Problem

> Domain experts can describe their work, but that description is often turned
> into an AI task too early. Unsupported capability promises then enter the
> build plan before anyone checks the evidence or human boundary.

Show the home page and the six-step workflow strip.

## 0:20-0:45 — Existing foundation versus Build Week work

> ProblemBridge's question discovery, alignment package, and ClaimHarness's
> manuscript audit existed before Build Week. This week I added the
> Evidence-Gated Build step: GPT-5.6 proposes structured capability claims,
> ClaimHarness gates them, and the system exports a Codex-ready contract.

Briefly show `BUILD_WEEK_DELTA.md` and the `pre-build-week-2026` tag.

## 0:45-1:15 — Generate the proposal

Open **Evidence-gated build**, select the synthetic quality-inspection package,
and choose **OpenAI GPT-5.6**.

> The key stays in the launch environment. The selected problem contains only
> synthetic data. GPT-5.6 uses the Responses API with a strict schema to return
> the user, workflow goal, human boundaries, evaluation signals, and candidate
> capability claims.

Click **Generate evidence-gated build contract**.

## 1:15-1:55 — Show the gate

Show the decision table. Open the deliberate claim that says the AI will
automatically approve the final decision.

> ClaimHarness does not trust fluent model output. It checks the claim against
> approved evidence references and the human-review plan. This autonomy claim
> is marked overclaimed and downgraded to decision support where a qualified
> human keeps final authority.

Point out one retained claim, one weak claim, and the downgraded claim.

## 1:55-2:25 — Show auditability

Open `gpt_5_6_runtime.json` and `build_record.jsonl`.

> The runtime record stores the model, response ID, and input/output hashes,
> but never the API key. Mock mode follows the same flow but truthfully records
> that GPT-5.6 was not called. The replay record shows proposal generation,
> claim decisions, and handoff hashes.

## 2:25-2:50 — Show the Codex handoff

Open the `codex_handoff` directory.

> The final package gives Codex bounded instructions, a specification, tasks,
> acceptance tests, the evidence contract, a risk register, and a demo
> scenario. Unsupported claims never become implementation requirements.

## 2:50-2:58 — Close

> ProblemBridge helps teams ask and align before they build. ClaimHarness checks
> what they are allowed to claim before Codex implements it.
