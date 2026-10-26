'use strict';

// Standalone experiment. No backend imports, network or database access.
// Never outputs credentials, digests, payload contents, file paths or exceptions.
const fs = require('node:fs');
const crypto = require('node:crypto');
const { TextDecoder } = require('node:util');

function main() {
  const args = process.argv.slice(2);
  const diagnostic = args.length === 1 && args[0] === '--json-diagnostic';
  if (args.length !== 0 && !diagnostic) {
    process.stderr.write('NOT RUN: unsupported arguments.\n');
    return 2;
  }

  const token = process.env.KIWIFY_WEBHOOK_TOKEN;
  const signature = process.env.KIWIFY_WEBHOOK_SIGNATURE;
  const rawBody = process.env.KIWIFY_WEBHOOK_RAW_BODY;
  const bodyFile = process.env.KIWIFY_WEBHOOK_RAW_BODY_FILE;
  const hasRawBody = rawBody !== undefined;
  if (!token || !signature || (!hasRawBody && !bodyFile)) {
    process.stderr.write('NOT RUN: required local data unavailable.\n');
    return 2;
  }

  let body;
  try {
    // An existing variable takes precedence even when its value is empty.
    // Preserve whitespace/newlines; do not parse JSON or interpret escapes here.
    body = hasRawBody ? Buffer.from(rawBody, 'utf8') : fs.readFileSync(bodyFile);
  } catch {
    process.stderr.write('NOT RUN: cannot read body input.\n');
    return 2;
  }

  // Default mode hashes UTF-8 environment content or exact fallback file bytes.
  // Diagnostic mode is explicitly selected and never runs as a fallback.
  if (diagnostic) {
    try {
      const text = new TextDecoder('utf-8', { fatal: true }).decode(body);
      body = Buffer.from(JSON.stringify(JSON.parse(text)), 'utf8');
    } catch {
      process.stderr.write('NOT RUN: diagnostic input is not valid UTF-8 JSON.\n');
      return 2;
    }
  }

  const digest = crypto.createHmac('sha1', token).update(body).digest();
  const validHex = /^[0-9a-fA-F]{40}$/.test(signature);
  // A same-size dummy buffer also permits constant-time comparison for malformed
  // signatures. Reject invalid format independently; never pad/truncate input.
  const observed = validHex ? Buffer.from(signature, 'hex') : Buffer.alloc(digest.length);
  const equal = crypto.timingSafeEqual(digest, observed);
  const matches = validHex && equal;

  process.stdout.write(JSON.stringify({
    result: matches ? 'MATCH' : 'NO MATCH',
    calculated_digest_hex_length: digest.length * 2,
    received_signature_length: signature.length,
    representation: diagnostic ? 'JSON reserialized: JSON.stringify' : 'raw body',
  }) + '\n');
  return matches ? 0 : 1;
}

try {
  process.exitCode = main();
} catch {
  process.stderr.write('NOT RUN: experiment failed.\n');
  process.exitCode = 2;
}
