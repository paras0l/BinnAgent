import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(() => {
  const appTarget = process.env.VITE_APP_TARGET === 'dev-console'
    ? 'dev-console'
    : process.env.VITE_APP_TARGET === 'review'
      ? 'review'
      : 'learner'
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
      port: appTarget === 'dev-console' ? 5176 : appTarget === 'review' ? 5177 : 5175,
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

function appEntryPlugin(appTarget: 'learner' | 'dev-console' | 'review') {
  return {
    name: 'binnagent-app-entry',
    enforce: 'pre' as const,
    transformIndexHtml(html: string) {
      if (appTarget === 'dev-console') {
        return html.replace('BinnAgent - AI 英语学习伙伴', 'BinnAgent Dev Console')
      }
      if (appTarget === 'review') {
        return html.replace('BinnAgent - AI 英语学习伙伴', 'BinnAgent 精读与泛读 · 团队验收')
      }
      return html
    },
  }
}
