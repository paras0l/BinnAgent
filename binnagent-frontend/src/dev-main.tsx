import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import DevConsoleApp from './dev-console/App'
import { ToastProvider } from './components/ui/ToastProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <DevConsoleApp />
    </ToastProvider>
  </StrictMode>,
)
