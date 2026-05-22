import { SignalContext, SignalResult } from './types';

const URGENCY_PATTERNS = [
    'urgent',
    'immediately',
    'right now',
    'breaking',
    'critical',
    'before it is too late'
];

export function detectUrgency(context: SignalContext): SignalResult {
    const text = context.articleText.toLowerCase();

    const matches = URGENCY_PATTERNS.filter((pattern) =>
        text.includes(pattern)
    );

    const score = Math.min(matches.length / 5, 1);

    return {
        id: 'urgency',
        label: 'Urgency Signal',
        score,
        uncertainty: 0.2,
        emotionalIntensity: score,
        excerpts: matches,
        rationale:
            'Detects compression-pressure rhetoric and time scarcity framing.'
    };
}
