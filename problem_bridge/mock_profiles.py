from .schemas import AlignmentPackage, ConceptAlignment, PainpointOpportunity


def quality_inspection_profile(source_problem: str) -> AlignmentPackage:
    return AlignmentPackage(
        profile="quality_inspection",
        project_name="quality_inspection_review_alignment",
        title="Quality Inspection Review Alignment",
        source_problem=source_problem,
        domain_goal=(
            "Support reviewable inspection by preserving material quality, defect visibility, "
            "uncertainty, reviewer notes, and final human judgement."
        ),
        not_allowed_goal="autonomous pass/fail decision",
        meaningful_outputs=[
            "Evidence sidecar for reviewer inspection",
            "Conservative inspection summary draft",
            "Human review flag for low-confidence or high-impact findings",
        ],
        non_meaningful_outputs=[
            "A standalone pass/fail decision from a visual mark",
            "A deployment-ready quality gate without validation",
        ],
        workflow_steps=[
            "Item intake",
            "Image or record capture",
            "Input quality judgement",
            "Defect candidate review",
            "Severity and uncertainty judgement",
            "Reviewer interpretation",
            "Inspection summary drafting",
            "Review and correction",
        ],
        painpoints=[
            PainpointOpportunity(
                workflow_step="input quality judgement",
                pain_point="Visibility, lighting, or sampling quality are inconsistently recorded.",
                ai_opportunity="Generate input-quality and visibility sidecars.",
                risk="medium",
                human_role="confirm quality and visibility labels",
            ),
            PainpointOpportunity(
                workflow_step="defect candidate review",
                pain_point="Repeated visual checking can be slow and inconsistent.",
                ai_opportunity="Highlight candidate regions and uncertainty.",
                risk="medium",
                human_role="confirm or reject highlighted evidence",
            ),
            PainpointOpportunity(
                workflow_step="inspection summary drafting",
                pain_point="Wording may overstate what the available evidence supports.",
                ai_opportunity="Draft conservative evidence-grounded report text.",
                risk="high",
                human_role="edit and approve final wording",
            ),
        ],
        concepts=[
            ConceptAlignment(
                domain_concept="quality failure",
                ai_representation="classification label",
                alignment_status="partial",
                misalignment_risk="a visual anomaly may reflect capture quality, context, or acceptable variation rather than failure",
            ),
            ConceptAlignment(
                domain_concept="defect visibility",
                ai_representation="detection confidence plus input quality",
                alignment_status="aligned",
                misalignment_risk="input quality and acceptance criteria still need reviewer interpretation",
            ),
            ConceptAlignment(
                domain_concept="operational readiness",
                ai_representation="deployment status",
                alignment_status="high-risk",
                misalignment_risk="requires validation beyond model metrics and sample screenshots",
            ),
        ],
        ai_task_type=[
            "input_quality_assessment",
            "defect_candidate_detection",
            "evidence_sidecar_generation",
            "conservative_inspection_summary_drafting",
        ],
        inputs=[
            "inspection_image_or_record",
            "candidate_region_overlay",
            "confidence_score",
            "input_quality_label",
        ],
        outputs=[
            "evidence_summary",
            "uncertainty_statement",
            "human_review_flag",
            "structured_draft_summary",
        ],
        required_evidence={
            "inspection_suggestion": [
                "source_region_or_record",
                "uncertainty_statement",
                "human_review_flag",
            ],
            "model_performance": [
                "quantitative_table",
                "baseline_comparison",
                "error_analysis",
            ],
        },
        forbidden_without={
            "inspection_suggestion": [
                "reviewer_confirmation",
                "input_quality_assessment",
            ],
        },
        evaluation_protocol=[
            "Candidate detection quality for visible issues",
            "Evidence completeness for each inspection statement",
            "Uncertainty calibration",
            "Overclaim rate",
            "Reviewer correction burden",
        ],
        insufficient_metrics=[
            "Detection accuracy alone is insufficient because a visible candidate does not equal final quality failure.",
        ],
        misalignment_risks=[
            "The task may treat a visual candidate as a final pass/fail decision.",
            "The report may turn a visibility limitation into a definitive quality claim.",
            "A model metric may be mistaken for operational readiness.",
        ],
        human_review_required=[
            "Any final pass/fail suggestion",
            "Low-confidence candidate detection",
            "Poor visibility or ambiguous source material",
            "Any wording that implies deployment readiness",
        ],
        implementation_routes=[
            "Dataset/benchmark paper for evidence completeness and overclaim rate",
            "Human-in-the-loop workflow demo for conservative summary drafting",
            "ClaimHarness audit layer for inspection claim-evidence checking",
        ],
    )


def cultural_archive_profile(source_problem: str) -> AlignmentPackage:
    return AlignmentPackage(
        profile="cultural_archive",
        project_name="cultural_archive_interpretation_alignment",
        title="Cultural Archive Interpretation Alignment",
        source_problem=source_problem,
        domain_goal=(
            "Evaluate whether AI outputs align visible archive details, catalog notes, "
            "source context, and expert interpretation boundaries."
        ),
        not_allowed_goal="object-only captioning as expert interpretation",
        meaningful_outputs=[
            "Region-note alignment evidence",
            "Interpretation fidelity notes",
            "Uncertainty-aware interpretation candidates",
        ],
        non_meaningful_outputs=[
            "Generic object captioning",
            "Authoritative interpretive claims without source or expert support",
        ],
        workflow_steps=[
            "Archive item inspection",
            "Detail and metadata identification",
            "Catalog note reading",
            "Context and provenance lookup",
            "Interpretive claim formation",
            "Expert review",
        ],
        painpoints=[
            PainpointOpportunity(
                workflow_step="catalog note reading",
                pain_point="Catalog concepts are difficult to align with visible details.",
                ai_opportunity="Suggest candidate region-note links.",
                risk="medium",
                human_role="validate interpretive links",
            ),
            PainpointOpportunity(
                workflow_step="interpretive claim formation",
                pain_point="Object descriptions can be mistaken for cultural interpretation.",
                ai_opportunity="Flag object-only explanations as weak.",
                risk="high",
                human_role="review cultural meaning claims",
            ),
        ],
        concepts=[
            ConceptAlignment(
                domain_concept="contextual absence",
                ai_representation="empty region or missing metadata",
                alignment_status="misaligned",
                misalignment_risk="absence may be meaningful, unknown, or simply undocumented",
            ),
            ConceptAlignment(
                domain_concept="material or stylistic feature",
                ai_representation="texture, line, or visual feature",
                alignment_status="partial",
                misalignment_risk="requires domain vocabulary and expert interpretation",
            ),
            ConceptAlignment(
                domain_concept="catalog note",
                ai_representation="caption or text prompt",
                alignment_status="partial",
                misalignment_risk="notes are interpretive evidence, not simple image labels",
            ),
        ],
        ai_task_type=[
            "multimodal_archive_reasoning_evaluation",
            "region_note_alignment",
            "evidence_grounded_explanation",
        ],
        inputs=[
            "image_region",
            "catalog_note_segment",
            "metadata_field",
            "context_note",
        ],
        outputs=[
            "visual_element_identification",
            "context_reference_detection",
            "interpretive_alignment_score",
            "evidence_grounded_explanation",
        ],
        required_evidence={
            "archive_interpretation": [
                "visible_image_detail",
                "catalog_or_context_note",
                "alternative_interpretation_check",
            ]
        },
        forbidden_without={
            "archive_interpretation": [
                "expert_review",
                "catalog_or_context_support",
            ]
        },
        evaluation_protocol=[
            "Object recognition accuracy",
            "Region-note alignment",
            "Domain concept fidelity",
            "Hallucinated interpretation rate",
            "Expert review score",
        ],
        insufficient_metrics=[
            "Caption similarity is insufficient because object-level description does not equal domain interpretation.",
        ],
        misalignment_risks=[
            "The task may reduce archive interpretation to image captioning.",
            "The model may hallucinate provenance or contextual meaning.",
            "The evaluation may reward fluent style imitation instead of evidence-grounded interpretation.",
        ],
        human_review_required=[
            "Ambiguous interpretive claims",
            "Provenance or attribution claims",
            "Interpretations not grounded in visible detail and catalog/context notes",
        ],
        implementation_routes=[
            "Benchmark paper for region-note alignment",
            "Expert annotation protocol for domain concept fidelity",
            "ClaimHarness audit of interpretation claims and evidence links",
        ],
    )


def training_policy_profile(source_problem: str) -> AlignmentPackage:
    return AlignmentPackage(
        profile="training_policy",
        project_name="training_policy_response_alignment",
        title="Training Policy Response Alignment",
        source_problem=source_problem,
        domain_goal=(
            "Evaluate whether generated training or policy-support answers remain source-grounded, "
            "conceptually aligned, and appropriately bounded for review."
        ),
        not_allowed_goal="fluent answer generation as policy compliance",
        meaningful_outputs=[
            "Source-grounded answer audit",
            "Concept framing consistency checks",
            "Reviewer correction burden estimate",
        ],
        non_meaningful_outputs=[
            "Fluency-only answer scores",
            "Generic factual QA accuracy without policy or training-context review",
        ],
        workflow_steps=[
            "Training objective selection",
            "Policy or guidance source selection",
            "Question or scenario design",
            "Model response generation",
            "Concept and source-grounding audit",
            "Reviewer correction and approval",
        ],
        painpoints=[
            PainpointOpportunity(
                workflow_step="model response generation",
                pain_point="Fluent answers may hide unsupported, misframed, or out-of-scope claims.",
                ai_opportunity="Classify unsupportedness, scope drift, and framing risks.",
                risk="high",
                human_role="review policy-sensitive explanations",
            ),
            PainpointOpportunity(
                workflow_step="reviewer correction and approval",
                pain_point="Manual review is slow and hard to standardize.",
                ai_opportunity="Produce review checklists and evidence gaps.",
                risk="medium",
                human_role="approve or revise final training content",
            ),
        ],
        concepts=[
            ConceptAlignment(
                domain_concept="hallucination",
                ai_representation="unsupported factual or policy statement",
                alignment_status="partial",
                misalignment_risk="unsupportedness may include scope or framing drift, not just false facts",
            ),
            ConceptAlignment(
                domain_concept="policy scope",
                ai_representation="topic or intent classification",
                alignment_status="partial",
                misalignment_risk="scope drift may not appear as factual error",
            ),
            ConceptAlignment(
                domain_concept="understanding",
                ai_representation="answer fluency",
                alignment_status="misaligned",
                misalignment_risk="fluent answers can still misstate source boundaries or procedures",
            ),
        ],
        ai_task_type=[
            "policy_sensitive_response_audit",
            "source_grounding_check",
            "scope_and_framing_risk_detection",
        ],
        inputs=[
            "training_objective",
            "policy_source_fragment",
            "learner_or_staff_question",
            "model_answer",
        ],
        outputs=[
            "unsupported_claims",
            "concept_alignment_notes",
            "scope_or_framing_risk",
            "reviewer_flag",
        ],
        required_evidence={
            "training_explanation": [
                "training_objective",
                "policy_source_fragment",
                "uncertainty_or_scope_statement",
            ]
        },
        forbidden_without={
            "training_explanation": [
                "reviewer_approval",
                "source_grounding",
            ]
        },
        evaluation_protocol=[
            "Factual correctness",
            "Concept relation consistency",
            "Source-groundedness",
            "Scope and framing stability",
            "Reviewer correction burden",
        ],
        insufficient_metrics=[
            "Answer fluency is insufficient because the key risk lies in scope, framing, and source grounding.",
        ],
        misalignment_risks=[
            "The task may reduce training or policy support to factual QA.",
            "The model may produce fluent but unsupported procedural claims.",
            "The evaluation may miss framing instability across equivalent questions.",
        ],
        human_review_required=[
            "Policy-sensitive or procedural explanation",
            "Unsupported claim about source guidance",
            "Ambiguous framing or contested interpretation",
        ],
        implementation_routes=[
            "Annotation schema for unsupportedness, scope drift, and source grounding",
            "Reviewer-in-the-loop training workflow",
            "ClaimHarness audit of response claims against source fragments",
        ],
    )


def generic_profile(source_problem: str) -> AlignmentPackage:
    return AlignmentPackage(
        profile="generic",
        project_name="interdisciplinary_problem_alignment",
        title="Interdisciplinary Problem Alignment",
        source_problem=source_problem,
        domain_goal="Clarify the workflow, evidence standards, and AI task boundaries before model building.",
        not_allowed_goal="direct automation of domain judgement",
        meaningful_outputs=[
            "Workflow map",
            "AI opportunity map",
            "Evidence and evaluation checklist",
        ],
        non_meaningful_outputs=[
            "A generic model proposal without domain evidence standards",
        ],
        workflow_steps=[
            "Domain intake",
            "Workflow reconstruction",
            "Decision point identification",
            "Evidence standard mapping",
            "AI task formulation",
            "Human review design",
        ],
        painpoints=[
            PainpointOpportunity(
                workflow_step="workflow reconstruction",
                pain_point="Implicit practice is hard to translate into an AI task.",
                ai_opportunity="Structure workflow steps and decision points.",
                risk="medium",
                human_role="validate the workflow map",
            )
        ],
        concepts=[
            ConceptAlignment(
                domain_concept="domain judgement",
                ai_representation="model prediction",
                alignment_status="partial",
                misalignment_risk="prediction may omit context, evidence, and human responsibility",
            )
        ],
        ai_task_type=["workflow_discovery", "problem_alignment"],
        inputs=["problem_brief", "domain_notes"],
        outputs=["alignment_package", "human_review_points"],
        required_evidence={"domain_claim": ["domain_note", "workflow_step", "human_review_boundary"]},
        forbidden_without={"domain_claim": ["domain_practitioner_review"]},
        evaluation_protocol=[
            "Workflow fidelity",
            "Evidence completeness",
            "Human review coverage",
            "Misalignment risk reduction",
        ],
        insufficient_metrics=[
            "Generic accuracy is insufficient when the task boundary is not aligned with the domain problem.",
        ],
        misalignment_risks=[
            "The AI task may optimize an easy proxy rather than the domain goal.",
        ],
        human_review_required=[
            "Any final domain judgement",
            "Any claim about deployment readiness",
        ],
        implementation_routes=[
            "Interview-driven workflow discovery",
            "Small benchmark around aligned task specifications",
            "ClaimHarness audit for generated claims",
        ],
    )
