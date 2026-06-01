from ast import parse
import json
# pyrefly: ignore [missing-import]
from langchain_ollama import ChatOllama
# pyrefly: ignore [missing-import]
from langchain_core.prompts import ChatPromptTemplate
from state import GraphState

def architect_agent(state: GraphState):
    print("\n--- [ARCHITECT AGENT WORK]")

    # get srs memory 
    srs_data = state["srs_input"]

    llm = ChatOllama(model="qwen2.5-coder:7b", format="json", temperature=0)

    # system prompt
    system_prompt = """You are an expert Software Architect specializing in Full-Stack MERN applications using Microservices. 
    Your job is to completely analyze the user's SRS and output a 100% production-ready architecture JSON.

    "Never drop essential fields like passwordHash for Auth, or owner/user IDs for data ownership"
    
    For each backend microservice, you MUST strictly identify:
    1. service_name: Name of the backend service (e.g., Auth-Service).
    2. database_config: Specific MongoDB configuration for this service containing 'database_name'.
    3. port_assignment: A unique port number for this service (Start from 5001, then 5002, 5003, etc.) to avoid port collisions.
    4. dependencies: List of other services it interacts with, communication type, and reason.
    5. env_variables: Essential environment variables needed (e.g., MONGO_URI, JWT_SECRET, PORT).
    6. required_npm_packages: Node.js libraries. Every service MUST include at least ["express", "cors", "dotenv", "mongoose"] plus service-specific packages (like bcryptjs, jsonwebtoken).
    7. models: MongoDB schemas with fields, data types, and strict rules like required (true/false), unique (true/false).
    8. controllers: Function names with step-by-step pseudo-logic.
    9. routes: Backend endpoint details. For EVERY route, you MUST include a boolean property "requires_auth" (true if it needs JWT protection, false if public).
    
    CRITICAL - Frontend Planning:
    Include a separate section in the JSON called "frontend_spec" defining required_npm_packages (e.g., axios, react-router-dom, tailwindcss, lucide-react), structural_components, and pages.

    You MUST respond ONLY with a raw JSON object matching this exact structure:
    {{
      "microservices": [
        {{
          "service_name": "Auth-Service",
          "database_config": {{ "database_name": "neighborly_auth_db" }},
          "port_assignment": 5001,
          "dependencies": [],
          "env_variables": ["MONGO_URI", "JWT_SECRET", "PORT"],
          "required_npm_packages": ["express", "cors", "dotenv", "mongoose", "jsonwebtoken", "bcryptjs"],
          "models": [{{ "model_name": "User", "fields": {{ "email": {{ "type": "String", "required": true, "unique": true }} }} }}],
          "controllers": [{{ "name": "login", "logic": "1. Check email. 2. Verify password." }}],
          "routes": [{{ "method": "POST", "endpoint": "/api/auth/login", "handler": "login", "requires_auth": false }}]
        }}
      ],
      "frontend_spec": {{
        "required_npm_packages": ["axios", "react-router-dom", "tailwindcss"],
        "structural_components": ["Glassmorphic Sidebar"],
        "pages": [{{ "page_name": "Login", "description": "Allows login" }}]
      }}
    }}
    Do not include any conversational text or explanation outside the JSON object."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Here is the SRS input data:\n\n{srs}")
    ])

    # combine ai using langchain
    chain = prompt | llm

    #live response
    full_response = ""

    #invoke the chain stream
    for chunk in chain.stream({"srs": srs_data}):
        token = chunk.content
        print(token,end="", flush=True)
        full_response += token

    print("\n--- [LIVE STRMEAMING COMPLETED] ---\n")

    try:
        parse_output = json.loads(full_response)
        print("Successfully structured SRS into Microservices with Relationships!")
        return {
            "microservices": parse_output.get("microservices", []),
            "frontend_spec": parse_output.get("frontend_spec", {})
        }
    except Exception as e:
        print(f"Error parsing architect response: {e}")
        return {"microservices": [], "frontend_spec": {}}
