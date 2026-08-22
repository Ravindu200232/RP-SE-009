"""
DeployForge, as AgentForge runs it.

`deployment_agent/`, `dfagents/` and `dfserver.py` are a copy of the standalone
agent at C:\\deployment-agent. Keep it that way: everything AgentForge-specific
belongs in `bridge.py`, and the copy imports it from exactly three places
(config.py, tools.py, orchestrator.py), each with a comment saying why.

Deliberately no imports here. `deployment_agent.config` imports
`deploy_agent.bridge` at call time, so anything imported at this level would
make that a cycle.
"""
