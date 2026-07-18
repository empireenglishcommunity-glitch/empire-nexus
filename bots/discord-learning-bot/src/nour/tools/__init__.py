"""Aql (العقل) — Tool Layer (Phase A3).

design.md Section 5. Two tool modules, one per role tier:
  - student_tools.py — implicitly "about me" reads, discord_id bound
    server-side, never a model-supplied parameter (Section 5.2).
  - owner_tools.py — thin wrappers over EXISTING ops_commands.py /
    nour_ops_commands.py functions, zero reimplementation (Section 5.3).

dispatcher.py is the single entry point (`execute_tool()`) that both
the future orchestrator (Phase A5) and every test in this phase call
through — it validates the requested tool name against the caller's
role BEFORE executing, and logs every call to `nour_tool_calls`.
"""
