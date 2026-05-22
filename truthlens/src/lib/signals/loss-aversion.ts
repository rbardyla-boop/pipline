import { SignalContext, SignalResult } from './types';

const LOSS_PATTERNS = [
    'lose access',
    'you could lose',
    'at risk of losing',
    'irreversible damage',
    'too late',
    'no longer available',
    'permanently lost',
    'cannot be undone',
    'last chance'
];

export function detectLossAversion(context: SignalContext): SignalResult {
    const text = context.articleText.toLowerCase();
    const matches = LOSS_PATTERNS.filter((pattern) => text.includes(pattern));
    const score = Math.min(matches.length / 4, 1);

    return {
        id: 'loss_aversion',
        label: 'Loss Aversion Signal',
        score,
        uncertainty: 0.2,
        emotionalIntensity: Math.min(score * 1.2, 1),
        excerpts: matches,
        rationale: 'Detects loss-frame rhetoric designed to trigger scarcity-driven behavior.'
    };
}
