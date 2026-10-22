import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// Vercel runs this after the website build. Capacitor/iOS builds do not load
// the web advertising script.
const output = fileURLToPath(new URL("../dist/spa/", import.meta.url));
const publisher = "ca-pub-9870060842199692";
const scriptUrl = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${publisher}`;

function htmlFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const filename = path.join(directory, entry.name);
    return entry.isDirectory() ? htmlFiles(filename) : entry.name.endsWith(".html") ? [filename] : [];
  });
}

const files = htmlFiles(output);
if (!files.length) throw new Error("No built HTML pages found for AdSense setup");

for (const filename of files) {
  const html = readFileSync(filename, "utf8");
  const head = html.match(/<head\b[^>]*>([\s\S]*?)<\/head>/i)?.[1];
  if (head === undefined) throw new Error(`Missing HTML head: ${filename}`);
  const otherPublisher = head.match(/ca-pub-\d+/g)?.some((value) => value !== publisher);
  if (otherPublisher) throw new Error(`Conflicting AdSense publisher: ${filename}`);
  const tags = [];
  if (!head.includes('name="google-adsense-account"')) {
    tags.push(`<meta name="google-adsense-account" content="${publisher}" />`);
  }
  if (!head.includes(scriptUrl)) {
    tags.push(`<script async src="${scriptUrl}" crossorigin="anonymous"></script>`);
  }
  if (tags.length) writeFileSync(filename, html.replace(/<\/head>/i, `${tags.join("\n")}\n</head>`));
}

console.log(`AdSense publisher configured in ${files.length} website HTML pages`);
