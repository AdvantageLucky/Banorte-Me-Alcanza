import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { COLORS } from './constants/colors.js'
import './styles/index.css'

// Inyección en CSS
Object.entries(COLORS).forEach(([key, value]) => {
  const cssKey = `--color-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
  document.documentElement.style.setProperty(cssKey, value);
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
