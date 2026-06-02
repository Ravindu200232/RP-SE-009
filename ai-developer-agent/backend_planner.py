"""
Backend planner (parent + per-service child).

Loops one service at a time (small calls = no truncation) and forces a COMPLETE,
runnable file set: db connection, models, controllers, routes, optional auth
middleware, server entry point, and package.json. The data_structure_or_endpoint_spec
shape is now LOCKED per file type so the downstream code-generator can parse it
consistently (your old runs mixed schema_fields / endpoint_methods / routes / route_definitions).
"""

import json
import os

from langchain_core.prompts import ChatPromptTemplate

from llm_config import get_llm, extract_json, stream_to_string
from state import GraphState


_CHILD_SYSTEM_PROMPT = """You are an Enterprise Backend Service Planner.
You receive ONE microservice's architecture. Output a COMPLETE, runnable file blueprint for that single service as raw JSON. Specifications only, never write JavaScript. No prose, no markdown, no code fences.

ALWAYS PLAN A RUNNABLE SERVICE. Include these files, in this order:
1. src/config/db.js (Config): Mongoose connection using MONGO_URI.
2. One Model file per model in src/models/.
3. One Controller file per model in src/controllers/.
4. One Route file per model in src/routes/.
5. src/middleware/authMiddleware.js (Middleware): ONLY if any route has requires_auth true; verifies the Bearer JWT.
6. src/index.js (Server): load dotenv, connect db, app.use(cors(), express.json()), mount every route, listen on PORT.
7. package.json (Config): name, scripts.start = "node src/index.js", dependencies from required_npm_packages.

EXACT data_structure_or_endpoint_spec PER file_type (use ONLY these keys):
- "Model": {{ "schema_fields": {{ field_name: {{ type, required, unique, enum, min, max, ref, default }} }} }}  (copy every field and constraint verbatim).
- "Controller": {{ "methods": [ {{ "name", "http_method", "description" }} ] }}.
- "Route": {{ "endpoints": [ {{ "method", "path", "handler", "requires_auth" }} ] }}.
- "Server" / "Config" / "Middleware": {{}}.

RULES:
- Route handler names MUST match controller method names exactly.
- Copy all field names, enums, refs and constraints verbatim. Do not drop or invent any.
- logic_steps_for_coder: 2 to 5 short imperative steps, concrete where it matters (bcrypt hash, jwt sign, .save(), findByIdAndUpdate, send status codes). Each step under 12 words.

Respond ONLY with raw JSON in EXACTLY this structure:
{{
  "service_name": "Name-Service",
  "port": 5001,
  "database_name": "db_name",
  "files_to_create": [
    {{
      "file_path": "src/models/Example.js",
      "file_type": "Model",
      "purpose": "Define the Example schema.",
      "imports_needed": ["mongoose"],
      "data_structure_or_endpoint_spec": {{
        "schema_fields": {{
          "example_id": {{ "type": "String", "required": true, "unique": true }}
        }}
      }},
      "logic_steps_for_coder": ["Import mongoose", "Define schema with fields", "Export the model"],
      "exports": "Example"
    }}
  ]
}}
Output compact JSON. No comments, no trailing text. Close every bracket."""


def backend_planner_agent(state: GraphState):
    microservices = state["microservices"]
    print(f"\n=== [PARENT BACKEND PLANNER: PROCESSING {len(microservices)} SERVICES INTO BLUEPRINTS] ===")

    chain = ChatPromptTemplate.from_messages([
        ("system", _CHILD_SYSTEM_PROMPT),
        ("user", "Here is the microservice architecture for your assigned service:\n\n{service_json}")
    ]) | get_llm()

    all_service_plans = []
    os.makedirs("plans/backend", exist_ok=True)

    for index, service in enumerate(microservices):
        service_name = service.get("service_name", f"Service-{index + 1}")
        print(f"\n--- [CHILD PLANNER: {service_name} ({index + 1}/{len(microservices)})] ---")

        response_str = stream_to_string(chain, {"service_json": json.dumps(service, indent=2)})
        try:
            plan = extract_json(response_str)
            all_service_plans.append(plan)
            path = f"plans/backend/{service_name}.json"
            with open(path, "w") as f:
                json.dump(plan, f, indent=2)
            print(f"\n[SAVED Blueprint] -> {path}")
        except Exception as e:
            print(f"\nError parsing plan for {service_name}: {e}")

    return {"backend_plan": json.dumps({"complete_backend_roadmap": all_service_plans}, indent=2)}
