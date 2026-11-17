import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { z } from 'zod';
import { generateTurn, type TurnArgs } from './lib/lab/ai.ts';
import {
  emptyProgress, inquiryBriefSchema, studentMessageSchema,
  type InquiryBrief, type TranscriptMessage, type DialogueProgress, type TurnOutput,
} from './lib/lab/schemas.ts';
import { StructuredRequestError } from './lib/lab/structured-request.ts';

const prefix = '/chat-api/v1';
const topicSchema = z.object({
  topic_id: z.string().trim().min(1).max(100),
  title: z.string().trim().min(1).max(300),
  description: z.string().max(3000).nullish(),
  age_range: z.enum(['13-15', '16-18', '18+']).nullish(),
  max_rounds: z.number().int().min(1).max(15).nullish(),
}).strict();
const messageSchema = z.object({
  content: studentMessageSchema, request_id: z.string().uuid(),
}).strict();
type Done = {
  message_id: string; is_guiding_question: boolean;
  remaining_rounds: number; is_completed: boolean;
};
type Session = {
  id: string; token: string; topicId: string; brief: InquiryBrief;
  transcript: TranscriptMessage[]; progress: DialogueProgress;
  completedTurns: number; completed: boolean; busy: boolean; touched: number;
  requests: Map<string, { content: string; reply: string; done: Done }>;
};
type Generator = (args: TurnArgs, onText: (text: string) => void) =>
  Promise<{ data: TurnOutput; meta?: unknown } | null>;
class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}
function json(res: ServerResponse, status: number, data: unknown) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(data));
}
async function readJson(req: IncomingMessage) {
  let size = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 32768) throw new HttpError(413, '請求內容過大。');
    chunks.push(chunk);
  }
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw new HttpError(422, '請提供有效的 JSON。'); }
}
function briefFromTopic(topic: z.infer<typeof topicSchema>): InquiryBrief {
  // Map PR205's topic to the original dialogue prompt; there is no setup page/API.
  const bands = { '13-15': '13–15 歲', '16-18': '16–18 歲', '18+': '大學及以上' } as const;
  return inquiryBriefSchema.parse({
    learnerBand: bands[topic.age_range ?? '16-18'],
    targetExchanges: topic.max_rounds ?? 5,
    theme: topic.title.length >= 3 ? topic.title : `探究：${topic.title}`,
    inquiryQuestion: topic.title.length >= 5 ? topic.title : `如何思考「${topic.title}」這個問題？`,
    inquiryFocus: '釐清學生對題目的立場與理由，檢驗假設、反例與其他觀點，並邀請學生修正或辯護自己的想法。',
    necessaryContext: topic.description ?? '', exclusions: '',
    openingMessage: `你好！今天我們來想一想：「${topic.title}」。先不用急著找標準答案，說說你的第一個想法是什麼？為什麼會這樣想？`,
  });
}
function snapshot(s: Session) {
  return {
    session_id: s.id, topic_id: s.topicId, status: s.completed ? 'COMPLETED' : 'IN_PROGRESS',
    max_rounds: s.brief.targetExchanges,
    remaining_rounds: s.brief.targetExchanges - s.completedTurns,
    messages: s.transcript.map(m => ({ message_id: m.id, role: m.role, content: m.content })),
  };
}
export function createChatService(options: { generate?: Generator; allowedOrigins?: string[] } = {}) {
  const sessions = new Map<string, Session>();
  const generate = options.generate ?? generateTurn;
  const origins = options.allowedOrigins ?? ['http://127.0.0.1:5180', 'http://localhost:5180'];
  async function handle(req: IncomingMessage, res: ServerResponse) {
    const origin = req.headers.origin;
    if (origin && !origins.includes(origin)) throw new HttpError(403, '此網頁來源未獲允許。');
    if (origin) {
      res.setHeader('Access-Control-Allow-Origin', origin);
      res.setHeader('Vary', 'Origin');
      res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    }
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
    const path = new URL(req.url ?? '/', 'http://localhost').pathname;
    if (path === '/health' && req.method === 'GET') {
      json(res, 200, {
        service: 'pr205-chat-only', status: 'ok',
        ai_configured: !!process.env.OPENROUTER_API_KEY?.trim(),
        model: process.env.OPENROUTER_MODEL || 'openai/gpt-4.1-mini',
      });
      return;
    }
    const now = Date.now();
    for (const [id, s] of sessions) {
      if (!s.busy && now - s.touched > 12 * 60 * 60 * 1000) sessions.delete(id);
    }
    if (path === `${prefix}/sessions` && req.method === 'POST') {
      const topic = topicSchema.parse(await readJson(req));
      if (sessions.size >= 200) throw new HttpError(503, '暫存對話已滿，請重新啟動本機 AI 服務。');
      const brief = briefFromTopic(topic);
      const s: Session = {
        id: randomUUID(), token: randomBytes(32).toString('hex'), topicId: topic.topic_id, brief,
        transcript: [{ id: randomUUID(), role: 'assistant', content: brief.openingMessage, exchange: 0 }],
        progress: structuredClone(emptyProgress), completedTurns: 0, completed: false,
        busy: false, touched: now, requests: new Map(),
      };
      sessions.set(s.id, s);
      json(res, 201, { session_id: s.id, topic_id: s.topicId, session_token: s.token });
      return;
    }
    const match = path.match(/^\/chat-api\/v1\/sessions\/([0-9a-f-]{36})\/(messages|messages\/stream)$/);
    if (!match) throw new HttpError(404, '查無此 API。');
    const s = sessions.get(match[1]);
    if (!s) throw new HttpError(404, '暫存對話已不存在，請重新進入題目。');
    const token = req.headers.authorization?.replace(/^Bearer /, '') ?? '';
    const provided = Buffer.from(token), expected = Buffer.from(s.token);
    if (provided.length !== expected.length || !timingSafeEqual(provided, expected)) {
      throw new HttpError(403, '無權讀取此對話。');
    }
    s.touched = now;
    if (match[2] === 'messages' && req.method === 'GET') { json(res, 200, snapshot(s)); return; }
    if (match[2] !== 'messages/stream' || req.method !== 'POST') throw new HttpError(405, '呼叫方式不正確。');
    const input = messageSchema.parse(await readJson(req));
    const replay = s.requests.get(input.request_id);
    if (replay && replay.content !== input.content) throw new HttpError(409, '同一請求編號不可用於不同內容。');
    if (s.busy) throw new HttpError(409, '上一則訊息仍在處理，請稍後重新載入。');
    if (!replay && s.completed) throw new HttpError(400, '這次對話已結束。');
    s.busy = true;
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform', Connection: 'keep-alive', 'X-Accel-Buffering': 'no',
    });
    res.flushHeaders();
    const event = (name: string, data: unknown) => {
      if (!res.destroyed) res.write(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`);
    };
    const heartbeat = setInterval(() => { if (!res.destroyed) res.write(': waiting\n\n'); }, 15000);
    try {
      if (replay) {
        event('data', replay.reply); event('done', replay.done);
        return;
      }
      const exchangeNumber = s.completedTurns + 1;
      const result = await generate({
        brief: s.brief, transcript: structuredClone(s.transcript),
        previousProgress: structuredClone(s.progress), studentMessage: input.content, exchangeNumber,
      }, text => event('data', text));
      if (!result) throw new HttpError(422, '這則回答未通過原型的有效性檢查，請針對題目補充你的想法；這次不扣回合。');
      const reply = result.data;
      const messageId = randomUUID();
      s.transcript.push(
        { id: randomUUID(), role: 'user', content: input.content, exchange: exchangeNumber },
        { id: messageId, role: 'assistant', content: reply.studentMessage, exchange: exchangeNumber },
      );
      s.progress = reply.progress;
      s.completedTurns = exchangeNumber;
      s.completed = exchangeNumber >= s.brief.targetExchanges ||
        reply.status === 'student_requested_stop' || reply.status === 'safety_interruption';
      const done: Done = {
        message_id: messageId, is_guiding_question: !s.completed,
        remaining_rounds: s.brief.targetExchanges - s.completedTurns, is_completed: s.completed,
      };
      s.requests.set(input.request_id, { content: input.content, reply: reply.studentMessage, done });
      event('done', done);
    } catch (error) {
      const status = error instanceof HttpError || error instanceof StructuredRequestError ? error.status : 502;
      event('error', {
        detail: error instanceof HttpError || error instanceof StructuredRequestError
          ? error.message : 'AI 回覆未通過檢查，這次不扣回合，請重試。', status,
      });
    } finally {
      clearInterval(heartbeat); s.busy = false; s.touched = Date.now(); res.end();
    }
  }
  return createServer((req, res) => {
    void handle(req, res).catch(error => {
      const status = error instanceof HttpError ? error.status : error instanceof z.ZodError ? 422 : 500;
      const detail = error instanceof HttpError ? error.message :
        error instanceof z.ZodError ? '欄位不符規則：訊息須為 1–2000 字，並附有效 request_id；題目須有標題。' : '對話服務暫時無法處理請求。';
      if (!res.headersSent) json(res, status, { detail }); else res.end();
    });
  });
}
