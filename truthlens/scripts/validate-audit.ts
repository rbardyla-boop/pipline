import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const Ajv2020 = require('ajv/dist/2020.js').default;

const ajv = new Ajv2020({ strict: false });

const schemaPath = path.join(process.cwd(), 'truthlens-audit-schema-v1.json');
const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
const validate = ajv.compile(schema);

const sampleAudit = {
    protocol: {
        constitution_version: '1.0',
        audit_schema_version: '1.0',
        signals_registry_version: '1.0'
    },
    article: {
        url: 'https://example.com',
        title: 'Sample Article',
        timestamp: new Date().toISOString()
    },
    signals: [],
    interpretation: {
        layer1: 'Test'
    },
    known_limits: [],
    exported_at: new Date().toISOString()
};

const valid = validate(sampleAudit);

if (!valid) {
    console.error(validate.errors);
    process.exit(1);
}

console.log('✅ Audit schema validation passed');
