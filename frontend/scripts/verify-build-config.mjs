import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from '@tailwindcss/node';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(root, relativePath), 'utf8'));
}

function loadLucideIconMap() {
  const entry = path.join(root, 'node_modules/lucide-react/dist/esm/lucide-react.js');
  const source = fs.readFileSync(entry, 'utf8');
  const exportsPattern = /export\s+\{([^}]+)\}\s+from\s+'\.\/icons\/([^']+\.js)'/g;
  const iconMap = new Map();

  for (const match of source.matchAll(exportsPattern)) {
    for (const item of match[1].split(',')) {
      const exportedName = item.trim().match(/^default\s+as\s+([A-Za-z_$][\w$]*)$/)?.[1];
      if (exportedName) {
        iconMap.set(exportedName, match[2]);
      }
    }
  }

  return iconMap;
}

function findSourceFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) return findSourceFiles(fullPath);
    if (/\.[cm]?[jt]sx?$/.test(entry.name)) return [fullPath];
    return [];
  });
}

async function verifyCssPipeline() {
  const cssPath = path.join(root, 'src/index.css');
  const dependencies = [];
  const result = await compile(fs.readFileSync(cssPath, 'utf8'), {
    base: root,
    from: cssPath,
    onDependency: (dependency) => dependencies.push(dependency),
    shouldRewriteUrls: true,
  });

  const required = [
    'tailwindcss/index.css',
    'tw-animate-css/dist/tw-animate.css',
    'shadcn/dist/tailwind.css',
  ];

  for (const expected of required) {
    if (!dependencies.some((dependency) => dependency.endsWith(expected))) {
      throw new Error(`CSS dependency did not resolve: ${expected}`);
    }
  }

  const probeCss = result.build([
    'bg-background',
    'text-foreground',
    'animate-in',
    'fade-in-0',
    'zoom-in-95',
    'data-open:animate-in',
  ]);

  if (!probeCss.includes('.animate-in') || !probeCss.includes('.bg-background')) {
    throw new Error('Tailwind probe build did not emit expected utilities');
  }

  return dependencies.length;
}

function verifyLucideImports() {
  const iconMap = loadLucideIconMap();
  const sourceFiles = findSourceFiles(path.join(root, 'src'));
  const importPattern = /import\s+(type\s+)?\{([^}]*)\}\s+from\s+['"]lucide-react['"];?/g;
  const missing = [];
  let checked = 0;

  for (const file of sourceFiles) {
    const source = fs.readFileSync(file, 'utf8');
    for (const match of source.matchAll(importPattern)) {
      if (match[1]) continue;
      for (const rawSpecifier of match[2].split(',')) {
        const specifier = rawSpecifier.trim();
        if (!specifier || specifier.startsWith('type ')) continue;
        const importedName = specifier.split(/\s+as\s+/)[0].trim();
        checked += 1;
        if (!iconMap.has(importedName)) {
          missing.push(`${path.relative(root, file)}: ${importedName}`);
        }
      }
    }
  }

  if (missing.length > 0) {
    throw new Error(`Lucide direct-import map is missing:\n${missing.join('\n')}`);
  }

  return checked;
}

function verifyAliases() {
  const componentsConfig = readJson('components.json');
  const tsconfig = readJson('tsconfig.json');

  if (componentsConfig.aliases.components !== '@/components') {
    throw new Error('components.json alias mismatch for components');
  }

  if (tsconfig.compilerOptions?.paths?.['@/*']?.[0] !== './src/*') {
    throw new Error('tsconfig @/* alias mismatch');
  }
}

verifyAliases();
const cssDependencyCount = await verifyCssPipeline();
const lucideImportCount = verifyLucideImports();

console.log(`Build diagnostics passed: ${cssDependencyCount} CSS dependencies, ${lucideImportCount} Lucide imports, aliases valid.`);
