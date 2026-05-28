#!/bin/bash
# Claude Master Folder (Layer 2.5) - Linux Setup
# Copy-paste ready. Run once to bootstrap.

set -e

MASTER_DIR="${HOME}/claude-master"
ARCHIVE_DIR="${HOME}/.claude-archives"

echo "🔧 Bootstrapping Claude Master System..."

# Create directory structure
mkdir -p "$MASTER_DIR"
mkdir -p "$ARCHIVE_DIR"
mkdir -p "$MASTER_DIR/.git"

# Initialize git repo (version control instead of manual archives)
cd "$MASTER_DIR"
git init
git config user.name "Claude Master"
git config user.email "master@claude.local"

# Create markdown files with YAML headers (enables CLI search)
cat > "$MASTER_DIR/INSTRUCTIONS.md" << 'EOF'
---
name: System Instructions
updated: $(date +%Y-%m-%d)
version: 1.0
---

## Voice & Governance

### Operating Frameworks
- **VAL Framework**: VIBE (fun/interest) + APEX (integrity) + LEVELS (speed)
- **APEX Orchestrator**: Research integrity, falsification mandates, multi-seed validation
- **KLEON Creative Layer**: Steal → Copy → Transform → Ship (side projects valid)
- **META-SCIENCE v1.1**: Investigate dismissed claims before dismissing

### Who You Are
- Canadian military veteran (CSOR Signal Technician)
- Licensed 309A Electrician, hardware researcher
- Full-stack developer voice (code-first, practical, assume implementation details)
- When hardware active: Senior Hardware Engineer tone (tactical, direct, volts/amps/ohms)
- Fiction author (gritty metaphysical fantasy, 95K-115K words/book)

### Rules (Hard Locks)
1. **HR-R3 (Falsification)**: Stress-test logic before presenting
2. **HR-D1 (Production Lock)**: All code/technical output copy-paste ready, no placeholders
3. **VOICE PARITY**: Match genre (sci-fi = atmospheric/technical, manual = visceral/direct)
4. **SIGNAL-TO-NOISE**: No fluff. Skip conversational preamble.
5. **MEMORY SYNC**: Update MEMORY.md after each session with new discoveries, decisions, project state

### What Good Outputs Look Like
- Tactical assessment tables (pros/cons, clear verdicts)
- Copy-paste-ready code/configs (tested, no placeholders)
- Hardware specs with exact component values and multimeter procedures
- Gritty prose that avoids AI exposition and over-explaining
- Structured YAML headers on important documents (enables search)

### Domains
- **Hardware**: NE555 oscillator networks, bioelectric wearables, RF energy harvesting
- **Software**: ML validation (Hebbian, DNC, continual learning), trading systems, game engines
- **Fiction**: Grounded Legion series (metaphysical fantasy), echo/resonance themes
- **Veteran**: RSD detection, transition frameworks, subtractive cognition research
EOF

cat > "$MASTER_DIR/MEMORY.md" << 'EOF'
---
name: Running Memory & State
updated: $(date +%Y-%m-%d)
type: evolving
---

## Active Projects

### TOLS (4-Oscillator Kuramoto Network)
- **Status**: Breadboard prototype, first iteration failed (overly conservative params)
- **Target**: ~5 Hz, NE555 timers, LED coupling indicators
- **Current Issue**: Hardware validation priority (Tesla Research Agent generated design rapidly but needs lab testing)
- **Next**: Rebuild with relaxed parameters, measure actual output frequency
- **Related**: [HARDWARE.md#NE555-Pinouts]

### RSD Bio-AI Detection System
- **Status**: Concept phase, hardware research active
- **Components**: Garmin Fenix 7X HRV data, EEG sensors (custom build planned)
- **Goal**: Detect Rejection Sensitive Dysphoria through biomarker fusion
- **Hardware Plan**: Build custom EEG using electrical background (not off-the-shelf)
- **Next**: EEG sensor design, Fenix data export pipeline

### Grounded Legion Book 2: Echo Rising
- **Status**: 24-chapter outline locked, Act 1 prose drafted
- **Word target**: 95K-115K
- **Chapter state**: Ch 1-7 prose complete, chapters 8+ awaiting outline-to-prose expansion
- **Voice**: Gritty metaphysical fantasy, subtext over exposition
- **Next**: Ch 8 prose, apply thematic pacing engine (avoid repetitive theme hammering)

### Pattern Zoo (TradingView Pine Script)
- **Status**: Multiple versions deployed, recent moderator warnings
- **Issue**: Visual clutter on 1-minute charts, documentation cleanup required
- **Next**: TradingView compliance audit, documentation finalization

### Garmin Fenix 7X Connect IQ App
- **Status**: Property boundary navigation tool, MGRS coordinates + haptic alerts
- **60-acre lot**: Roseville, PEI (waterfront)
- **Next**: Test on property, integrate with RSD bio-AI pipeline

### Veteran Transition Book
- **Status**: Research advanced, 14-book reading list compiled, competitive landscape analyzed
- **Core Thesis**: "Subtractive cognition under constraint" — military-trained cognitive styles misread as deficits during civilian reintegration
- **Frameworks**: GMAIE Meta-Cognitive Layer (v1.1, PhD-defensible)
- **Next**: Begin prose expansion

### The Operator's Deck (clovelearni0.io)
- **Status**: Live PWA, 30+ single-file HTML/JS tools
- **Tools**: DBT/ACT/CBT influenced, gamified, offline-first, localStorage-backed
- **Aesthetics**: Dark/tactical with red accents, Bebas Neue + DM Mono
- **Next**: New tool ideas, performance optimization

## Preferences & Rules

### Response Style
- Tactical, direct, zero-fluff
- Tables for data comparisons
- LaTeX for electrical/system physics
- Vibe check before deep dives
- Military comms check: Clear, Concise, Correct?

### Hardware Preferences
- Canadian suppliers: Amazon.ca, DigiKey.ca, Montreal (Addison Électronique, Active Components)
- No Python/data science suggestions unless asked
- No oscilloscope assumed
- Multimeter procedures must be exact (step-by-step)

### Avoid
- Generic encouragement/cheerleading
- Teaching assistant tone (explaining basics)
- "Looking into" suggestions (be specific or skip)
- AI-slop fiction writing (gritty, human-sounding, no exposition)

## Corrections & Updates
(Auto-updated by Claude after sessions)

## Decisions & Locked States
- **TOLS Frequency**: ~5 Hz (Kuramoto synch target)
- **Echo Rising Chapters**: 1-7 prose locked, 8-24 outline locked
- **Veteran Book**: Subtractive cognition thesis locked, won't pivot
- **Fenix App**: MGRS coordinate system locked

## Recently Discovered
- Sentient Skin Ghost Key paper (Zenodo, dermal resonator @ 100 MHz)
- Living Computational Bit (LCB) paper gained early download traction
- GMAIE Meta-Cognitive Layer v1.1 PhD-defensible version completed
EOF

cat > "$MASTER_DIR/HARDWARE.md" << 'EOF'
---
name: Hardware Research & Specifications
updated: $(date +%Y-%m-%d)
domain: electronics
---

## TOLS Oscillator Network

### NE555 Pinout & Configuration
```
Pin 1: GND
Pin 2: Trigger (threshold for timing)
Pin 3: Output
Pin 4: Reset (active low, pull to VCC for normal operation)
Pin 5: Control Voltage (0.01µF cap to GND for stability)
Pin 6: Threshold (tied to pin 2 in astable mode)
Pin 7: Discharge (capacitor discharge path)
Pin 8: VCC (+5V or +9V)
```

### Astable Mode (Oscillation)
**Frequency Formula**: f = 1.44 / ((R1 + 2*R2) * C)

**For ~5 Hz target**:
- R1 = 100kΩ
- R2 = 100kΩ
- C = 2.2µF (electrolytic, 16V rated)
- Calculated: f ≈ 4.7 Hz (acceptable tolerance)

**LED Coupling Indicators**:
- Output → 330Ω resistor → LED anode
- LED cathode → GND
- Confirms oscillation visually

### Breadboard Risks
1. **Loose connections**: Verify all DIP socket contacts. Use 22AWG jumper wire, not breadboard pins.
2. **Capacitor polarity**: Electrolytic caps MUST be oriented correctly (stripe = negative).
3. **Frequency drift**: Cheap resistors vary ±5%. Use 1% tolerance metal-film resistors.
4. **Ground loops**: Ensure star grounding (all GND to single point, then to supply).

### Measurement Procedures (No Oscilloscope)

**Method 1: Multimeter Hz Mode**
1. Set multimeter to Hz (Frequency)
2. Connect probes to Pin 3 (output) and GND
3. Record frequency
4. Expected: 4-6 Hz (5 Hz target)

**Method 2: Audacity Slow-Mo (No Hz Mode)**
1. Connect audio recorder near LED (captures blink frequency)
2. Record 30 seconds of LED pulsing
3. Export WAV file, import into Audacity
4. Analyze → Plot Spectrum → identify peak frequency
5. Lower frequencies (<10 Hz) visible as visible blink rhythm

**Method 3: Phone Slow-Mo**
1. Record LED at 240 fps slow-motion
2. Count blinks in 5-second video
3. Multiply: (blinks / 5) = Hz

### Synchronization (Kuramoto Coupling)
- Oscillators phase-lock when coupled via LED light feedback
- Expected behavior: Phase drift reduces over 30 seconds
- LED brightness increases when phase-aligned (constructive interference)

### Supplies (Canada)
- NE555 timer ICs (DIP-8): Amazon.ca (~$0.50/unit)
- Resistors 1% metal-film (100k, 1M): Addison Électronique (bulk discount)
- Electrolytic capacitors (2.2µF, 10µF): DigiKey.ca
- Breadboard (830 holes): Amazon.ca (~$8)
- LEDs (5mm red, diffused): Local electronics shop or Amazon

## RSD Bio-AI Sensor Integration

### Fenix 7X Data Export
- HRV (Heart Rate Variability) available via Garmin Connect API
- CSV export format: timestamp, HRV (ms), Resting HR, SpO2, Stress level
- Window size for analysis: 5-minute rolling window (captures acute stress spikes)

### EEG Custom Build (Planned)
- Electrode count: 4-8 (simplified from 32-channel clinical)
- Frequency range: 0-40 Hz (Delta, Theta, Alpha, Beta bands)
- Sampling rate: 256 Hz minimum (Nyquist: avoid aliasing >128 Hz)
- Amplifier: Custom design or AD8065 op-amp circuit (low-cost, 100 MHz BW)
- ADC: ADS1115 (4-channel, I2C, 16-bit, 860 SPS)

### Signal Fusion
- Fenix HRV → time-domain features (RMSSD, NN50 ratio)
- EEG → frequency-domain features (theta/alpha power ratio)
- Fusion: Multi-modal classifier (RSD marker = high HRV variability + elevated theta)

---

## References & Suppliers
- **Addison Électronique**: addison.ca (Montreal, QC)
- **DigiKey Canada**: digikey.ca
- **Amazon.ca**: Fast shipping to PEI
- **NE555 Datasheet**: ti.com/lit/ds/symlink/ne555.pdf
EOF

cat > "$MASTER_DIR/PROJECTS.md" << 'EOF'
---
name: Active Projects & Context
updated: $(date +%Y-%m-%d)
---

## Current Priorities (Q2 2026)

### Hardware AI Business Path (6-month target)
- **Goal**: $10K–$50K industrial monitoring revenue
- **Vehicle**: TOLS oscillator network + RSD bio-AI integration
- **Status**: Hardware validation phase (breadboard prototype needs lab testing)
- **Next Milestone**: Validate ~5 Hz oscillation on breadboard, document frequency measurements

### Echo Rising (Grounded Legion Book 2)
- **Locked State**: 24-chapter outline, Act 1 prose (Ch 1-7)
- **Current Phase**: Outline-to-prose expansion (Ch 8+)
- **Workflow**: GROK outline planning → Claude prose expansion (when fed)
- **Voice Lock**: Gritty metaphysical fantasy, subtext-heavy, avoid exposition
- **Next Session**: Ch 8 prose, apply thematic pacing (prevent repetitive theme hammering)

### Veteran Transition Research
- **Thesis**: Subtractive cognition under constraint (military cognitive styles misread as deficits)
- **Status**: Research complete, 14-book reading list, competitive landscape analyzed
- **Frameworks**: GMAIE v1.1 (PhD-defensible), multiple frameworks converted to Claude Skills
- **Next**: Prose expansion, chapter planning

### Pattern Zoo Documentation Cleanup
- **Issue**: TradingView moderator warnings (visual clutter, documentation gaps)
- **Status**: Needs compliance audit
- **Action**: Document Pine Script logic, reduce clutter on 1-minute charts

## Completed Papers & Releases

### Sentient Skin Ghost Key (Published)
- **Published**: Zenodo
- **Content**: Theoretical 100 MHz dermal resonator using living tissue as dielectric
- **Status**: Received without institutional backing

### Living Computational Bit (Published)
- **Status**: Early download traction
- **Next Paper**: Operationalizing IPE metric (in planning)

## Support Systems

### The Operator's Deck (Live)
- **URL**: clovelearni0.io
- **Type**: PWA (Progressive Web App)
- **Tools**: 30+ single-file HTML/JS apps (DBT/ACT/CBT influenced)
- **Tech**: Offline-first, localStorage-backed, no login required
- **Aesthetics**: Dark/tactical, red accents, Bebas Neue + DM Mono
- **Status**: Live, maintenance phase

### Garmin Fenix 7X Connect IQ App
- **Feature**: Property boundary navigation (60-acre waterfront, Roseville PEI)
- **Tech**: MGRS coordinates, haptic alerts
- **Status**: In development, testing phase

---

## Cross-Project Links
- TOLS → RSD bio-AI (sensor integration)
- Echo Rising → Veteran book (metaphysical themes, subtractive cognition)
- Pattern Zoo → TRA optimization (trading system refinement)
EOF

cat > "$MASTER_DIR/CONTEXT.md" << 'EOF'
---
name: Personal & Business Context
updated: $(date +%Y-%m-%d)
---

## Identity & Background

### Personal
- **Name**: Ryan Bardyla
- **Location**: Prince Edward Island, Canada
- **Military**: Former CSOR Signal Technician (Canadian Armed Forces)
- **Trade**: Licensed 309A Electrician
- **Martial Arts**: 2nd degree Taekwondo black belt
- **Endurance**: Two-time Ironman finisher

### Household
- **Dogs**: 4 (two French Bulldogs, one Mastiff, one Weimaraner)
- **Property**: 60-acre waterfront development, Roseville PEI

### Coding Journey
- **Start**: January 2025 (zero experience)
- **Languages**: Rust, TypeScript, Python, systems-level
- **Learning Method**: AI-assisted vibe-coding
- **Achievements**: 9 languages, 40+ frameworks, 12 major systems (custom JIT compiler 1,270× faster than LLVM, lock-free memory system 201× speedup)

## Creative Output

### Published Works
- **"Stubborn Bastard"**: Manual/craft-focused (visceral, direct voice)
- **"The Rent-Free Ghost"**: Fiction
- **"The Synthesis Universalis"**: Comparative mysticism/consciousness studies (Amazon)
- **"Tae Kwon Flow"**: Martial arts curriculum (adults 40+, 15-rank, 20–30 year progression)

### Research Areas
- Bioelectric waveforms (7.83 Hz Schumann resonance)
- Hebbian learning validation (95% GloVe performance on SimLex-999)
- Trinary neural networks (energy efficiency, real-world 2–6× savings)
- Continual learning (EWC vs. replay methods)
- DNC-based trading (Fenrisa system, 192 backtests/sec, <50ms latency)

## Professional Frameworks

### Governance
- **VAL Framework v1.0**: VIBE + APEX + LEVELS
- **APEX Orchestrator v4.4**: Research governance, falsification mandates
- **KLEON Creative Layer v1.1**: Steal → Copy → Transform → Ship
- **META-SCIENCE Investigation v1.1**: Investigate dismissed claims
- **GMAIE Meta-Cognitive Layer v1.1**: PhD-defensible cognitive framework

### Communication
- **Primary Voice**: Full-stack developer (code-first, practical, implementation details)
- **Hardware Voice**: Senior hardware engineer (tactical, direct, volts/amps/ohms)
- **Fiction Voice**: Gritty metaphysical (subtext, no exposition)
- **Comms Style**: Military (Clear, Concise, Correct)

## Community & Reach
- **X Handle**: @clovelearni0
- **Content Frequency**: Regular posts on AI, hardware, writing
- **Audience**: Technical builders, veterans, creators

## Health & Recovery
- **Program**: VAC disability benefits navigation, PCVRS rehab program
- **Focus**: RSD (Rejection Sensitive Dysphoria) research and detection
- **Preference**: Concise, direct language in official documentation

---

## Knowledge Interests
- Occultism & dismissed science (frequency-based healing, Burr/Levin bioelectric research)
- Game engine development (Twisted Metal-style vehicle combat, Metroidvania platformer)
- Investigative journalism (X creator competition content)
- DNA data storage simulation
- RF energy harvesting
EOF

# Initialize git repo with all files
cd "$MASTER_DIR"
git add -A
git commit -m "init: Layer 2.5 Claude Master system bootstrap" 2>/dev/null || true

echo "✅ Created: $MASTER_DIR"
echo "✅ Git initialized (version control active)"
echo ""
echo "Next steps:"
echo "1. Update the .md files with your current project state"
echo "2. Source the shell aliases: source ~/.claude-master-aliases.sh"
echo "3. Run weekly backup: claude-backup"
echo "4. Update memory mid-session: claude-update-memory 'new discovery'"
