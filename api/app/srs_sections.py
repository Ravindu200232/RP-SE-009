from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .common import has_answer_value
from .config import QUESTION_DEFAULTS
from .question_maker import build_question_plan


def normalize_priority(value: Any, default: str = "Medium") -> str:
    text = str(value or "").strip().lower()
    if text.startswith("h"):
        return "High"
    if text.startswith("l"):
        return "Low"
    if text.startswith("m"):
        return "Medium"
    return default


def build_sections_payload(
    session: dict[str, Any],
    name: str,
    features: list[str],
    users: list[str],
    platforms: list[str],
    auth_method: str,
    integrations: list[str],
    compliance: list[str],
    stack: dict[str, str],
) -> dict[str, Any]:
    summary = session.get("analysis_summary") or build_question_plan(session)["summary"]
    return {
        "introduction": {
            "purpose": f"This document defines the functional and non-functional requirements for {name}.",
            "product_scope": {
                "summary": summary,
                "business_objectives": ["Clarify scope early", "Create a delivery-ready requirements baseline"],
                "benefits": ["Reduces ambiguity", "Improves downstream handoff", "Transforms guided interview answers into a structured IEEE SRS"],
                "goals": [f"Deliver the first usable release of {name}.", "Support JSON and PDF artifact export"],
            },
        },
        "overall_description": {
            "product_perspective": {
                "system_context": f"{name} is delivered through {', '.join(platforms).lower()} with an API layer, AI orchestration, persistent storage, and downloadable artifacts.",
                "product_origin": "New system",
                "related_systems": [{"name": item, "relationship": "Integration", "interface_summary": f"Used for {item.lower()}."} for item in integrations[:3]],
                "context_diagram_reference": "Diagram generation is deferred. Review the analyst workspace and service breakdown for the current phase.",
            },
            "product_functions": [{"function_id": f"PF-{index + 1:03d}", "name": feature, "description": f"{name} supports {feature.lower()} as part of the core workflow."} for index, feature in enumerate(features[:5])],
            "user_classes_and_characteristics": [{"user_class_id": f"UC-{index + 1:03d}", "user_class_name": user, "description": f"{user} uses the platform to complete the main workflow.", "technical_expertise": "Low to Medium", "security_or_privilege_level": "Role-based", "education_or_experience": "Basic digital literacy", "frequency_of_use": "Daily" if index == 0 else "Weekly", "importance_rank": index + 1, "notes": ""} for index, user in enumerate(users[:4])],
        },
        "external_interface_requirements": {
            "user_interfaces": [
                {"ui_id": "UI-001", "name": "New Project page", "description": "Collects text, files, and optional voice input.", "input_elements": ["Text area", "Upload control", "Voice recorder"], "output_elements": ["Analysis summary", "Upload list"], "layout_constraints": ["Responsive layout"], "accessibility_requirements": ["Keyboard support"], "error_message_standards": ["Human-readable validation"], "design_reference": "New Project"},
                {"ui_id": "UI-002", "name": "Question and answer workspace", "description": "Captures guided interview answers before generation.", "input_elements": ["Chat questions", "Answer composer"], "output_elements": ["Progress state", "Draft readiness"], "layout_constraints": ["Responsive layout"], "accessibility_requirements": ["Touch-friendly controls"], "error_message_standards": ["Inline validation"], "design_reference": "Agent 1 interview"},
                {"ui_id": "UI-003", "name": "Agent 1 review dashboard", "description": "Shows SRS, requirements, JSON, risks, and export actions.", "input_elements": ["Tabs", "Export buttons"], "output_elements": ["SRS document", "JSON", "Validation state"], "layout_constraints": ["Two-column desktop layout"], "accessibility_requirements": ["Semantic tabs"], "error_message_standards": ["Explicit artifact status"], "design_reference": "Agent 1 dashboard"},
            ],
            "software_interfaces": [{"software_interface_id": f"SI-{index + 1:03d}", "component_name": item, "component_version": "Current stable", "description": f"Integration with {item.lower()}.", "incoming_data_items": ["Request payload"], "outgoing_data_items": ["Response payload"], "services_needed": ["Authentication"], "communication_method": "REST or webhook", "shared_data": ["Project metadata"], "implementation_constraints": ["Use secure transport"]} for index, item in enumerate(integrations[:4])],
            "hardware_interfaces": [{"hardware_interface_id": "HI-001", "device_name": "Microphone", "description": "Used for optional voice notes.", "supported_device_types": ["Built-in microphone", "USB microphone"], "data_interaction": "Captures audio", "protocol": "Browser media devices API"}] if any(upload["kind"] == "audio" for upload in session.get("uploads", [])) else [],
            "communications_interfaces": [
                {"communication_interface_id": "CI-001", "name": "Browser to API", "description": "Interactive application traffic.", "protocols": ["HTTPS"], "message_format": "JSON and multipart form data", "security_or_encryption": "TLS 1.2+", "data_transfer_rate": "Interactive", "synchronization_mechanism": "Request-response"},
                {"communication_interface_id": "CI-002", "name": "Artifact delivery", "description": "Downloads JSON and PDF artifacts.", "protocols": ["HTTPS"], "message_format": "JSON and PDF", "security_or_encryption": "TLS 1.2+", "data_transfer_rate": "On demand", "synchronization_mechanism": "Direct download"},
            ],
        },
        "system_features": [
            {
                "feature_id": f"FEAT-{index + 1:03d}",
                "feature_name": feature,
                "description_and_priority": {"description": f"The platform provides {feature.lower()} as part of the main workflow.", "priority": "High" if index < 3 else "Medium", "benefit_score": max(6, 10 - index), "penalty_score": 7 if index < 3 else 5, "cost_score": 5, "risk_score": 4},
                "stimulus_response_sequences": [{"sequence_id": f"SRSQ-{index + 1:03d}", "stimulus": f"User initiates {feature.lower()}", "preconditions": ["An active session exists."], "system_response": f"The system processes {feature.lower()} and returns a visible status update.", "postconditions": [f"{feature} data is available for review."]}],
                "functional_requirements": [
                    {"requirement_id": f"REQ-{index + 1:02d}1", "title": f"{feature} submission", "description": f"The system shall support {feature.lower()} through the primary interface.", "actor": "Primary User", "trigger": "User submits an action", "inputs": [{"name": "payload", "type": "json", "required": True, "validation_rules": ["Validate required fields"]}], "processing_logic": ["Validate input", "Persist state", "Return a clear status"], "outputs": [{"name": "result", "type": "json", "description": "Structured action result"}], "business_rules_applied": ["BR-001"], "error_conditions": [{"condition": "Invalid input", "system_behavior": "Show a validation message"}], "acceptance_criteria": ["Valid actions succeed", "Errors are understandable to non-technical users"], "priority": "High", "status": "draft", "traceability": {"linked_user_class_ids": ["UC-001"], "linked_interface_ids": ["UI-002"], "linked_test_case_ids": [f"TC-{index + 1:03d}-01"]}},
                    {"requirement_id": f"REQ-{index + 1:02d}2", "title": f"{feature} review", "description": f"The system shall display {feature.lower()} history and status to authorized users.", "actor": "Administrator", "trigger": "User opens a review screen", "inputs": [{"name": "filters", "type": "json", "required": False, "validation_rules": ["Ignore empty filters"]}], "processing_logic": ["Load records", "Sort results", "Render the view"], "outputs": [{"name": "history", "type": "json", "description": "Matching records and status"}], "business_rules_applied": ["BR-001"], "error_conditions": [{"condition": "Data unavailable", "system_behavior": "Show a retryable error state"}], "acceptance_criteria": ["Authorized users can review status"], "priority": "Medium", "status": "draft", "traceability": {"linked_user_class_ids": ["UC-001"], "linked_interface_ids": ["UI-003"], "linked_test_case_ids": [f"TC-{index + 1:03d}-02"]}},
                ],
            }
            for index, feature in enumerate(features)
        ],
        "other_nonfunctional_requirements": {
            "performance_requirements": [{"requirement_id": "NFR-PERF-001", "description": "The system shall return primary page loads and standard API actions within 2 seconds under normal load.", "rationale": "Keeps the guided workflow responsive.", "measurement_method": "Monitoring and tracing", "target_metric": "95th percentile response time", "target_value": "<= 2 seconds", "conditions": "Normal business-hour traffic"}],
            "safety_requirements": [{"requirement_id": "NFR-SAFE-001", "description": "The system shall prevent accidental loss of active project work.", "hazard": "Loss of project inputs or artifacts", "safeguards": ["Persist session state", "Confirm destructive actions"], "prevented_actions": ["Silent discard of work"], "compliance_reference": "Internal product policy"}],
            "security_requirements": [{"requirement_id": "NFR-SEC-001", "description": "The system shall protect uploaded materials, generated artifacts, and session metadata.", "authentication_requirements": [auth_method], "authorization_requirements": ["Role-based access to projects and exports"], "data_protection_requirements": ["TLS in transit", "Encrypted storage"], "privacy_requirements": compliance, "compliance_reference": ", ".join(compliance), "verification_method": "Security review and integration tests"}],
            "software_quality_attributes": [{"attribute_id": "QA-001", "attribute_name": "Usability", "description": "Non-technical users should complete the intake and answer flow without training.", "measurement": "Task completion rate", "target_value": ">= 90%", "priority": "High"}],
            "business_rules": [{"rule_id": "BR-001", "description": "The platform only marks an SRS ready when required sections have content and export artifacts can be produced.", "applicable_roles": ["Administrator", "Primary User"], "conditions": ["Required sections exist"], "enforcement_requirements": ["REQ-011", "REQ-021"]}],
        },
        "other_requirements": {
            "database_requirements": [{"requirement_id": "DB-001", "description": "The database shall store sessions, answers, upload metadata, generated SRS JSON, and validation results.", "entities": ["Session", "Upload", "AnswerSet", "SRSArtifact", "ValidationReport"], "retention_policy": "Retain project data until policy-based cleanup", "backup_policy": "Daily backup with point-in-time recovery"}],
            "internationalization_requirements": [{"requirement_id": "I18N-001", "description": "The product should support future localization without changing the API contract.", "supported_languages": ["en"], "locale_rules": ["ISO date formatting for API payloads"]}],
            "legal_requirements": [{"requirement_id": "LEGAL-001", "description": "The platform shall state how uploaded materials are stored and used for generation.", "jurisdiction": "Project-dependent", "reference": ", ".join(compliance)}],
            "reuse_objectives": [{"objective_id": "REUSE-001", "description": "Reuse question planning, validation, and export modules across future agents.", "target_components": ["Question planner", "Validation engine", "Artifact exporter"]}],
            "additional_requirements": [{"requirement_id": "OTH-001", "description": f"Recommended delivery stack: {stack['frontend']} with {stack['api']} and {stack['ai_orchestrator']}."}],
        },
    }


def build_appendices_payload(info: dict[str, Any]) -> dict[str, Any]:
    return {
        "glossary": [{"term": "SRS", "definition": "Software Requirements Specification"}, {"term": "NFR", "definition": "Nonfunctional Requirement"}],
        "analysis_models": [
            {"model_id": "AM-001", "model_type": "Interview Coverage Summary", "description": "Summarises AI-driven questions, user answers, and completion coverage for the current SRS.", "reference": "See analyst workspace interview review."},
            {"model_id": "AM-002", "model_type": "Service Outline", "description": "Summarises service responsibilities and handoff boundaries for the current build phase.", "reference": "See risk and stack review."},
        ],
        "to_be_determined_list": [{"tbd_id": f"TBD-{index + 1:03d}", "description": f"Clarify {question['key'].replace('_', ' ')}.", "owner": "Product owner", "status": "open", "target_resolution_date": (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()} for index, question in enumerate(QUESTION_DEFAULTS) if not has_answer_value(info.get(question["key"]))],
    }


def build_service_catalog() -> list[dict[str, Any]]:
    return [
        {"service_name": "api-gateway", "port": 8200, "summary": "Routes frontend requests to backend capabilities.", "endpoints": [{"method": "POST", "path": "/api/v1/sessions", "description": "Create a new session", "entities": ["Session"], "dependencies": ["project-service"]}, {"method": "POST", "path": "/api/v1/sessions/{id}/intake", "description": "Submit idea and files", "entities": ["Session", "Upload"], "dependencies": ["ingestion-service", "srs-service"]}]},
        {"service_name": "project-service", "port": 8201, "summary": "Stores session state, answers, and document metadata.", "endpoints": [{"method": "GET", "path": "/api/v1/sessions/{id}", "description": "Load a session", "entities": ["Session"], "dependencies": ["artifact-service"]}, {"method": "POST", "path": "/api/v1/sessions/{id}/answers", "description": "Save answers and generate the SRS", "entities": ["AnswerSet", "SRSDocument"], "dependencies": ["srs-service"]}]},
        {"service_name": "artifact-service", "port": 8202, "summary": "Publishes JSON and PDF artifacts for download.", "endpoints": [{"method": "GET", "path": "/api/v1/sessions/{id}/artifacts/srs.json", "description": "Download machine-readable JSON", "entities": ["SRSDocument"], "dependencies": ["object-storage"]}, {"method": "GET", "path": "/api/v1/sessions/{id}/artifacts/srs.pdf", "description": "Download the PDF artifact", "entities": ["SRSArtifact"], "dependencies": ["object-storage"]}]},
    ]


def apply_deepseek_srs_content_pack(srs: dict[str, Any], content_pack: dict[str, Any], interview_workspace: dict[str, Any]) -> dict[str, Any]:
    if not content_pack:
        return srs

    sections = srs.setdefault("sections", {})
    introduction = sections.setdefault("introduction", {})
    scope = introduction.setdefault("product_scope", {})
    overall = sections.setdefault("overall_description", {})
    perspective = overall.setdefault("product_perspective", {})
    interfaces = sections.setdefault("external_interface_requirements", {})
    nfr = sections.setdefault("other_nonfunctional_requirements", {})
    other = sections.setdefault("other_requirements", {})

    intro_pack = content_pack.get("introduction") or {}
    if intro_pack.get("purpose"):
        introduction["purpose"] = str(intro_pack["purpose"]).strip()
    if intro_pack.get("product_scope_summary"):
        scope["summary"] = str(intro_pack["product_scope_summary"]).strip()
    if isinstance(intro_pack.get("business_objectives"), list) and intro_pack["business_objectives"]:
        scope["business_objectives"] = [str(item).strip() for item in intro_pack["business_objectives"] if str(item).strip()]
    if isinstance(intro_pack.get("benefits"), list) and intro_pack["benefits"]:
        scope["benefits"] = [str(item).strip() for item in intro_pack["benefits"] if str(item).strip()]
    if isinstance(intro_pack.get("goals"), list) and intro_pack["goals"]:
        scope["goals"] = [str(item).strip() for item in intro_pack["goals"] if str(item).strip()]

    perspective_pack = content_pack.get("product_perspective") or {}
    if perspective_pack.get("system_context"):
        perspective["system_context"] = str(perspective_pack["system_context"]).strip()
    if isinstance(perspective_pack.get("related_systems"), list) and perspective_pack["related_systems"]:
        perspective["related_systems"] = [
            {
                "name": str(item.get("name") or f"System {index + 1}").strip(),
                "relationship": "Integration",
                "interface_summary": str(item.get("interface_summary") or "").strip(),
            }
            for index, item in enumerate(perspective_pack["related_systems"])
            if isinstance(item, dict) and (item.get("name") or item.get("interface_summary"))
        ]

    if isinstance(content_pack.get("product_functions"), list) and content_pack["product_functions"]:
        overall["product_functions"] = [
            {
                "function_id": f"PF-{index + 1:03d}",
                "name": str(item.get("name") or f"Function {index + 1}").strip(),
                "description": str(item.get("description") or "").strip(),
            }
            for index, item in enumerate(content_pack["product_functions"])
            if isinstance(item, dict) and (item.get("name") or item.get("description"))
        ]

    if isinstance(content_pack.get("user_classes"), list) and content_pack["user_classes"]:
        overall["user_classes_and_characteristics"] = [
            {
                "user_class_id": f"UC-{index + 1:03d}",
                "user_class_name": str(item.get("name") or f"User Class {index + 1}").strip(),
                "description": str(item.get("description") or "").strip(),
                "technical_expertise": str(item.get("technical_expertise") or "Low to Medium").strip(),
                "security_or_privilege_level": "Role-based",
                "education_or_experience": "Basic digital literacy",
                "frequency_of_use": str(item.get("frequency_of_use") or "Weekly").strip(),
                "importance_rank": index + 1,
                "notes": "",
            }
            for index, item in enumerate(content_pack["user_classes"])
            if isinstance(item, dict) and (item.get("name") or item.get("description"))
        ]

    if isinstance(content_pack.get("user_interfaces"), list) and content_pack["user_interfaces"]:
        interfaces["user_interfaces"] = [
            {
                "ui_id": f"UI-{index + 1:03d}",
                "name": str(item.get("name") or f"Interface {index + 1}").strip(),
                "description": str(item.get("description") or "").strip(),
                "input_elements": ["AI-guided input"],
                "output_elements": ["Structured response"],
                "layout_constraints": ["Responsive layout"],
                "accessibility_requirements": ["Keyboard support"],
                "error_message_standards": ["Human-readable validation"],
                "design_reference": "Agent 1 UI",
            }
            for index, item in enumerate(content_pack["user_interfaces"])
            if isinstance(item, dict) and (item.get("name") or item.get("description"))
        ]

    if isinstance(content_pack.get("software_interfaces"), list) and content_pack["software_interfaces"]:
        interfaces["software_interfaces"] = [
            {
                "software_interface_id": f"SI-{index + 1:03d}",
                "component_name": str(item.get("name") or f"Integration {index + 1}").strip(),
                "component_version": "Current stable",
                "description": str(item.get("description") or "").strip(),
                "incoming_data_items": ["Request payload"],
                "outgoing_data_items": ["Response payload"],
                "services_needed": ["Authentication"],
                "communication_method": "REST or webhook",
                "shared_data": ["Project metadata"],
                "implementation_constraints": ["Use secure transport"],
            }
            for index, item in enumerate(content_pack["software_interfaces"])
            if isinstance(item, dict) and (item.get("name") or item.get("description"))
        ]

    if isinstance(content_pack.get("system_features"), list) and content_pack["system_features"]:
        system_features = []
        for feature_index, item in enumerate(content_pack["system_features"]):
            if not isinstance(item, dict):
                continue
            requirement_items = []
            for req_index, requirement in enumerate(item.get("functional_requirements") or []):
                if not isinstance(requirement, dict):
                    continue
                requirement_items.append(
                    {
                        "requirement_id": f"REQ-{feature_index + 1:02d}{req_index + 1}",
                        "title": str(requirement.get("title") or f"Requirement {req_index + 1}").strip(),
                        "description": str(requirement.get("description") or "").strip(),
                        "actor": str(requirement.get("actor") or "Primary User").strip(),
                        "trigger": "User initiates the workflow",
                        "inputs": [{"name": "payload", "type": "json", "required": True, "validation_rules": ["Validate required fields"]}],
                        "processing_logic": ["Validate input", "Persist state", "Return clear status"],
                        "outputs": [{"name": "result", "type": "json", "description": "Structured action result"}],
                        "business_rules_applied": ["BR-001"],
                        "error_conditions": [{"condition": "Invalid input", "system_behavior": "Show a validation message"}],
                        "acceptance_criteria": [str(criteria).strip() for criteria in (requirement.get("acceptance_criteria") or []) if str(criteria).strip()] or ["The workflow completes successfully."],
                        "priority": normalize_priority(requirement.get("priority")),
                        "status": srs.get("metadata", {}).get("status", "draft"),
                        "traceability": {
                            "linked_user_class_ids": ["UC-001"],
                            "linked_interface_ids": ["UI-001"],
                            "linked_test_case_ids": [f"TC-{feature_index + 1:03d}-{req_index + 1:02d}"],
                        },
                    }
                )
            system_features.append(
                {
                    "feature_id": f"FEAT-{feature_index + 1:03d}",
                    "feature_name": str(item.get("name") or f"Feature {feature_index + 1}").strip(),
                    "description_and_priority": {
                        "description": str(item.get("description") or "").strip(),
                        "priority": normalize_priority(item.get("priority")),
                        "benefit_score": max(6, 10 - feature_index),
                        "penalty_score": 7 if feature_index < 3 else 5,
                        "cost_score": 5,
                        "risk_score": 4,
                    },
                    "stimulus_response_sequences": [
                        {
                            "sequence_id": f"SRSQ-{feature_index + 1:03d}",
                            "stimulus": f"User starts {str(item.get('name') or f'feature {feature_index + 1}').strip().lower()}",
                            "preconditions": ["An active session exists."],
                            "system_response": "The system processes the request and shows a clear status update.",
                            "postconditions": ["The updated result is available for review."],
                        }
                    ],
                    "functional_requirements": requirement_items,
                }
            )
        if system_features:
            sections["system_features"] = system_features

    if isinstance(content_pack.get("performance_requirements"), list) and content_pack["performance_requirements"]:
        nfr["performance_requirements"] = [
            {
                "requirement_id": f"NFR-PERF-{index + 1:03d}",
                "description": str(item).strip(),
                "rationale": "Supports a responsive product experience.",
                "measurement_method": "Monitoring and tracing",
                "target_metric": "Service performance",
                "target_value": "Defined during implementation",
                "conditions": "Normal operating conditions",
            }
            for index, item in enumerate(content_pack["performance_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("security_requirements"), list) and content_pack["security_requirements"]:
        nfr["security_requirements"] = [
            {
                "requirement_id": f"NFR-SEC-{index + 1:03d}",
                "description": str(item).strip(),
                "authentication_requirements": ["Role-based authentication"],
                "authorization_requirements": ["Role-based access"],
                "data_protection_requirements": ["TLS in transit", "Encrypted storage"],
                "privacy_requirements": ["Business and user data protection"],
                "compliance_reference": "Project-dependent",
                "verification_method": "Security review and tests",
            }
            for index, item in enumerate(content_pack["security_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("business_rules"), list) and content_pack["business_rules"]:
        nfr["business_rules"] = [
            {
                "rule_id": f"BR-{index + 1:03d}",
                "description": str(item).strip(),
                "applicable_roles": ["Administrator", "Primary User"],
                "conditions": ["Project workflow is active"],
                "enforcement_requirements": ["REQ-011"],
            }
            for index, item in enumerate(content_pack["business_rules"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("database_requirements"), list) and content_pack["database_requirements"]:
        other["database_requirements"] = [
            {
                "requirement_id": f"DB-{index + 1:03d}",
                "description": str(item).strip(),
                "entities": ["Session", "AnswerSet", "SRSArtifact"],
                "retention_policy": "Policy-based retention",
                "backup_policy": "Scheduled backups",
            }
            for index, item in enumerate(content_pack["database_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("legal_requirements"), list) and content_pack["legal_requirements"]:
        other["legal_requirements"] = [
            {
                "requirement_id": f"LEGAL-{index + 1:03d}",
                "description": str(item).strip(),
                "jurisdiction": "Project-dependent",
                "reference": "Business and regulatory policy",
            }
            for index, item in enumerate(content_pack["legal_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("additional_requirements"), list) and content_pack["additional_requirements"]:
        other["additional_requirements"] = [
            {
                "requirement_id": f"OTH-{index + 1:03d}",
                "description": str(item).strip(),
            }
            for index, item in enumerate(content_pack["additional_requirements"])
            if str(item).strip()
        ]

    if isinstance(content_pack.get("services"), list) and content_pack["services"]:
        existing_service_map = {service.get("service_name"): service for service in srs.get("services", [])}
        merged_services = []
        for item in content_pack["services"]:
            if not isinstance(item, dict):
                continue
            service_name = str(item.get("service_name") or "").strip()
            if not service_name:
                continue
            existing = existing_service_map.get(service_name, {})
            merged_services.append(
                {
                    "service_name": service_name,
                    "port": existing.get("port", 8200 + len(merged_services)),
                    "summary": str(item.get("summary") or existing.get("summary") or "").strip(),
                    "endpoints": existing.get("endpoints", []),
                }
            )
        if merged_services:
            srs["services"] = merged_services

    if content_pack.get("analyst_summary"):
        interview_workspace["analysis_summary"] = str(content_pack["analyst_summary"]).strip()
    return srs
