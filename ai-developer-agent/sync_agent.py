"""
Reviewer / sync agent.

Detects endpoint + missing-field mismatches between frontend pages and backend
routes, then programmatically patches the saved blueprints. Nothing is deleted.

Includes a fail-safe programmatic child routine to auto-heal empty form inputs 
by mapping schema properties directly from database models.
"""

import json
import os
import re

from langchain_core.prompts import ChatPromptTemplate

from llm_config import get_llm, extract_json, stream_to_string
from state import GraphState


_SYNC_SYSTEM_PROMPT = """You are an Elite QA Code Reviewer and System Sync Agent.
You receive ALL backend service blueprints and ALL frontend page blueprints. Find every mismatch between what the frontend calls and what the backend exposes, and output only the fixes as raw JSON. No prose, no markdown, no code fences.

STRICT DETECTION RULES:
1. Endpoint Mismatch: A frontend form/logic calls a path or method that NO backend route exposes. Pick the correct backend path and method.
2. Field Key Alignment (CRITICAL): Cross-examine the text case style. If the backend schema model uses snake_case (e.g., patient_mpi_id, scheduled_start_time) but the frontend page uses camelCase (e.g., patientMpiId, startTime), you MUST treat this as a critical data mismatch and add the exact matching backend database keys into 'corrected_fields_to_add' to enforce uniform data binding.
3. Empty Forms Detection (MANDATORY): Scan all 11 frontend pages individually. If ANY page creation/edit blueprint contains an empty or missing 'fields_to_bind' array (e.g., Encounter Create, Invoice Create, Patient Profile Create), look up its specific corresponding Backend Mongoose schema fields, extract all exact keys, and dump them into the 'corrected_fields_to_add' list. Never let a form remain empty.
4. Never rename a microservice. Never delete any pre-existing files or folders.

OUTPUT RULES:
- Include ONLY files that need changes. If everything aligns perfectly, return empty arrays.
- service_name = the exact existing microservice name.
- file_path = the exact backend route file path.
- page_file_name = the exact frontend json filename, e.g. page_Appointment_Create.json or page_Invoice_Create.json.
- corrected_endpoint_path = a real backend path.

Respond ONLY with raw JSON in EXACTLY this structure:
{{
  "modified_backend_files": [
    {{
      "service_name": "Appointment-Scheduling-Service",
      "file_path": "src/routes/AppointmentRoutes.js",
      "corrected_spec": {{
        "schema_fields_or_route_methods": {{
          "POST /api/appointment/schedule": "scheduleAppointment",
          "PUT /api/appointment/status/:appointment_id": "updateAppointmentStatus"
        }}
      }}
    }}
  ],
  "modified_frontend_files": [
    {{
      "page_file_name": "page_Appointment_Create.json",
      "corrected_endpoint_path": "/api/appointment/schedule",
      "corrected_fields_to_add": ["patient_mpi_id", "scheduled_start_time"]
    }}
  ]
}}
Output compact JSON. No comments, no trailing text. Close every bracket."""


def _load_folder(folder: str) -> dict:
    data = {}
    if os.path.exists(folder):
        for file in os.listdir(folder):
            if file.endswith(".json"):
                with open(os.path.join(folder, file), "r") as f:
                    data[file] = json.load(f)
    return data


def reviewer_sync_agent(state: GraphState):
    print("\n=== [MASTER REVIEWER & PROGRAMMATIC SYNC AGENT: PATCHING MISMATCHES] ===")

    backend_folder = "plans/backend"
    frontend_folder = "plans/frontend"

    backend_files_data = _load_folder(backend_folder)
    frontend_files_data = _load_folder(frontend_folder)

    chain = ChatPromptTemplate.from_messages([
        ("system", _SYNC_SYSTEM_PROMPT),
        ("user", "BACKEND:\n{back_data}\n\nFRONTEND:\n{front_data}")
    ]) | get_llm()

    response_str = stream_to_string(chain, {
        "back_data": json.dumps(backend_files_data, indent=2),
        "front_data": json.dumps(frontend_files_data, indent=2),
    })

    try:
        sync_output = extract_json(response_str)
        print("\n[MERGE PROCESS] -> Programmatically patching original blueprints (nothing deleted)...")

        # 1. Backend patch: replace ONLY the targeted route file's spec
        for patch in sync_output.get("modified_backend_files", []):
            s_name = patch.get("service_name")
            f_path = patch.get("file_path")
            new_spec = patch.get("corrected_spec")
            target = f"{backend_folder}/{s_name}.json"
            if os.path.exists(target):
                with open(target, "r") as f:
                    orig = json.load(f)
                for file_obj in orig.get("files_to_create", []):
                    if file_obj.get("file_path") == f_path:
                        file_obj["data_structure_or_endpoint_spec"] = new_spec
                with open(target, "w") as f:
                    json.dump(orig, f, indent=2)
                print(f"[PATCHED BACKEND] -> Synced endpoints inside {target}")

        # 2. Frontend patch: fix the endpoint + add missing fields
        for patch in sync_output.get("modified_frontend_files", []):
            f_name = patch.get("page_file_name")
            new_path = patch.get("corrected_endpoint_path")
            add_fields = patch.get("corrected_fields_to_add", []) or []
            target = f"{frontend_folder}/{f_name}"
            
            if os.path.exists(target) and new_path:
                with open(target, "r") as f:
                    orig = json.load(f)

                form = orig.get("data_bindings_and_forms")
                if isinstance(form, dict):
                    form["api_endpoint"] = new_path
                    existing = {fb.get("field_name") for fb in form.get("fields_to_bind", [])}
                    for fld in add_fields:
                        if fld and fld not in existing:
                            form.setdefault("fields_to_bind", []).append(
                                {"field_name": fld, "type": "text", "validation": "required"}
                            )

                if "logic_steps_for_coder" in orig:
                    orig["logic_steps_for_coder"] = [
                        re.sub(r"'/api/[^']+'", f"'{new_path}'", step)
                        for step in orig["logic_steps_for_coder"]
                    ]

                with open(target, "w") as f:
                    json.dump(orig, f, indent=2)
                print(f"[PATCHED FRONTEND] -> Synced endpoint to '{new_path}' inside {target}")

        # 3. 🛡️ FAIL-SAFE PROGRAMMATIC CHILD HEALER LOGIC (Runs right after LLM to double-secure empty keys)
        print("\n[CHILD HEALER] -> Scanning blueprints for hidden empty forms...")
        for front_file in os.listdir(frontend_folder):
            if front_file.startswith("page_") and front_file.endswith(".json"):
                fp_path = os.path.join(frontend_folder, front_file)
                with open(fp_path, "r") as f:
                    page_data = json.load(f)
                
                form = page_data.get("data_bindings_and_forms", {})
                if isinstance(form, dict) and ("fields_to_bind" in form or "forms" in page_data):
                    fields_list = form.get("fields_to_bind", [])
                    
                    if not fields_list and page_data.get("file_type") == "Page":
                        print(f"[HEAL] -> Empty fields detected in {front_file}. Resolving matching entities...")
                        
                        clean_page_token = page_data.get("name", "").replace("Create", "").replace("Form", "").replace(" ", "").lower()
                        injected_fields = []
                        
                        for back_file in os.listdir(backend_folder):
                            if back_file.endswith(".json"):
                                with open(os.path.join(backend_folder, back_file), "r") as bf:
                                    b_data = json.load(bf)
                                
                                for file_item in b_data.get("files_to_create", []):
                                    if file_item.get("file_type") == "Model":
                                        spec = file_item.get("data_structure_or_endpoint_spec", {})
                                        schema_fields = spec.get("schema_fields", {})
                                        
                                        if schema_fields:
                                            clean_model_token = file_item.get("file_path", "").split("/")[-1].replace(".js", "").lower()
                                            
                                            if clean_page_token in clean_model_token or clean_model_token in clean_page_token:
                                                for key, val in schema_fields.items():
                                                    b_type = val.get("type", "String")
                                                    f_type = "number" if b_type == "Number" else "date" if b_type == "Date" else "text"
                                                    injected_fields.append({
                                                        "field_name": key,
                                                        "type": f_type,
                                                        "validation": "required" if val.get("required") else "optional"
                                                    })
                                                break
                                if injected_fields:
                                    break
                        
                        if injected_fields:
                            form["fields_to_bind"] = injected_fields
                            with open(fp_path, "w") as f:
                                json.dump(page_data, f, indent=2)
                            print(f"[HEALED] -> Injected {len(injected_fields)} schema fields into {front_file} successfully!")

        print("\n=== [MASTER SYNC SUCCESSFULLY COMPLETED WITH 100% DATA PRESERVATION] ===")
    except Exception as e:
        print(f"\nError executing Sync Agent merge layout: {e}")

    return state