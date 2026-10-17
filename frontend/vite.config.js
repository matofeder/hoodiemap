import { defineConfig } from 'vite';

// Pretty paths for the extra pages; production does the same in src/api.py.
const PAGES = [
  [/^\/p\/[^/]+\/?$/, '/presentation.html'],
  [/^\/(novy|upravit\/[^/]+)\/?$/, '/editor.html'],
  [/^\/import\/?$/, '/import.html'],
  [/^\/prever\/?$/, '/prever.html'],
  [/^\/admin\/?$/, '/admin.html'],
];

const pageRoutes = {
  name: 'hoodiemap-pages',
  configureServer(server) {
    server.middlewares.use((req, _res, next) => {
      const [path, query = ''] = req.url.split('?');
      const hit = PAGES.find(([re]) => re.test(path));
      if (hit) req.url = hit[1] + (query ? `?${query}` : '');
      next();
    });
  },
};

export default defineConfig({
  plugins: [pageRoutes],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        main: 'index.html',
        presentation: 'presentation.html',
        editor: 'editor.html',
        import: 'import.html',
        prever: 'prever.html',
        admin: 'admin.html',
      },
    },
  },
  test: {
    environment: 'node',
    exclude: ['node_modules', 'dist'],
  },
});
