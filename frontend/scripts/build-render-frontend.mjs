import { cp, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputDir = path.join(frontendRoot, 'dist');
const configuredApiUrl = process.env.SATQUERY_API_URL;

if (!configuredApiUrl) {
  throw new Error('SATQUERY_API_URL must be set to the deployed backend URL.');
}

const normalizedApiUrl = configuredApiUrl.startsWith('http')
  ? configuredApiUrl
  : `https://${configuredApiUrl}`;
const apiUrl = new URL(normalizedApiUrl);

if (apiUrl.protocol !== 'https:' || apiUrl.pathname !== '/' || apiUrl.search || apiUrl.hash) {
  throw new Error('SATQUERY_API_URL must be an HTTPS origin without a path, query, or fragment.');
}

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });
const entries = await readdir(frontendRoot, { withFileTypes: true });

for (const entry of entries) {
  if (entry.name === 'dist' || entry.name === 'scripts') continue;
  await cp(
    path.join(frontendRoot, entry.name),
    path.join(outputDir, entry.name),
    { recursive: true },
  );
}

const configPath = path.join(outputDir, 'js', 'config.js');
const configSource = await readFile(configPath, 'utf8');
const configPattern = /API_URL:\s*"http:\/\/localhost:8000"/g;
const configMatches = configSource.match(configPattern) || [];

if (configMatches.length !== 1) {
  throw new Error('Expected exactly one local API URL in frontend/js/config.js.');
}

await writeFile(
  configPath,
  configSource.replace(configPattern, `API_URL: ${JSON.stringify(apiUrl.origin)}`),
  'utf8',
);
