#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

required=(
  AGENTS.md CLAUDE.md
  .harness/references/project-map.md
  .harness/references/quality-gates.md
  .harness/references/business-workflow.md
  .harness/references/data-contracts.md
  .harness/skills/minwon-orchestrator/SKILL.md
  .claude/skills/minwon-orchestrator/SKILL.md
  .agents/skills/minwon-orchestrator/SKILL.md
)

for file in "${required[@]}"; do
  test -s "$file" || { echo "missing: $file" >&2; exit 1; }
done

for role in system-architect agent-pipeline-engineer streamlit-pixel-engineer civic-safety-reviewer integration-qa; do
  test -s ".harness/agents/$role.md" || { echo "missing core role: $role" >&2; exit 1; }
  test -s ".claude/agents/$role.md" || { echo "missing Claude adapter: $role" >&2; exit 1; }
done

business_roles=(intake-agent classifier-agent evidence-search-agent response-writer-agent response-validator-agent output-publisher-agent)
for role in "${business_roles[@]}"; do
  test -s ".harness/agents/$role.md" || { echo "missing business role: $role" >&2; exit 1; }
  test -s ".claude/agents/$role.md" || { echo "missing Claude business adapter: $role" >&2; exit 1; }
done

grep -q '^name: minwon-orchestrator$' .harness/skills/minwon-orchestrator/SKILL.md
grep -q '공용 원본' .claude/skills/minwon-orchestrator/SKILL.md
grep -q '공용 원본' .agents/skills/minwon-orchestrator/SKILL.md

orchestrator=.harness/skills/minwon-orchestrator/SKILL.md
for phase in 'Phase 1 — 입력' 'Phase 2 — 처리' 'Phase 3 — 검증' 'Phase 4 — 출력'; do
  grep -q "$phase" "$orchestrator" || { echo "missing workflow phase: $phase" >&2; exit 1; }
done

for decision in PASS REVISE ESCALATE REJECT; do
  grep -q "$decision" "$orchestrator" || { echo "missing validation decision: $decision" >&2; exit 1; }
done

grep -q '최대 2회' "$orchestrator" || { echo "missing bounded revision loop" >&2; exit 1; }
grep -q 'DRAFT_APPROVED' .harness/references/data-contracts.md || { echo "missing final output contract" >&2; exit 1; }
grep -q '입력.*처리.*검증.*출력' README.md || { echo "README does not expose end-to-end flow" >&2; exit 1; }
echo "harness validation: PASS"
