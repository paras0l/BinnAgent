import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(() => {
  const appTarget = process.env.VITE_APP_TARGET === 'dev-console' ? 'dev-console' : 'learner'
  const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [appEntryPlugin(appTarget), react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    define: {
      'import.meta.env.VITE_APP_TARGET': JSON.stringify(appTarget),
    },
    server: {
      port: appTarget === 'dev-console' ? 5176 : 5175,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: appTarget === 'dev-console' ? 'dist-dev-console' : 'dist',
      emptyOutDir: true,
    },
  }
})

function appEntryPlugin(appTarget: 'learner' | 'dev-console') {
  return {
    name: 'binnagent-app-entry',
    enforce: 'pre' as const,
    transformIndexHtml(html: string) {
      if (appTarget === 'dev-console') {
        return html.replace('BinnAgent - AI 英语学习伙伴', 'BinnAgent Dev Console')
      }
      return html
    },
  }
}
