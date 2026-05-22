import { SignalContext, SignalResult } from './types';

const AUTHORITY_PATTERNS = [
    'experts say',
    'officials stated',
    'government sources',
    'scientists confirm',
    'according to authorities',
    'researchers found',
    'leading experts'
];

export function detectAuthority(context: SignalContext): SignalResult {
    const text = context.articleText.toLowerCase();
    const matches = AUTHORITY_PATTERNS.filter((pattern) => text.includes(pattern));
    const score = Math.min(matches.length / 4, 1);

    return {
        id: 'authority',
        label: 'Authority Signal',
        score,
        uncertainty: 0.25,
        emotionalIntensity: score * 0.7,
        excerpts: matches,
        rationale: 'Detects deference to unnamed institutional authority as rhetorical legitimation.'
    };
}
