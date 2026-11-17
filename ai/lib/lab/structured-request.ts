import { readStructuredStream } from './streaming.ts';

export class StructuredRequestError extends Error {
  status: number;
  constructor(message: string, status = 503) {
    super(message);
    this.status = status;
  }
}
type RequestArgs = {
  name: string; instructions: string; input: unknown; schema: object;
  model: string; apiKey: string; siteUrl: string; onText?: (text: string) => void;
};
type Payload = {
  choices?: { finish_reason?: string | null; message?: { content?: string | null } }[];
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
};
export async function requestStructured(args: RequestArgs, send: typeof fetch = fetch) {
  const deadline = AbortSignal.timeout(60000);
  let response: Response;
  let body: Payload;
  try {
    response = await send('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${args.apiKey}`,
        'Content-Type': 'application/json', 'HTTP-Referer': args.siteUrl,
        'X-Title': 'PR205 Chat Integration',
      },
      body: JSON.stringify({
        model: args.model,
        messages: [
          { role: 'system', content: args.instructions },
          { role: 'user', content: JSON.stringify(args.input) },
        ],
        temperature: 0.35, max_tokens: 4500,
        ...(args.onText ? { stream: true, stream_options: { include_usage: true } } : {}),
        response_format: {
          type: 'json_schema',
          json_schema: { name: args.name, strict: true, schema: args.schema },
        },
      }),
      signal: deadline,
    });
    body = response.ok && args.onText
      ? await readStructuredStream(response, args.onText)
      : await response.json().catch(() => ({})) as Payload;
  } catch {
    throw new StructuredRequestError(
      deadline.aborted ? 'AI 回應逾時，請稍後重試。' : '無法取得完整 AI 回覆，請稍後重試。',
      deadline.aborted ? 504 : 503,
    );
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: 'AI 服務金鑰無效，請檢查 ai/.env.local。',
      402: 'AI 服務額度不足，請檢查 OpenRouter 帳戶。',
      403: '目前金鑰無法使用指定模型。',
      404: '找不到指定模型，請檢查 ai/.env.local 的 OPENROUTER_MODEL。',
      429: 'AI 服務目前忙碌，請稍後再試。',
    };
    throw new StructuredRequestError(messages[response.status] ?? 'AI 服務暫時無法完成請求。');
  }
  const choice = body.choices?.[0];
  if (choice?.finish_reason !== 'stop') {
    throw new StructuredRequestError('AI 未完整產生回覆，這次不扣回合，請重試。', 502);
  }
  try {
    return { decoded: JSON.parse(choice.message?.content ?? ''), usage: body.usage ?? {} };
  } catch {
    throw new StructuredRequestError('AI 回覆格式無法解析，這次不扣回合，請重試。', 502);
  }
}
