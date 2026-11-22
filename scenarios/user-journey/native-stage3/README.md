# Native Stage3 API acceptance

Follows the author's httpyac journey structure. Use only a disposable local backend/database with a deterministic provider. Without one, starting synthesis may spend provider credits; live calls require separate approval. No production/shared server. This scenario is supplied for manual acceptance and has not been executed in the implementation workspace.

Prerequisites: completed Stage1/2 fixture, all existing topic dialogues ended, every eligible report ready with native evidence. Set local environment variables BASE_URL (including /api/v1), TOPIC_ID, SESSION_ID, TEACHER_TOKEN and STUDENT_TOKEN. Tokens are raw access tokens, without Bearer. Do not commit values or publish request headers/logs.

Run these named requests using `httpyac send scenarios/user-journey/native-stage3/01-native-stage3.http --name NAME`:

1. `individualReport`: verifies the student can read their report independently of class synthesis.
2. `startSynthesis`: queues the class job. Also run against a fixture with an open dialogue or pending personal report and expect409 instead of this positive assertion.
3. `readDraft`: run after the job is ready. If it remains pending/processing, poll the GET manually for at most60 seconds; failed/timeout is a failed acceptance run, not permission to ignore the assertion.
4. `publishReviewed`: loads the ready draft, reviews that exact text and publishes it. It does not regenerate synthesis.
5. `studentPublished`: checks aggregate response and private-field exclusion.
6. `withdraw`: removes publication; student report remains available.

Run fixtures for normal completion, early/cap ending, mixed partial/inconclusive and all-inconclusive cohorts. Unit/API tests cover negative membership/output cases; tests/integration/test_native_stage3_postgres.py covers persisted gates and native-version retention. This journey does not establish AI grouping quality.
