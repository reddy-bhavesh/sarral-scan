import * as msal from "@azure/msal-browser";

/**
 * MSAL Configuration for Microsoft SSO
 * 
 * To enable Microsoft SSO:
 * 1. Register app in Azure Portal
 * 2. Set environment variables in .env:
 *    - VITE_MICROSOFT_CLIENT_ID
 *    - VITE_MICROSOFT_AUTHORITY (optional)
 *    - VITE_MICROSOFT_REDIRECT_URI (optional)
 */

export const msalConfig: msal.Configuration = {
  auth: {
    clientId: import.meta.env.VITE_MICROSOFT_CLIENT_ID || "",
    authority: import.meta.env.VITE_MICROSOFT_AUTHORITY || "https://login.microsoftonline.com/common",
    redirectUri: import.meta.env.VITE_MICROSOFT_REDIRECT_URI || window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage", // Store tokens in session storage
    storeAuthStateInCookie: false,    // Set to true for IE11/Edge support
  },
};

export const loginRequest: msal.PopupRequest = {
  scopes: ["openid", "profile", "email"], // Minimum scopes for authentication
};
