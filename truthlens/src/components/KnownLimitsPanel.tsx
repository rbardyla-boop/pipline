import { generateKnownLimits } from '@/lib/interpretation/known-limits';

export function KnownLimitsPanel() {
    const limits = generateKnownLimits();

    return (
        <section className="rounded-2xl border p-4 space-y-4">
            <div>
                <h2 className="text-lg font-semibold">Known Limits</h2>
                <p className="text-sm text-muted-foreground">
                    These signals are observational and uncertainty-weighted.
                </p>
            </div>

            <div className="space-y-3">
                {limits.map((limit) => (
                    <div key={limit.title} className="rounded-xl border p-3">
                        <h3 className="font-medium">{limit.title}</h3>
                        <p className="text-sm text-muted-foreground">
                            {limit.description}
                        </p>
                    </div>
                ))}
            </div>
        </section>
    );
}
