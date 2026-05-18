import path from 'path';
import fs from 'fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';

const enablePwa = process.env.OPENJARVIS_ENABLE_PWA === '1';

function lucideDirectImports() {
  let iconMap: Map<string, string> | undefined;

  const getIconMap = () => {
    if (iconMap) return iconMap;

    const lucideEntry = path.resolve(__dirname, 'node_modules/lucide-react/dist/esm/lucide-react.js');
    const source = fs.readFileSync(lucideEntry, 'utf8');
    const exportsPattern = /export\s+\{([^}]+)\}\s+from\s+'\.\/icons\/([^']+\.js)'/g;
    iconMap = new Map();

    for (const match of source.matchAll(exportsPattern)) {
      const exportList = match[1];
      const iconFile = match[2];

      for (const item of exportList.split(',')) {
        const exportedName = item.trim().match(/^default\s+as\s+([A-Za-z_$][\w$]*)$/)?.[1];
        if (exportedName) {
          iconMap.set(exportedName, `lucide-react/dist/esm/icons/${iconFile}`);
        }
      }
    }

    return iconMap;
  };

  return {
    name: 'openjarvis-lucide-direct-imports',
    enforce: 'pre' as const,
    transform(code: string, id: string) {
      if (!/\.[cm]?[jt]sx?$/.test(id) || id.includes('/node_modules/') || !code.includes('lucide-react')) {
        return null;
      }

      const importsPattern = /import\s+(type\s+)?\{([^}]*)\}\s+from\s+(['"])lucide-react\3;?/g;
      let changed = false;
      const map = getIconMap();

      const nextCode = code.replace(importsPattern, (statement, typeOnly, specifiers) => {
        if (typeOnly) return statement;

        const typeSpecifiers: string[] = [];
        const unresolvedSpecifiers: string[] = [];
        const directImports: string[] = [];

        for (const rawSpecifier of specifiers.split(',')) {
          const specifier = rawSpecifier.trim();
          if (!specifier) continue;

          if (specifier.startsWith('type ')) {
            typeSpecifiers.push(specifier.replace(/^type\s+/, ''));
            continue;
          }

          const [importedName, localName = importedName] = specifier.split(/\s+as\s+/).map((part) => part.trim());
          const moduleId = map.get(importedName);

          if (!moduleId) {
            unresolvedSpecifiers.push(specifier);
            continue;
          }

          directImports.push(`import ${localName} from '${moduleId}';`);
        }

        if (directImports.length === 0) return statement;

        changed = true;
        return [
          typeSpecifiers.length > 0 ? `import type { ${typeSpecifiers.join(', ')} } from 'lucide-react';` : '',
          unresolvedSpecifiers.length > 0 ? `import { ${unresolvedSpecifiers.join(', ')} } from 'lucide-react';` : '',
          ...directImports,
        ].filter(Boolean).join('\n');
      });

      return changed ? { code: nextCode, map: null } : null;
    },
  };
}

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  plugins: [
    lucideDirectImports(),
    react(),
    tailwindcss(),
    enablePwa && VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Siri Layer',
        short_name: 'Siri',
        description: 'On-device AI assistant',
        theme_color: '#161618',
        background_color: '#161618',
        display: 'standalone',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
        navigateFallbackDenylist: [/^\/v1\//, /^\/health/, /^\/dashboard/],
      },
    }),
  ].filter(Boolean),
  build: {
    outDir: '../src/openjarvis/server/static',
    emptyOutDir: true,
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
          markdown: ['react-markdown', 'rehype-highlight', 'remark-gfm'],
          charts: ['recharts'],
          router: ['react-router'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/v1': process.env.VITE_API_URL || 'http://localhost:8000',
      '/health': process.env.VITE_API_URL || 'http://localhost:8000',
    },
  },
});
