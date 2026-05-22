import { SignalContext, SignalResult } from './types';

export function detectEntropy(context: SignalContext): SignalResult {
    const words = context.articleText
        .toLowerCase()
        .match(/\b\w+\b/g) ?? [];

    const total = words.length;

    if (total === 0) {
        return {
            id: 'entropy',
            label: 'Narrative Entropy',
            score: 0,
            uncertainty: 0.1,
            excerpts: [],
            rationale: 'No word tokens found in article.'
        };
    }

    const uniqueRatio = new Set(words).size / total;
    // Low uniqueness = high repetition = narrative control signal
    const score = parseFloat((1.0 - uniqueRatio).toFixed(2));

    return {
        id: 'entropy',
        label: 'Narrative Entropy',
        score,
        uncertainty: 0.1,
        excerpts: [],
        rationale: `Lexical diversity ratio: ${uniqueRatio.toFixed(4)}. Low diversity indicates repetitive or controlled narrative framing.`
    };
}
