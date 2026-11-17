import test from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { createChatService } from '../service.ts';
import { emptyProgress } from '../lib/lab/schemas.ts';

const topic = { topic_id: 't-lie', title: '善意的謊言是對的嗎？', age_range: '13-15', max_rounds: 2 };
function answer(text = '你會如何區分善意和欺騙？', status = 'continue') {
  return { data: { studentMessage: text, progress: structuredClone(emptyProgress), move: 'elicit_reason', status, safetyLevel: 'normal' } };
}
async function app(t, generate) {
  const server = createChatService({ generate });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => { server.close(); server.closeAllConnections(); });
  const base = 'http://127.0.0.1:' + server.address().port;
  const create = await fetch(base + '/chat-api/v1/sessions', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(topic),
  });
  assert.equal(create.status, 201);
  const session = await create.json();
  const url = base + '/chat-api/v1/sessions/' + session.session_id + '/messages';
  const headers = { 'Content-Type': 'application/json', Authorization: 'Bearer ' + session.session_token };
  return {
    base, session, url, headers,
    send: (content, request_id = randomUUID()) => fetch(url + '/stream', { method: 'POST', headers, body: JSON.stringify({ content, request_id }) }),
    history: async () => (await fetch(url, { headers })).json(),
  };
}
function events(raw) {
  return raw.split(/\r?\n\r?\n/).filter(frame => frame.startsWith('event:')).map(frame => {
    const [event, data] = frame.split('\n');
    return { event: event.slice(7), data: JSON.parse(data.slice(6)) };
  });
}
test('PR205 topic creates opening without calling AI; read requires session token', async t => {
  const a = await app(t, async () => { assert.fail('must not call AI on creation'); });
  const history = await a.history();
  assert.equal(history.messages.length, 1);
  assert.match(history.messages[0].content, /善意的謊言/);
  assert.equal(history.remaining_rounds, 2);
  assert.equal((await fetch(a.url)).status, 403);
  assert.equal((await fetch(a.url, { headers: { Authorization: 'Bearer wrong' } })).status, 403);
  assert.equal((await fetch(a.base + '/health')).status, 200);
  assert.equal((await fetch(a.url, { headers: { ...a.headers, Origin: 'https://untrusted.example' } })).status, 403);
  const allowed = await fetch(a.url, { headers: { ...a.headers, Origin: 'http://127.0.0.1:5180' } });
  assert.equal(allowed.headers.get('access-control-allow-origin'), 'http://127.0.0.1:5180');
});
test('text arrives before generation finishes; only canonical messages are stored', async t => {
  let finish;
  const gate = new Promise(resolve => { finish = resolve; });
  const a = await app(t, async (args, text) => {
    assert.equal(args.brief.inquiryQuestion, topic.title);
    assert.equal(args.brief.learnerBand, '13–15 歲');
    assert.equal(args.exchangeNumber, 1);
    text('你會如何');
    await gate;
    text('區分善意和欺騙？');
    return answer();
  });
  const response = await a.send('我認為善意的謊言可以保護別人。');
  const reader = response.body.getReader();
  const first = new TextDecoder().decode((await reader.read()).value);
  assert.match(first, /你會如何/);
  assert.equal((await a.history()).messages.length, 1);
  finish();
  let rest = '';
  for (;;) { const { done, value } = await reader.read(); if (done) break; rest += new TextDecoder().decode(value); }
  const result = events(first + rest);
  assert.equal(result.filter(e => e.event === 'data').map(e => e.data).join(''), answer().data.studentMessage);
  assert.equal(result.at(-1).event, 'done');
  assert.equal((await a.history()).messages.length, 3);
  assert.equal((await a.history()).remaining_rounds, 1);
});
test('request_id replay does not regenerate, double-save or spend a turn; changed payload conflicts', async t => {
  let calls = 0;
  const a = await app(t, async (_, text) => { calls++; text('你會如何區分善意和欺騙？'); return answer(); });
  const id = randomUUID();
  const first = events(await (await a.send('這是我的理由。', id)).text());
  const replay = events(await (await a.send('這是我的理由。', id)).text());
  assert.deepEqual(replay, first);
  assert.equal(calls, 1);
  assert.equal((await a.history()).remaining_rounds, 1);
  assert.equal((await a.send('不同內容', id)).status, 409);
  await (await a.send('我願意再考慮反例。')).text();
  assert.equal((await a.history()).status, 'COMPLETED');
  assert.equal((await a.send('還想多說一句。')).status, 400);
  assert.equal((await a.send('這是我的理由。', id)).status, 200);
});
test('invalid input and rejected prototype validity leave history and rounds unchanged', async t => {
  let calls = 0;
  const a = await app(t, async () => { calls++; return null; });
  assert.equal((await a.send(' ')).status, 422);
  assert.equal((await a.send('字'.repeat(2001))).status, 422);
  const result = events(await (await a.send('不相關內容')).text());
  assert.equal(result.at(-1).event, 'error');
  assert.equal(result.at(-1).data.status, 422);
  assert.equal(calls, 1);
  assert.equal((await a.history()).remaining_rounds, 2);
  assert.equal((await a.history()).messages.length, 1);
});
test('one turn at a time; provider failure rolls back provisional text and permits retry', async t => {
  let finish, calls = 0;
  const gate = new Promise(resolve => { finish = resolve; });
  const a = await app(t, async (_, text) => {
    calls++; text('暫時文字');
    if (calls === 1) { await gate; throw new Error('provider secret must not leak'); }
    return answer('正式回覆');
  });
  const id = randomUUID();
  const first = await a.send('我有這個想法。', id);
  assert.equal((await a.send('另一則訊息')).status, 409);
  finish();
  const result = events(await first.text());
  assert.equal(result.at(-1).event, 'error');
  assert.doesNotMatch(JSON.stringify(result), /provider secret/);
  assert.equal((await a.history()).messages.length, 1);
  await (await a.send('我有這個想法。', id)).text();
  assert.equal((await a.history()).messages.at(-1).content, '正式回覆');
  assert.equal(calls, 2);
});
test('this service exposes conversation routes only', async t => {
  const a = await app(t, async () => answer());
  for (const path of ['/topics/t/setup', '/topics/t/setup/generate', '/topics/t/summary', '/sessions/x/report', '/']) {
    assert.equal((await fetch(a.base + '/chat-api/v1' + path)).status, 404);
  }
});
test('prototype stop status is respected before the turn limit', async t => {
  const a = await app(t, async (_, text) => {
    text('我們就先停在這裡。');
    return answer('我們就先停在這裡。', 'student_requested_stop');
  });
  const result = events(await (await a.send('我想先停止。')).text());
  assert.equal(result.at(-1).data.is_completed, true);
  assert.equal((await a.history()).status, 'COMPLETED');
  assert.equal((await a.history()).remaining_rounds, 1);
});
