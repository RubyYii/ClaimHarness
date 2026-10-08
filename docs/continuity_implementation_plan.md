# Continuous feedback and audit comparison

The October 2026 implementation follows PB-01–06 and CH-01–06 in the supplied task brief. It reuses the current deterministic pipeline, immutable run lifecycle, confirmed problem records, clarification functions and bilingual handoffs.

1. Preserve an input-text/table snapshot and a fingerprint of the actual checking code in new audit runs. Compare only validated packages; show legacy limitations explicitly. Match exact, unique statements without normalising numbers, units or negation. Ambiguous correspondence remains open; user mappings may describe splits or merges.
2. Keep user annotations and handling/reviewer notes in a separate version-bound journal. Manual additions are unevaluated. Export comparison JSON, a readable report, pending questions and optional research-discussion inputs. No claim of automatic resolution or full-text coverage.
3. Add a persistent feedback discussion bound to a confirmed problem version. Preserve verbatim feedback, user interpretation, selected excerpt, category and provenance. Reuse clarification answer/correction logic, allow open questions, unknown and deferred states, and reject stale writes.
4. Explicitly confirm additions, corrections or goal changes into a new immutable problem version. Both handoffs use that version and include decisions, open questions, changes and next actions. Old audits remain history after a changed requirement.
5. Extend the existing bilingual Streamlit workbench with feedback/discussion and audit-comparison panels. Keep standalone ClaimHarness CLI/report access. Use only existing trusted demonstration execution adapters, with execution/example/inference labels.
6. Verify synthetic adversarial cases, Streamlit flows, legacy compatibility, the required mock demo and the full pytest suite. Capture UI screenshots and seek Gemini visual review. Engineering checks do not establish benefits on real tasks.

Remote advisory input is restricted to this generic implementation/design description, changed public application source and synthetic UI evidence. Existing research directories, manuscripts, local records and credentials are excluded.
