import { SignalContext, SignalResult } from './types';

export function detectMutualInfo(context: SignalContext): SignalResult {
    return {
        id: 'mutual-info',
        label: 'Primary Source Overlap',
        score: 0,
        uncertainty: 0.5,
        emotionalIntensity: 0,
        excerpts: [],
        rationale:
            'Placeholder for keyword overlap comparison with primary sources.'
    };
}
