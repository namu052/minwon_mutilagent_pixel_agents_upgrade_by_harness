# 민원 업무 데이터 계약

모든 payload는 JSON 직렬화 가능한 객체로 취급한다. 필수 필드가 없으면 다음 단계로 넘기지 않는다.

## 1. ComplaintInput

```json
{"complaint_id":"string","title":"string","body":"string","submitted_at":"string|null"}
```

`title` 또는 `body`가 비어 있으면 입력 보완이 필요하다. 원문은 임의로 의미 변경하지 않는다.

## 2. IntakeResult

```json
{
  "complaint":{"complaint_id":"string","title":"string","body":"string"},
  "quality_flags":[],
  "privacy_flags":[],
  "safe_summary":"string",
  "decision":"CONTINUE|REJECT|ESCALATE"
}
```

## 3. ClassificationResult

```json
{
  "department":"string",
  "complaint_type":"string",
  "confidence":0.0,
  "rationale":"string",
  "issues":["string"],
  "search_terms":["string"],
  "decision":"CONTINUE|ESCALATE"
}
```

## 4. EvidencePackage

```json
{
  "legal_bases":[{"title":"string","article":"string|null","claim":"string","url":"string","source_type":"OFFICIAL|SECONDARY","verified":true}],
  "similar_cases":[{"summary":"string","url":"string","source_type":"OFFICIAL|SECONDARY"}],
  "conflicts":[],
  "coverage_gaps":[],
  "decision":"CONTINUE|ESCALATE"
}
```

URL이 없거나 확인하지 못한 근거는 `verified: false`이며 핵심 단정의 근거로 사용할 수 없다.

## 5. DraftPackage

```json
{
  "draft":"string",
  "claim_evidence_map":[{"claim":"string","evidence_urls":["string"]}],
  "uncertainties":[],
  "revision_count":0
}
```

## 6. ValidationReport

```json
{
  "decision":"PASS|REVISE|ESCALATE|REJECT",
  "checks":{"input_fidelity":"PASS|FAIL","jurisdiction":"PASS|FAIL","evidence":"PASS|FAIL","citation":"PASS|FAIL","tone":"PASS|FAIL","privacy":"PASS|FAIL"},
  "findings":[{"severity":"BLOCKER|HIGH|MEDIUM|LOW","message":"string","fix":"string"}],
  "revision_instructions":[],
  "validated_at":"string"
}
```

하나라도 BLOCKER면 `PASS`할 수 없다. 근거·관할·개인정보 항목의 HIGH도 `PASS`할 수 없다.

## 7. FinalOutput

```json
{
  "status":"DRAFT_APPROVED|HUMAN_REVIEW_REQUIRED|REJECTED|INPUT_REJECTED",
  "answer":"string|null",
  "citations":[],
  "validation_report":{},
  "disclaimer":"담당자 검토 전 초안입니다.",
  "trace_id":"string"
}
```

