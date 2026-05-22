import { SignalContext, SignalResult } from '../signals/types';
import { detectFear } from '../signals/fear';
import { detectUrgency } from '../signals/urgency';
import { detectAuthority } from '../signals/authority';
import { detectLossAversion } from '../signals/loss-aversion';
import { detectEntropy } from '../signals/entropy';

export function runAnalysis(context: SignalContext): SignalResult[] {
    return [
        detectFear(context),
        detectUrgency(context),
        detectAuthority(context),
        detectLossAversion(context),
        detectEntropy(context),
    ];
}

export function formatSignalProfile(signals: SignalResult[]): string {
    return signals.map((s) => `${s.id}=${s.score.toFixed(2)}`).join(' ');
}

export function hasHighIntensitySignal(signals: SignalResult[], threshold = 0.5): boolean {
    return signals.some((s) => s.score > threshold);
}
