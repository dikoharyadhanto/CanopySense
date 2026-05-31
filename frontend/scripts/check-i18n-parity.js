#!/usr/bin/env node
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOCALES_DIR = join(__dirname, '..', 'src', 'i18n', 'locales');
const ID_FILE = join(LOCALES_DIR, 'id.json');
const EN_FILE = join(LOCALES_DIR, 'en.json');

function collectKeys(obj, prefix = '') {
  const keys = [];
  for (const [k, v] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k;
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      keys.push(...collectKeys(v, fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys;
}

function checkEmptyStrings(obj, prefix = '') {
  const empties = [];
  for (const [k, v] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k;
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      empties.push(...checkEmptyStrings(v, fullKey));
    } else if (v === '') {
      empties.push(fullKey);
    }
  }
  return empties;
}

let exitCode = 0;

const id = JSON.parse(readFileSync(ID_FILE, 'utf8'));
const en = JSON.parse(readFileSync(EN_FILE, 'utf8'));

const idKeys = new Set(collectKeys(id));
const enKeys = new Set(collectKeys(en));

const missingInEn = [...idKeys].filter(k => !enKeys.has(k));
const missingInId = [...enKeys].filter(k => !idKeys.has(k));
const emptyInEn = checkEmptyStrings(en);

if (missingInEn.length > 0) {
  console.error(`\nKeys in id.json missing from en.json (${missingInEn.length}):`);
  missingInEn.forEach(k => console.error(`  - ${k}`));
  exitCode = 1;
}

if (missingInId.length > 0) {
  console.error(`\nKeys in en.json missing from id.json (${missingInId.length}):`);
  missingInId.forEach(k => console.error(`  - ${k}`));
  exitCode = 1;
}

if (emptyInEn.length > 0) {
  console.error(`\nEmpty string values in en.json (must be "TODO") (${emptyInEn.length}):`);
  emptyInEn.forEach(k => console.error(`  - ${k}`));
  exitCode = 1;
}

if (exitCode === 0) {
  console.log(`✓ i18n parity OK — ${idKeys.size} keys, id.json ↔ en.json in sync, no empty strings in en.json`);
} else {
  console.error('\ni18n parity check FAILED');
}

process.exit(exitCode);
