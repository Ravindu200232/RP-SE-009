"""Prompt registry for ArchitectAgent."""
from agents.planning.architect_stack_rules import WRITE_FILE_TOOL, VITE_STACK_RULES, NEXT_STACK_RULES
from agents.planning.architect_vite_prompts import VITE_PLANNER_SYSTEM, VITE_BUILDER_SYSTEM
from agents.planning.architect_next_planner_prompt_a import PROMPT_PART_A as NEXT_PLANNER_A
from agents.planning.architect_next_planner_prompt_b import PROMPT_PART_B as NEXT_PLANNER_B
from agents.planning.architect_next_builder_prompt_a import PROMPT_PART_A as NEXT_BUILDER_A
from agents.planning.architect_next_builder_prompt_b import PROMPT_PART_B as NEXT_BUILDER_B

NEXT_PLANNER_SYSTEM = NEXT_PLANNER_A + NEXT_PLANNER_B
NEXT_BUILDER_SYSTEM = NEXT_BUILDER_A + NEXT_BUILDER_B

PROMPTS = {
    "vite": {
        "rules":   VITE_STACK_RULES,
        "planner": VITE_PLANNER_SYSTEM,
        "builder": VITE_BUILDER_SYSTEM,
        "roots":   ("src/",),
        "entry":   ("src/App.jsx", "src/App.js"),
    },
    "next": {
        "rules":   NEXT_STACK_RULES,
        "planner": NEXT_PLANNER_SYSTEM,
        "builder": NEXT_BUILDER_SYSTEM,
        "roots":   ("app/", "components/", "lib/"),
        "entry":   ("app/page.js", "app/page.jsx"),
    },
}
