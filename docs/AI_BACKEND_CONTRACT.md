# AI backend API contract and sequences

Contract revision 1, 21 November 2026. Local candidate based on `f015e190b9daf92661ffb362408d639da5b9db54` (PR250–255 and main `f762701`). This guide describes implemented behavior; the early-stop/turn-limit reporting proposal is **not implemented or approved for adoption** in this revision. Paths below have the `/api/v1` prefix. Generate OpenAPI from the same checkout when integrating.

## Authentication and error responses

Use the application's existing authentication/CSRF flow. These endpoints require an active authenticated account; 401 means authentication is required, and 403 can mean the password-change gate. Teacher-only routes additionally enforce their role/course checks. UUID/body validation returns 422 with a list under `detail`; application rejections commonly use a string under `detail`. Stage1 semantic rejection also uses 422 with a string. Do not assume every 422 has the same detail type.

Student history, reply, end and personal-report operations return **404**, not 403, for a missing or other-owner session. Session entry checks course membership separately and returns 403 for a nonmember. Setup read/save/generate/refine/opening allow the course teacher or a course TA with `edit_topics`. Publish remains restricted to the course teacher. Teaching report routes also still require the global teacher role.

## Teacher setup

| Operation | Input | Persistence and response |
| --- | --- | --- |
| POST `/courses/{courseId}/topics` | `age_band`, `max_turns`, `course_description`; optional `model_id`, `content_language` | Creates a setup topic after successful generation. Returns identifiers, setup and teacher feedback. |
| GET `/topics/{topicId}/setup` | None | Saved setup. Null-valued keys are omitted, including nested setup keys; tolerate missing optional fields. |
| POST `/topics/{topicId}/setup/generate` | `age_band`, `max_turns`, `content_language`, `course_description`, `model_id` | Returns a suggestion plus feedback. Does not save fields, language or model. The model must be in the catalog. |
| POST `/topics/{topicId}/setup/refine` | `setup`, `feedback` | Returns a suggestion plus feedback, without saving it. Uses the topic's effective model/language. |
| PUT `/topics/{topicId}/setup` | `setup`; optional `model_id`, `content_language` | Saves displayed fields and explicit selections. Omitted selections preserve stored values; null/blank selections are rejected. |
| POST `/topics/{topicId}/setup/opening-message` | `setup` | Returns **and saves** the new opening and records a revision. It does not save unrelated displayed fields. A concurrent write causes 409. |
| POST `/topics/{topicId}/publish` | `setup`; optional `model_id`, `content_language` | Saves fields/selections and publishes atomically. Invalid publication rolls back. Only age, cap, topic and core question are currently required by the publication gate; blank opening is permitted. |

Generation/refinement feedback: `assessments`, `clarification_questions`, `suggestions`, `warnings`. These are returned guidance, not separately persisted feedback. Treat missing optional response fields as unavailable. Preserve the teacher's draft on failure; the server does not durably save a rejected generation request.

Generation errors include 400 outside setup, 422 for request/semantic rejection, 502 for invalid provider output, 503 for unavailable service/incomplete substantive output, and 504 for the task timeout. See per-route OpenAPI for examples. Opening generation sends the effective content language and requests only `opening_message` using a dedicated schema (45-second timeout, at most500 output tokens). Missing/blank/malformed opening output returns502 without replacing the saved opening.

Stage1 uses the requesting user's stored OpenRouter key when available, otherwise the server key. Dialogue/report calls use server credentials. Configuring only a teacher key does not establish access for all stages. For teacher- and TA-created activities, model selection is explicit creation override → course owner (`Course.created_by`) saved default → server default. Explicit and saved selections must exist in the catalog; stale saved defaults return422. Language defaults to server configuration. These defaults affect only new topics. Generate/refine return the effective language/model; to adopt a generated selection, send it explicitly on Save/Publish. Model/language changes are recorded in inquiry revisions. No key belongs in a frontend payload, trace or example beyond the dedicated existing key-settings flow.

```mermaid
sequenceDiagram
    actor Teacher
    participant API as FastAPI
    participant Model as OpenRouter
    participant DB as Postgres
    Teacher->>API: POST /courses/{courseId}/topics
    API->>Model: Native Stage1 design request
    alt usable valid design
        API->>DB: Save setup topic and revision
        API-->>Teacher: setup and feedback
    else rejected or failed
        API-->>Teacher: 422 / 502 / 503 / 504, no new topic
    end
    Teacher->>API: POST /topics/{topicId}/setup/generate or refine
    API->>Model: Generate suggestion
    API-->>Teacher: setup and feedback, not saved
    opt opening regeneration
        Teacher->>API: POST /topics/{topicId}/setup/opening-message
        API->>Model: Generate opening
        API->>DB: Save opening and revision if not stale
        API-->>Teacher: opening_message
    end
    Teacher->>API: PUT setup or POST publish with setup and optional model/language
    API->>DB: Save; publish also enters conversation
    API-->>Teacher: Stored setup and status
```

## Session state and dialogue transport

POST `/topics/{topicId}/sessions` creates or returns the same session. Setup topics return 404; summary topics return an existing session but reject creation of a missing one with 400. Existing ended sessions are returned as ended, not reopened. The endpoint currently checks course membership, not an exclusive student course role.

The name `session_status` has two endpoint-specific meanings:

| Endpoint family | Values |
| --- | --- |
| Session entry, history, end | `open`, `completed`, `abandoned`, `closed_by_summary` (dialogue outcome) |
| Student rows in course-topic list | `IN_PROGRESS`, `COMPLETED`, or null before entry (legacy status) |

Do not decide reply eligibility from the course-list enum. Use session history and topic stage. `open` alone does not guarantee another turn: the cap may already be spent. The opening shown in history is not a counted student turn.

POST `/sessions/{sessionId}/messages/stream` takes:

```json
{"content":"I think access matters because people need to get to work.","request_id":"11111111-1111-4111-8111-111111111111"}
```

Use authenticated POST streaming (for example, `fetch` with a stream reader); native `EventSource` does not send this POST body. Inference and persistence finish **before** the SSE response begins. Successful content type is `text/event-stream`; this is not progressive provider token streaming. Parse SSE event boundaries, not individual network chunks.

```text
data: What would change your view?
data: Consider who pays for the service.

event: done
data: {"message_id":"44444444-4444-4444-4444-444444444444","completed_turns":1,"is_completed":false,"awaiting_end_consent":true}

```

The first event is unnamed (standard event type `message`), containing the whole visible reply. Join its data lines with LF; CR/CRLF input normalizes to LF. The final named `done` event contains JSON with four required fields. OpenAPI documents the stream as a string and exposes each event schema in the `x-sse-events` response extension; it is not a JSON HTTP response. No SSE `id:` or Last-Event-ID resumption is provided.

`awaiting_end_consent=true` asks the client to offer an ending choice. It does not make the session completed or report-eligible. A new reply currently has `is_completed=false`; replay of an older committed reply can reflect a now-completed session. Replayed count/flags reflect current session state, while text/message ID identify the stored reply.

Errors before SSE starts are ordinary JSON responses: 400 closed/capped, 404 missing/other owner, 409 busy/stale/ended during generation, 413 context-budget rejection, 422 request validation, 502 model/output failure, or 503 availability/tokenizer configuration failure, plus authentication errors. Check HTTP status/content type before parsing events.

Retry the same logical submission with the same `request_id` **and content**. Once committed, its reply is replayed without another inference or stored turn. A new submission needs a new ID. A failed model turn has no durable pending student receipt; retain the draft until success and reload history after an ambiguous disconnect. The busy guard is process-local: neither cross-worker exactly-once inference nor exactly-once provider billing is guaranteed. Do not automatically retry model failures indefinitely.

## Ending and starting reports

| End action | Current result |
| --- | --- |
| `complete` | Requires stored goal achievement; otherwise 409. Sets outcome `completed`, clears consent. |
| `continue` | Keeps `open`, clears consent, preserves stored goal achievement. Does not reset or extend the cap. |
| `abandon` | Sets outcome `abandoned`, clears goal/consent. No personal report. |

End on an already-ended session returns 400; end while the process-local reply guard is held returns 409. Current readiness/goal flags can diverge after later progress changes (LC-03); this remains a code fix in the dialogue chunk, not solved by this guide.

Reaching the cap without the goal currently strands completion/report eligibility. Do not fake `goal_reached=true` or invent a supported finish action. Early-stop/cap reporting and model stop/safety status handling remain the separate local proposal LC-01/02.

```mermaid
sequenceDiagram
    actor Student
    participant API as FastAPI
    participant DB as Postgres
    participant Model as OpenRouter
    Student->>API: POST /topics/{topicId}/sessions
    API->>DB: Create or find owned session
    API-->>Student: session_id and current outcome
    Student->>API: GET /sessions/{sessionId}/messages
    API-->>Student: History, counts, goal and consent
    loop while open and under cap in conversation
        Student->>API: POST messages/stream with request_id
        alt committed request replay
            API->>DB: Read saved reply
        else new turn
            API->>Model: validity, then status/planning if valid
            API->>DB: Commit student/AI pair and progress
        end
        API-->>Student: SSE text then done
    end
    alt complete requested and goal achieved
        Student->>API: POST end action complete
        API->>DB: Set outcome completed
        API-->>Student: completed; report not yet scheduled
        Student->>API: POST /sessions/{sessionId}/report
        API->>DB: Reuse attempt or insert eligible retry
        API-->>Student: report_status and report
        Student->>API: GET report to poll
        API-->>Student: Latest status and latest ready body if any
    else continue or abandon
        Student->>API: POST end action continue or abandon
        API->>DB: Remain open or set abandoned
        API-->>Student: Current outcome; no report
    end
```

GET `/sessions/{sessionId}/report` does not start generation. Before completion it returns 409; after completion but before any attempt it returns 404. First call POST, then GET to poll. Both return 200 for a successful request, including pending/processing; failed generation is represented by `report_status=failed`, not necessarily a failing polling HTTP status.

| Newest attempt at POST | Behavior |
| --- | --- |
| None | Insert pending attempt, snapshot progress and schedule |
| Pending/processing with unexpired lease | Reuse |
| Ready | Reuse; not forced regeneration |
| Failed or expired pending/processing | Insert and schedule a new attempt |

Teacher POST `/topics/{topicId}/reports/{sessionId}` uses the same retry/reuse rules. It is not “always generate another report.” Snapshot refresh occurs only on insertion. A latest failed/running attempt may coexist with an older ready body: `report_status` describes the newest attempt, while `report` is the latest available ready body or null. Stop normal polling on ready/failed and present appropriate recovery; no fixed server polling interval is promised.

```json
{"report_status":"pending","report":null}
```

Report format gaps remain explicit: the current formatter supplies IDs, constant `version=1`, turn count and `completion_reason=completed`, but not `anonymous_id`/`completed_at`. Structured citations are not enforced yet. The teaching list contains wrapped `{report_status, report, student_display_name}` items; current code does not supply the spec's grouping tags/summary version. These are remaining report/Stage3 contract gaps, not fields the frontend can assume exist.

## Scope and verification

This chunk corrects descriptions/OpenAPI and SSE text fidelity. It does not change permissions, topic settings persistence, goal logic, ending actions, report DTOs or database schemas. Those remain tracked in the project register. Historical PR sequence charts are historical; this revision is the current candidate guide.

The new regression tests exercise actual ASGI routing/serialization, SSE decoding, replay and ending/report ordering with in-memory persistence. Existing service/route tests supplement them. This is not a real Postgres integration or live-model dialogue evaluation. See the local chunk handoff for exact commands and results.
