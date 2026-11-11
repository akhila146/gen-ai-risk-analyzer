import { OktaAuth } from '@okta/okta-auth-js';

const issuer = import.meta.env.VITE_OKTA_ISSUER?.trim().replace(/\/+$/, '');
const clientId = import.meta.env.VITE_OKTA_CLIENT_ID?.trim();
const scope = import.meta.env.VITE_OKTA_SCOPE?.trim();
export const authConfigurationError = !issuer || !clientId || !scope
  || !/^https:\/\/[^/?#]+\/oauth2\/[^/?#]+$/.test(issuer)
  || issuer.includes('your-org') || clientId === 'your-spa-client-id' || /\s/.test(scope)
  ? 'Configure VITE_OKTA_ISSUER, VITE_OKTA_CLIENT_ID, and VITE_OKTA_SCOPE, then restart the frontend.'
  : '';

let sessionEnded = false;

export const oktaAuth = authConfigurationError ? null : new OktaAuth({
  issuer,
  clientId,
  redirectUri: `${window.location.origin}/login/callback`,
  scopes: ['openid', 'profile', 'email', 'offline_access', scope],
  pkce: true,
  storageManager: {
    token: { storageType: 'sessionStorage', storageTypes: [] },
    transaction: { storageType: 'sessionStorage', storageTypes: [] },
  },
  tokenManager: { autoRenew: true, autoRemove: false },
  services: { autoRenew: false, autoRemove: false, syncStorage: false },
  transformAuthState: async (_client, state) => ({
    ...state,
    isAuthenticated: state.isAuthenticated && !sessionEnded,
  }),
  restoreOriginalUri: async () => {
    window.history.replaceState(null, '', '/dashboard');
  },
});

let initialization;

export function initializeAuth() {
  if (!initialization) {
    initialization = (async () => {
      if (!oktaAuth) throw new Error(authConfigurationError);
      if (oktaAuth.isLoginRedirect()) {
        await oktaAuth.handleRedirect();
      } else if (window.location.pathname === '/login/callback') {
        throw new Error('The sign-in callback is missing its authorization response.');
      }
      const { accessToken, refreshToken } = oktaAuth.tokenManager.getTokensSync();
      if (accessToken && !refreshToken) {
        await clearAuthentication();
        throw new Error('Sign in again to authorize refresh-token access.');
      }
      await oktaAuth.start();
      await oktaAuth.authStateManager.updateAuthState();
    })();
  }
  return initialization;
}

export async function getAccessToken() {
  try {
    if (!oktaAuth || sessionEnded) throw new Error('Sign-in is required.');
    const { accessToken, refreshToken } = oktaAuth.tokenManager.getTokensSync();
    if ((!accessToken || oktaAuth.tokenManager.hasExpired(accessToken)) && !refreshToken) {
      throw new Error('No refresh token is available.');
    }
    const token = await oktaAuth.getOrRenewAccessToken();
    if (!token || sessionEnded) throw new Error('The sign-in session has ended.');
    return token;
  } catch {
    await clearAuthentication();
    throw new Error('Your session could not be renewed. Sign in with Okta again.');
  }
}

export async function clearAuthentication() {
  sessionEnded = true;
  oktaAuth?.tokenManager.clear();
  await oktaAuth?.authStateManager.updateAuthState();
}
