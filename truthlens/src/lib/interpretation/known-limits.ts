export interface KnownLimit {
    title: string;
    description: string;
}

export function generateKnownLimits(): KnownLimit[] {
    return [
        {
            title: 'Breaking News Volatility',
            description:
                'Rapidly evolving stories may produce unstable rhetorical signals.'
        },
        {
            title: 'Sarcasm and Irony',
            description:
                'Figurative language may increase uncertainty in signal interpretation.'
        },
        {
            title: 'Headline vs Body Divergence',
            description:
                'Headline framing may differ from article body framing.'
        }
    ];
}
