import fs from 'fs';
import path from 'path';

const ROOT = process.cwd();

const FORBIDDEN_TERMS = [
    'bias detector',
    'truth score',
    'credibility score',
    'manipulative intent',
    'best outlet',
    'worst outlet',
    'ranking',
    'trusted source',
    'untrusted source'
];

const SIGNALS_DIR = path.join(ROOT, 'src/lib/signals');
const INTERPRETATION_DIR = path.join(ROOT, 'src/lib/interpretation');

function getFiles(dir: string): string[] {
    if (!fs.existsSync(dir)) {
        return [];
    }

    const entries = fs.readdirSync(dir, { withFileTypes: true });

    return entries.flatMap((entry) => {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            return getFiles(fullPath);
        }

        return fullPath;
    });
}

function fail(message: string): never {
    console.error(`❌ Constitutional Violation: ${message}`);
    process.exit(1);
}

function validateForbiddenTerms(files: string[]) {
    for (const file of files) {
        const content = fs.readFileSync(file, 'utf8').toLowerCase();

        for (const term of FORBIDDEN_TERMS) {
            if (content.includes(term)) {
                fail(`${term} found in ${file}`);
            }
        }
    }
}

function validateOneWayDependency(signalFiles: string[]) {
    for (const file of signalFiles) {
        const content = fs.readFileSync(file, 'utf8');

        if (content.includes('interpretation/')) {
            fail(`signals/ may not import interpretation/: ${file}`);
        }
    }
}

function validateKnownLimits(interpFiles: string[]) {
    const hasKnownLimits = interpFiles.some((file) => {
        const content = fs.readFileSync(file, 'utf8');
        return content.includes('KnownLimits');
    });

    if (!hasKnownLimits) {
        fail('Known Limits integration missing');
    }
}

const signalFiles = getFiles(SIGNALS_DIR);
const interpretationFiles = getFiles(INTERPRETATION_DIR);

validateForbiddenTerms([...signalFiles, ...interpretationFiles]);
validateOneWayDependency(signalFiles);
validateKnownLimits(interpretationFiles);

console.log('✅ Constitution compliance checks passed');
