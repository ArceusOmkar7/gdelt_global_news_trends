# GNIEM — Project Memory & Mandates

This is the Global News Intelligence & Event Monitoring (GNIEM) system. The rules and context defined in this memory bank are mandatory for all agent sessions.

@./memory-bank/architecture.md
@./memory-bank/active-context.md
@./memory-bank/progress.md
@./memory-bank/failures.md

## MANDATORY SESSION END BEHAVIOR

After EVERY task or at the end of every session, the agent MUST:
1. Update `active-context.md` with a summary of what was completed and the next immediate steps.
2. Append completed items to `progress.md`.
3. Append any new failures, bugs, or technical debt discovered (and their resolutions) to `failures.md`.
4. Git commit the `memory-bank/` directory with a descriptive message.
