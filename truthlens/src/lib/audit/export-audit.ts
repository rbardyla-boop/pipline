import { SignalResult } from '../signals/types';

export function exportAudit(
    article: {
        url: string;
        title: string;
    },
    signals: SignalResult[]
) {
    return {
        protocol: {
            constitution_version: '1.0',
            audit_schema_version: '1.0',
            signals_registry_version: '1.0'
        },
        article: {
            ...article,
            timestamp: new Date().toISOString()
        },
        signals,
        interpretation: {
            layer1:
                'Observability summary generated from deterministic signals.'
        },
        known_limits: [
            'Signals do not imply intent.',
            'Framing variation does not determine factual correctness.'
        ],
        exported_at: new Date().toISOString()
    };
}
