import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { MsalProvider } from "@azure/msal-react";
import * as msal from "@azure/msal-browser";
import { msalConfig } from "./config/msalConfig";

// Initialize MSAL instance
const msalInstance = new msal.PublicClientApplication(msalConfig);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MsalProvider instance={msalInstance}>
      <App />
    </MsalProvider>
  </StrictMode>,
)
