import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const packageManifest = fileURLToPath(
  new URL('../node_modules/@onesignal/capacitor-plugin/Package.swift', import.meta.url),
);
const manifest = readFileSync(packageManifest, 'utf8');
const ios14 = 'platforms: [.iOS(.v14)]';
const ios15 = 'platforms: [.iOS(.v15)]';

if (manifest.includes(ios15)) {
  console.log('OneSignal Capacitor Swift package already targets iOS 15.');
} else if (manifest.includes(ios14)) {
  writeFileSync(packageManifest, manifest.replace(ios14, ios15));
  console.log('Aligned OneSignal Capacitor Swift package with the app iOS 15 target.');
} else {
  throw new Error('Unexpected OneSignal Swift package platform; inspect before building.');
}
