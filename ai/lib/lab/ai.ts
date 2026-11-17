import { LAB_CONFIG } from './config.ts';
import { STAGE2_PROMPT, STAGE2_PROMPT_VALIDITY } from './prompts.ts';
import {
  inquiryBriefSchema, transcriptMessageSchema, progressSchema, studentMessageSchema,
  turnValidationOutputJSON, turnValidationOutputSchema, turnOutputJSON, turnOutputSchema,
  normalizeProgress,
  type InquiryBrief, type TranscriptMessage, type DialogueProgress,
} from './schemas.ts';
import { requestStructured, StructuredRequestError } from './structured-request.ts';

export type TurnArgs = {
  brief: InquiryBrief; transcript: TranscriptMessage[]; previousProgress: DialogueProgress;
  studentMessage: string; exchangeNumber: number;
};
/** Prototype Stage 2: validity check → dialogue turn → progress normalization. */
export async function generateTurn(args: TurnArgs, onText: (text: string) => void) {
  const apiKey = process.env.OPENROUTER_API_KEY?.trim();
  if (!apiKey || apiKey === '填入你的金鑰') {
    throw new StructuredRequestError('尚未設定 AI 金鑰，請填寫 ai/.env.local 後重新啟動。');
  }
  const model = process.env.OPENROUTER_MODEL?.trim() || 'openai/gpt-4.1-mini';
  const common = { model, apiKey, siteUrl: process.env.OPENROUTER_SITE_URL || 'http://localhost' };
  const brief = inquiryBriefSchema.parse(args.brief);
  const transcript = transcriptMessageSchema.array().max(31).parse(args.transcript);
  const previousProgress = progressSchema.parse(args.previousProgress);
  const studentMessage = studentMessageSchema.parse(args.studentMessage);
  const exchangeNumber = Math.max(1, Math.min(brief.targetExchanges, Math.trunc(args.exchangeNumber)));
  const validation = await requestStructured({
    ...common, name: 'validation', instructions: STAGE2_PROMPT_VALIDITY,
    input: { transcript, latestStudentMessage: studentMessage },
    schema: turnValidationOutputJSON,
  });
  if (turnValidationOutputSchema.parse(validation.decoded).validity === 'NO') return null;
  const result = await requestStructured({
    ...common, name: 'dialogue_turn', instructions: STAGE2_PROMPT,
    input: {
      interfaceLanguage: 'zh-TW', approvedInquiryBrief: brief, currentExchange: exchangeNumber,
      remainingExchanges: brief.targetExchanges - exchangeNumber,
      previousProgress, transcript, latestStudentMessage: studentMessage,
    },
    schema: turnOutputJSON, onText,
  });
  let data;
  try { data = turnOutputSchema.parse(result.decoded); }
  catch { throw new StructuredRequestError('AI 回覆未通過原型格式檢查，這次不扣回合，請重試。', 502); }
  data.progress = normalizeProgress(data.progress);
  return { data, meta: { model, promptVersion: LAB_CONFIG.promptVersions.stage2 } };
}
