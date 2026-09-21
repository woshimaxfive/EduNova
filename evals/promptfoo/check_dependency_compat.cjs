// Check the optional native/ZIP security overrides against project assets offline.
const assert = require('node:assert/strict');
const { readFileSync, realpathSync } = require('node:fs');
const { createRequire } = require('node:module');
const path = require('node:path');

const fromPromptfoo = createRequire(realpathSync(path.join(__dirname, 'node_modules/promptfoo/package.json')));
const fromTransformers = createRequire(fromPromptfoo.resolve('@huggingface/transformers'));
const fromOnnx = createRequire(fromTransformers.resolve('onnxruntime-node'));
const AdmZip = fromOnnx('adm-zip');
const sharp = fromTransformers('sharp');
const { parse } = fromPromptfoo('csv-parse/sync');

async function main() {
  const config = readFileSync(path.join(__dirname, 'promptfooconfig.yaml'));
  const rows = parse(readFileSync(path.join(__dirname, 'dependency-cases.csv')), { columns: true });
  assert.equal(rows.length, 2);
  assert.equal(rows[1].__expected, 'contains:证据');
  const hostile = parse('__proto__,__proto__\na,b\n', { columns: true, group_columns_by_name: true });
  assert.equal(Object.getPrototypeOf(hostile[0]), Object.prototype);
  assert.equal(Object.hasOwn(hostile[0], '__proto__'), true);
  const icon = readFileSync(path.join(__dirname, '../../frontend/public/favicon.svg'));
  const archive = new AdmZip();
  archive.addFile('evals/promptfooconfig.yaml', config);
  archive.addFile('assets/favicon.svg', icon);
  const restored = new AdmZip(archive.toBuffer());
  assert.deepEqual(restored.readFile('evals/promptfooconfig.yaml'), config);
  assert.deepEqual(restored.readFile('assets/favicon.svg'), icon);
  const image = await sharp(icon).resize(32, 32).png().toBuffer();
  const metadata = await sharp(image).metadata();
  assert.equal(metadata.width, 32);
  assert.equal(metadata.height, 32);
  assert.equal(metadata.format, 'png');
  console.log('Project CSV/prototype guard, YAML/SVG ZIP roundtrip and native image resize passed.');
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });
