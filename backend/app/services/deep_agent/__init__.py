"""Deep Agent mode (mode="deep").

A LangChain `deepagents` orchestrator that delegates to specialist sub-agents, each
proficient in a SINGLE attack type. Every command is bound to a developer-authored
template, validated params only, run through the existing scope/safety gate
(`agent_orchestrator._is_command_safe`), and only against a target covered by an
ACTIVE `Engagement` (see authorization.py). Detection/assessment-oriented:
no DoS flooding, no malware, no social engineering, no supply-chain compromise.
"""
