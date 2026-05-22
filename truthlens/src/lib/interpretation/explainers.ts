import { SignalResult } from '../signals/types';

export function generateSummary(signals: SignalResult[]): string {
    const activeSignals = signals.filter((s) => s.score > 0.3);

    if (activeSignals.length === 0) {
        return 'Minimal rhetorical signal activity detected.';
    }

    return `Detected ${activeSignals.length} notable rhetorical signals with visible uncertainty bands.`;
}
