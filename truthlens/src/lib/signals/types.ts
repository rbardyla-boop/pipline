export interface SignalResult {
    id: string;
    label: string;
    score: number;
    uncertainty: number;
    excerpts: string[];
    rationale: string;
    emotionalIntensity?: number;
}

export interface SignalContext {
    articleText: string;
    locale: 'en' | 'fr';
}
