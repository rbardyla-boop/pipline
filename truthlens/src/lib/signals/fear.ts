import { SignalContext, SignalResult } from './types';

const FEAR_PATTERNS = [
    'dangerous',
    'threat',
    'crisis',
    'fear',
    'catastrophic',
    'risk to public safety'
];

export function detectFear(context: SignalContext): SignalResult {
    const text = context.articleText.toLowerCase();

    const matches = FEAR_PATTERNS.filter((pattern) =>
        text.includes(pattern)
    );

    const score = Math.min(matches.length / 5, 1);

    return {
        id: 'fear',
        label: 'Fear Signal',
        score,
        uncertainty: 0.3,
        emotionalIntensity: score,
        excerpts: matches,
        rationale:
            'Detects emotionally amplifying language associated with risk framing.'
    };
}
