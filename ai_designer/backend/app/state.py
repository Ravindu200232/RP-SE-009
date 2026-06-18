from typing import TypedDict, List, Dict, Any

class GraphState(TypedDict):
    project_id: str           # Unique identifier for the project directory
    prompt: str               # The current user request (initial or edit instruction)
    history: List[Dict[str, str]] # History of prompts and milestones
    roles: List[str]          # Roles identified for the prototype
    pages: List[Dict[str, Any]] # Pages identified (path, title, template keys)
    entities: List[Dict[str, Any]] # Data entities (name, fields) extracted from the prompt/SRS
    app_name: str             # Human app name (used e.g. for the navbar brand)
    files: Dict[str, str]     # Dict mapping file paths relative to project root -> content
    status: str               # Status description
    logs: List[str]           # Execution progress logs to be streamed to UI
    theme: Dict[str, Any]     # The design-token theme chosen for this project
    # PHASE 1-3 (Pro upgrade) - MUST be declared here or LangGraph drops them
    # between the planning and code_generation nodes.
    blueprint: Dict[str, Any]      # Deep Research domain blueprint
    marketing_pages: List[Dict[str, Any]]  # domain-specific public pages
    theme_style: str               # visual paradigm (minimal/neo-brutalism/glassmorphism/cyberpunk)
    is_utility_tool: bool          # single-screen tool -> skip the marketing tier
    srs: Dict[str, Any]            # parsed SRS when the input was an SRS JSON
    intake: Dict[str, Any]         # answers from the requirements interview (pages, components, auth, roles, theme)
    ai_sections: bool              # opt-in: let Gemma write each marketing section's JSX (validate + fallback)
    genome: Dict[str, Any]         # Design Genome that DRIVES structure (styles, crud layouts, section order)
