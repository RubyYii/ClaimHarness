from .schemas import AlignmentPackage, ConceptAlignment, PainpointOpportunity


def hsg_profile(source_problem: str) -> AlignmentPackage:
    return AlignmentPackage(
        profile="hsg",
        project_name="evidence_ready_hsg_support",
        title="HSG Evidence-Ready Second-Reader Support",
        source_problem=source_problem,
        domain_goal=(
            "Support reviewable HSG interpretation by preserving image quality, "
            "contrast passage, visibility, uncertainty, and clinician judgement."
        ),
        not_allowed_goal="autonomous diagnosis",
        meaningful_outputs=[
            "Evidence sidecar for clinician review",
            "Conservative structured report draft",
            "Human review flag for low-confidence or high-risk findings",
        ],
        non_meaningful_outputs=[
            "A standalone obstruction diagnosis from mask absence",
            "A deployment-ready clinical conclusion without validation",
        ],
        workflow_steps=[
            "Patient preparation",
            "Image acquisition",
            "Image quality judgement",
            "Contrast passage observation",
            "Tubal visibility judgement",
            "Clinician interpretation",
            "Report drafting",
            "Review and correction",
        ],
        painpoints=[
            PainpointOpportunity(
                workflow_step="image quality judgement",
                pain_point="Visibility and contrast timing are inconsistently recorded.",
                ai_opportunity="Generate image-quality and visibility sidecars.",
                risk="medium",
                human_role="confirm quality labels",
            ),
            PainpointOpportunity(
                workflow_step="contrast passage observation",
                pain_point="Repeated visual checking can be slow and subjective.",
                ai_opportunity="Highlight candidate regions and uncertainty.",
                risk="medium",
                human_role="confirm or reject highlighted evidence",
            ),
            PainpointOpportunity(
                workflow_step="report drafting",
                pain_point="Wording may overstate what image evidence supports.",
                ai_opportunity="Draft conservative evidence-grounded report text.",
                risk="high",
                human_role="edit and approve final wording",
            ),
        ],
        concepts=[
            ConceptAlignment(
                domain_concept="tubal obstruction",
                ai_representation="classification label",
                alignment_status="partial",
                misalignment_risk="segmentation absence may mean poor visibility rather than obstruction",
            ),
            ConceptAlignment(
                domain_concept="tube visibility",
                ai_representation="segmentation confidence plus contrast quality",
                alignment_status="aligned",
                misalignment_risk="image quality and timing still need clinician interpretation",
            ),
            ConceptAlignment(
                domain_concept="clinical readiness",
                ai_representation="deployment status",
                alignment_status="high-risk",
                misalignment_risk="requires validation beyond model metrics",
            ),
        ],
        ai_task_type=[
            "image_quality_assessment",
            "anatomy_visibility_segmentation",
            "evidence_sidecar_generation",
            "conservative_report_drafting",
        ],
        inputs=[
            "original_image",
            "segmentation_overlay",
            "confidence_score",
            "image_quality_label",
        ],
        outputs=[
            "evidence_summary",
            "uncertainty_statement",
            "human_review_flag",
            "structured_draft_report",
        ],
        required_evidence={
            "clinical_suggestion": [
                "original_image_region",
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
            "clinical_suggestion": [
                "clinician_confirmation",
                "image_quality_assessment",
            ],
        },
        evaluation_protocol=[
            "Segmentation quality for visible anatomy",
            "Evidence completeness for each report statement",
            "Uncertainty calibration",
            "Overclaim rate",
            "Clinician correction burden",
        ],
        insufficient_metrics=[
            "Dice / IoU alone is insufficient because segmentation quality does not equal diagnostic reliability.",
        ],
        misalignment_risks=[
            "The task may treat segmentation absence as tubal obstruction.",
            "The report may turn a visibility limitation into a definitive clinical claim.",
            "A model metric may be mistaken for clinical readiness.",
        ],
        human_review_required=[
            "Any tubal abnormality suggestion",
            "Low-confidence segmentation",
            "Poor visibility or ambiguous contrast passage",
            "Any wording that implies diagnosis or deployment readiness",
        ],
        implementation_routes=[
            "Dataset/benchmark paper for evidence completeness and overclaim rate",
            "Human-in-the-loop workflow demo for conservative report drafting",
            "ClaimHarness audit layer for report claim-evidence checking",
        ],
    )


def chinese_painting_profile(source_problem: str) -> AlignmentPackage:
    return AlignmentPackage(
        profile="chinese_painting",
        project_name="vlm_cultural_interpretation_alignment",
        title="VLM Cultural Interpretation Alignment for Chinese Painting",
        source_problem=source_problem,
        domain_goal=(
            "Evaluate whether VLM outputs align visible image details, commentary text, "
            "historical context, and culturally situated interpretation."
        ),
        not_allowed_goal="object-only captioning as cultural understanding",
        meaningful_outputs=[
            "Region-commentary alignment evidence",
            "Cultural concept fidelity notes",
            "Uncertainty-aware interpretation candidates",
        ],
        non_meaningful_outputs=[
            "Generic object captioning",
            "Universal symbolic claims without textual or historical support",
        ],
        workflow_steps=[
            "Image inspection",
            "Detail and inscription identification",
            "Commentary reading",
            "Historical and aesthetic context lookup",
            "Interpretive claim formation",
            "Expert review",
        ],
        painpoints=[
            PainpointOpportunity(
                workflow_step="commentary reading",
                pain_point="Commentary concepts are difficult to align with image regions.",
                ai_opportunity="Suggest candidate region-commentary links.",
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
                domain_concept="blank space",
                ai_representation="white pixels or empty region",
                alignment_status="misaligned",
                misalignment_risk="visual emptiness may carry compositional and cultural meaning",
            ),
            ConceptAlignment(
                domain_concept="brushwork",
                ai_representation="texture and line features",
                alignment_status="partial",
                misalignment_risk="requires art-historical vocabulary and expert interpretation",
            ),
            ConceptAlignment(
                domain_concept="scholar commentary",
                ai_representation="caption or text prompt",
                alignment_status="partial",
                misalignment_risk="commentary is interpretive evidence, not a simple image label",
            ),
        ],
        ai_task_type=[
            "multimodal_cultural_reasoning_evaluation",
            "region_commentary_alignment",
            "evidence_grounded_explanation",
        ],
        inputs=[
            "image_region",
            "commentary_segment",
            "modern_translation",
            "historical_context_note",
        ],
        outputs=[
            "visual_element_identification",
            "cultural_reference_detection",
            "interpretive_alignment_score",
            "evidence_grounded_explanation",
        ],
        required_evidence={
            "cultural_interpretation": [
                "visible_image_detail",
                "textual_or_historical_context",
                "alternative_interpretation_check",
            ]
        },
        forbidden_without={
            "cultural_interpretation": [
                "expert_review",
                "commentary_support",
            ]
        },
        evaluation_protocol=[
            "Object recognition accuracy",
            "Region-commentary alignment",
            "Cultural concept fidelity",
            "Hallucinated interpretation rate",
            "Expert review score",
        ],
        insufficient_metrics=[
            "Caption similarity is insufficient because object-level description does not equal cultural interpretation.",
        ],
        misalignment_risks=[
            "The task may reduce cultural interpretation to image captioning.",
            "The model may hallucinate art-historical context.",
            "The evaluation may reward fluent style imitation instead of evidence-grounded understanding.",
        ],
        human_review_required=[
            "Ambiguous symbolic claims",
            "Historical attribution",
            "Interpretations not grounded in visible detail and commentary",
        ],
        implementation_routes=[
            "Benchmark paper for region-commentary alignment",
            "Expert annotation protocol for cultural concept fidelity",
            "ClaimHarness audit of interpretation claims and evidence links",
        ],
    )


def political_education_profile(source_problem: str) -> AlignmentPackage:
    return AlignmentPackage(
        profile="political_education",
        project_name="value_sensitive_llm_risk_evaluation",
        title="LLM Risk Evaluation for Value-Sensitive Political Theory Education",
        source_problem=source_problem,
        domain_goal=(
            "Evaluate whether model answers remain source-grounded, conceptually aligned, "
            "and appropriately bounded in value-sensitive educational settings."
        ),
        not_allowed_goal="fluent answer generation as educational safety",
        meaningful_outputs=[
            "Source-grounded answer audit",
            "Concept framing consistency checks",
            "Teacher review burden estimate",
        ],
        non_meaningful_outputs=[
            "Fluency-only answer scores",
            "Generic factual QA accuracy without value-sensitive framing review",
        ],
        workflow_steps=[
            "Curriculum concept selection",
            "Source text selection",
            "Question or scenario design",
            "Model response generation",
            "Concept and source-grounding audit",
            "Teacher review and correction",
        ],
        painpoints=[
            PainpointOpportunity(
                workflow_step="model response generation",
                pain_point="Fluent answers may hide unsupported or misframed claims.",
                ai_opportunity="Classify unsupportedness and concept-framing risks.",
                risk="high",
                human_role="review value-sensitive explanations",
            ),
            PainpointOpportunity(
                workflow_step="teacher review and correction",
                pain_point="Manual review is slow and hard to standardize.",
                ai_opportunity="Produce review checklists and evidence gaps.",
                risk="medium",
                human_role="approve or revise final educational content",
            ),
        ],
        concepts=[
            ConceptAlignment(
                domain_concept="hallucination",
                ai_representation="unsupported factual or doctrinal statement",
                alignment_status="partial",
                misalignment_risk="unsupportedness may include concept framing, not just false facts",
            ),
            ConceptAlignment(
                domain_concept="bias",
                ai_representation="classification of stance or sentiment",
                alignment_status="partial",
                misalignment_risk="ideological framing imbalance may not appear as sentiment bias",
            ),
            ConceptAlignment(
                domain_concept="understanding",
                ai_representation="answer fluency",
                alignment_status="misaligned",
                misalignment_risk="fluent answers can still misstate concept relations",
            ),
        ],
        ai_task_type=[
            "value_sensitive_response_audit",
            "source_grounding_check",
            "concept_framing_risk_detection",
        ],
        inputs=[
            "curriculum_concept",
            "source_text_fragment",
            "student_question",
            "model_answer",
        ],
        outputs=[
            "unsupported_claims",
            "concept_alignment_notes",
            "value_framing_risk",
            "teacher_review_flag",
        ],
        required_evidence={
            "educational_explanation": [
                "curriculum_concept",
                "source_text_fragment",
                "uncertainty_or_scope_statement",
            ]
        },
        forbidden_without={
            "educational_explanation": [
                "teacher_review",
                "source_grounding",
            ]
        },
        evaluation_protocol=[
            "Factual correctness",
            "Concept relation consistency",
            "Source-groundedness",
            "Value framing stability",
            "Teacher correction burden",
        ],
        insufficient_metrics=[
            "Answer fluency is insufficient because the key risk lies in concept framing and source grounding.",
        ],
        misalignment_risks=[
            "The task may reduce value-sensitive education to factual QA.",
            "The model may produce fluent but unsupported conceptual claims.",
            "The evaluation may miss framing instability across equivalent questions.",
        ],
        human_review_required=[
            "Normative or value-sensitive explanation",
            "Unsupported claim about curriculum concepts",
            "Ambiguous framing or contested interpretation",
        ],
        implementation_routes=[
            "Annotation schema for hallucination, framing risk, and source grounding",
            "Teacher-in-the-loop review workflow",
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
