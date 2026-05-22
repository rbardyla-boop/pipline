interface ExtensionSignalResult {
    id: string;
    label: string;
    score: number;
    excerpts: string[];
}

// 1. DOM text extraction — prefer article/main content nodes
function extractDocumentPayload(): string {
    const selectors = ['article', 'main', '[role="main"]', '.content', '.post-body', '.article-body'];
    for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (el?.textContent) return el.textContent.trim();
    }
    return document.body.textContent?.trim() ?? '';
}

// 2. Client-side signal pattern matching
function analyzeTextLocally(text: string): ExtensionSignalResult[] {
    const lower = text.toLowerCase();

    const rules: Array<{ id: string; label: string; patterns: RegExp[] }> = [
        {
            id: 'fear',
            label: 'Fear Vector',
            patterns: [/dangerous/g, /\bthreat\b/g, /\bcrisis\b/g, /catastrophic/g]
        },
        {
            id: 'urgency',
            label: 'Urgency Spike',
            patterns: [/\burgent\b/g, /immediately/g, /right now/g, /\bbreaking\b/g, /\bcritical\b/g]
        },
        {
            id: 'authority',
            label: 'Authority Framing',
            patterns: [/experts say/g, /officials stated/g, /scientists confirm/g, /government sources/g]
        },
        {
            id: 'loss_aversion',
            label: 'Loss Framing',
            patterns: [/lose access/g, /irreversible/g, /too late/g, /last chance/g]
        }
    ];

    return rules.map((rule) => {
        let matchCount = 0;
        rule.patterns.forEach((regex) => {
            const hits = lower.match(regex);
            if (hits) matchCount += hits.length;
        });
        return {
            id: rule.id,
            label: rule.label,
            score: Math.min(1.0, matchCount / 4.0),
            excerpts: []
        };
    });
}

// 3. Signal overlay UI injection
function injectAnalysisInterface(signals: ExtensionSignalResult[]) {
    const existing = document.getElementById('truthlens-frame');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'truthlens-frame';
    Object.assign(overlay.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        width: '300px',
        backgroundColor: '#0d0d0d',
        color: '#e0e0e0',
        fontFamily: '"Courier New", monospace',
        fontSize: '12px',
        padding: '14px',
        borderRadius: '8px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.7)',
        zIndex: '2147483647',
        border: '1px solid #2a2a2a',
        userSelect: 'none'
    });

    const header = document.createElement('div');
    header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:10px';
    header.innerHTML = '<span style="color:#00ff88;font-weight:bold;font-size:13px;">⚡ TRUTHLENS</span>';

    const closeBtn = document.createElement('span');
    closeBtn.textContent = '×';
    closeBtn.style.cssText = 'cursor:pointer;color:#666;font-size:16px;line-height:1';
    closeBtn.onclick = () => overlay.remove();
    header.appendChild(closeBtn);
    overlay.appendChild(header);

    signals.forEach((s) => {
        const pct = Math.round(s.score * 100);
        const barColor = s.score > 0.6 ? '#ff3333' : s.score > 0.3 ? '#ffaa00' : '#444';
        const row = document.createElement('div');
        row.style.marginBottom = '8px';
        row.innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:3px">
                <span>${s.label}</span>
                <span style="color:${barColor}">${pct}%</span>
            </div>
            <div style="background:#1a1a1a;height:4px;border-radius:2px">
                <div style="background:${barColor};width:${pct}%;height:100%;border-radius:2px;transition:width 0.3s"></div>
            </div>`;
        overlay.appendChild(row);
    });

    document.body.appendChild(overlay);
}

// 4. SATS idle-state loop (Page Visibility API)
document.addEventListener('visibilitychange', () => {
    const overlay = document.getElementById('truthlens-frame');
    if (document.visibilityState === 'hidden') {
        if (overlay) overlay.style.opacity = '0.3';
        console.log('[TRUTHLENS SATS] Tab sleep — priming signal vectors.');
    } else if (document.visibilityState === 'visible') {
        if (overlay) overlay.style.opacity = '1';
        // On return: subtly reframe the dominant heading toward precision
        const h1 = document.querySelector('h1');
        if (h1 && h1.textContent) {
            h1.style.transition = 'color 0.8s ease';
            h1.style.color = '#00ff88';
            setTimeout(() => { h1.style.color = ''; }, 2000);
        }
        console.log('[TRUTHLENS SATS] Page active — realigning focal vectors.');
    }
});

// Bootstrap
const pageText = extractDocumentPayload();
if (pageText.length > 100) {
    const signals = analyzeTextLocally(pageText);
    const triggered = signals.filter((s) => s.score > 0.2);
    if (triggered.length > 0) {
        injectAnalysisInterface(signals);
    }
}
