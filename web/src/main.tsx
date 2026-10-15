import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { ThemeProvider, applyThemeToDocument, readStoredTheme } from './theme/ThemeContext'
import { SettingsProvider, applySettingsToDocument, readStoredSettings } from './theme/SettingsContext'

// Apply the stored theme + global attributes before React paints so there is
// no flash; the providers' effects keep <html> in sync afterwards.
const initialTheme = readStoredTheme()
applyThemeToDocument(initialTheme)
const initialSettings = readStoredSettings()
const initialEffective =
  initialTheme === 'system'
    ? window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light'
      : 'dark'
    : initialTheme
applySettingsToDocument(initialSettings, initialEffective)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <SettingsProvider>
        <App />
      </SettingsProvider>
    </ThemeProvider>
  </React.StrictMode>,
)