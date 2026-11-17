import { z } from 'zod';

export const learnerBands = ['13–15 歲', '16–18 歲', '大學及以上'] as const;
export const exchangeTargets = [5, 10, 15] as const;
export const studentMessageSchema = z.string().trim().min(1).max(2000);

export const inquiryBriefSchema = z.object({
	learnerBand: z.enum(learnerBands),
	targetExchanges: z.number().int().min(1).max(15),
	theme: z.string().trim().min(3).max(300),
	inquiryQuestion: z.string().trim().min(5).max(600),
	inquiryFocus: z.string().trim().min(5).max(1200),
	necessaryContext: z.string().trim().max(3000),
	exclusions: z.string().trim().max(1500),
	openingMessage: z.string().trim().min(20).max(2000),
});

export const transcriptMessageSchema = z.object({
	id: z.string().max(100),
	role: z.enum(['user', 'assistant']),
	content: z.string().max(2500),
	exchange: z.number().int().min(0).max(15),
});

export const milestoneSchema = z.object({
	met: z.boolean(),
	evidenceExchange: z.number().int().min(1).max(15).nullable(),
	summary: z.string().max(1000),
});

export const evidenceItemSchema = z.object({
	text: z.string().max(1000),
	evidenceExchanges: z.array(z.number().int().min(1).max(15)).max(6),
});

export const progressSchema = z.object({
	position: milestoneSchema,
	reason: milestoneSchema,
	examination: milestoneSchema,
	response: milestoneSchema,
	currentPosition: z.string().max(1400),
	reasonedUncertainty: z.string().max(1400),
	definitions: z.array(evidenceItemSchema).max(10),
	reasons: z.array(evidenceItemSchema).max(10),
	assumptions: z.array(evidenceItemSchema).max(10),
	alternatives: z.array(evidenceItemSchema).max(10),
	counterexamples: z.array(evidenceItemSchema).max(10),
	revisionsOrDefences: z.array(evidenceItemSchema).max(10),
	unresolvedQuestions: z.array(z.string().max(800)).max(10),
	focalTensionConnection: z.string().max(1400),
	dialogueMovement: z.string().max(1400),
	stalledTurns: z.number().int().min(0).max(15),
});

export const dialogueMoves = ['establish_position', 'clarify_term', 'elicit_reason', 'test_assumption', 'present_counterexample', 'consider_alternative', 'change_one_condition', 'connect_back', 'invite_revision_or_defence', 'support_stuck_student', 'redirect_to_inquiry', 'complete_dialogue', 'complete_partial_dialogue', 'safety_response'] as const;
export const dialogueStatuses = ['continue', 'ready', 'partial_complete', 'student_requested_stop', 'safety_interruption'] as const;

export const turnValidationOutputSchema = z.object({
	thinkingProgress: z.string().max(1000),
	validity: z.enum(['YES', 'NO']),
});

export const turnOutputSchema = z.object({
	studentMessage: z.string().trim().min(1).max(2000),
	move: z.enum(dialogueMoves),
	progress: progressSchema,
	status: z.enum(dialogueStatuses),
	safetyLevel: z.enum(['normal', 'restricted_request', 'safeguarding_concern', 'urgent_risk']),
});

export type InquiryBrief = z.infer<typeof inquiryBriefSchema>;
export type TranscriptMessage = z.infer<typeof transcriptMessageSchema>;
export type DialogueProgress = z.infer<typeof progressSchema>;
export type TurnOutput = z.infer<typeof turnOutputSchema>;

export const emptyProgress: DialogueProgress = {
	position: { met: false, evidenceExchange: null, summary: '' },
	reason: { met: false, evidenceExchange: null, summary: '' },
	examination: { met: false, evidenceExchange: null, summary: '' },
	response: { met: false, evidenceExchange: null, summary: '' },
	currentPosition: '', reasonedUncertainty: '', definitions: [], reasons: [], assumptions: [], alternatives: [], counterexamples: [], revisionsOrDefences: [], unresolvedQuestions: [], focalTensionConnection: '', dialogueMovement: '', stalledTurns: 0,
};

export function validateProgress(progress: DialogueProgress, currentExchange: number) {
	const issues: string[] = [];
	const milestones = [['position', progress.position], ['reason', progress.reason], ['examination', progress.examination], ['response', progress.response]] as const;
	for (const [name, milestone] of milestones) {
		if (milestone.met && (milestone.evidenceExchange === null || milestone.evidenceExchange > currentExchange)) issues.push(`${name} has no valid student-exchange evidence.`);
		if (!milestone.met && milestone.evidenceExchange !== null) issues.push(`${name} is unmet but still cites evidence.`);
	}
	if (progress.response.met && progress.examination.met && (progress.response.evidenceExchange ?? 0) <= (progress.examination.evidenceExchange ?? 0)) issues.push('The response milestone must follow the examination milestone.');
	const structurallyReady = currentExchange >= 3 && milestones.every(([, m]) => m.met) && issues.length === 0;
	return { structurallyReady, issues };
}

export function normalizeProgress(progress: DialogueProgress) {
	const normalized = { ...progress };
	for (const key of ['position', 'reason', 'examination', 'response'] as const) {
		normalized[key] = progress[key].met ? progress[key] : { ...progress[key], evidenceExchange: null };
	}
	return normalized;
}

const string = { type: 'string' } as const;
const integer = { type: 'integer' } as const;
const stringArray = { type: 'array', items: string } as const;
function object(properties: Record<string, unknown>) { return { type: 'object', properties, required: Object.keys(properties), additionalProperties: false }; }
function enumString(values: readonly string[]) { return { type: 'string', enum: values }; }
const milestoneJSON = object({
	met: { type: 'boolean' },
	evidenceExchange: { type: ['integer', 'null'] },
	summary: string
});
const evidenceJSON = object({
	text: string,
	evidenceExchanges: { type: 'array', items: integer }
});
export const turnValidationOutputJSON = object({
	thinkingProgress: string,
	validity: enumString(['YES', 'NO'])
});
export const turnOutputJSON = object({
	studentMessage: string,
	move: enumString(dialogueMoves),
	progress: object({
		position: milestoneJSON,
		reason: milestoneJSON,
		examination: milestoneJSON,
		response: milestoneJSON,
		currentPosition: string,
		reasonedUncertainty: string,
		definitions: { type: 'array', items: evidenceJSON },
		reasons: { type: 'array', items: evidenceJSON },
		assumptions: { type: 'array', items: evidenceJSON },
		alternatives: { type: 'array', items: evidenceJSON },
		counterexamples: { type: 'array', items: evidenceJSON },
		revisionsOrDefences: { type: 'array', items: evidenceJSON },
		unresolvedQuestions: stringArray,
		focalTensionConnection: string,
		dialogueMovement: string,
		stalledTurns: integer
	}),
	status: enumString(dialogueStatuses),
	safetyLevel: enumString(['normal', 'restricted_request', 'safeguarding_concern', 'urgent_risk']),
});
