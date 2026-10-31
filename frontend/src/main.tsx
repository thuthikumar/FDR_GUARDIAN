import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { configureFavicon } from './config/favicon'
import './styles.css'

configureFavicon()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
