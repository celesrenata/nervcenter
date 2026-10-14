import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { ThemeProvider, applyThemeToDocument, readStoredTheme } from './theme/ThemeContext'

// Apply the stored theme before React paints so there is no theme flash;
// the ThemeProvider effect keeps the attribute in sync afterwards.
applyThemeToDocument(readStoredTheme())

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </React.StrictMode>,
)