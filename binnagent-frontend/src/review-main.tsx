import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { ToastProvider } from './components/ui/ToastProvider'
import { ReadingWorkshopReviewApp } from './review/ReadingWorkshopReviewApp'
import { installReadingReviewApiMock } from './review/readingReviewApiMock'

installReadingReviewApiMock()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <ReadingWorkshopReviewApp />
    </ToastProvider>
  </StrictMode>,
)
