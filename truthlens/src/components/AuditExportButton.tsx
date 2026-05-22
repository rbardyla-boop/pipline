import { exportAudit } from '@/lib/audit/export-audit';
import { SignalResult } from '@/lib/signals/types';

export function AuditExportButton({
    article,
    signals
}: {
    article: { url: string; title: string };
    signals: SignalResult[];
}) {
    const handleExport = () => {
        const audit = exportAudit(article, signals);
        const blob = new Blob([JSON.stringify(audit, null, 2)], {
            type: 'application/json'
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'truthlens-audit.json';
        link.click();
        URL.revokeObjectURL(url);
    };

    return (
        <button type="button" onClick={handleExport}>
            Export Audit
        </button>
    );
}
