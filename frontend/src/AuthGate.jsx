import { useEffect, useState } from 'react';
import { ArrowRight, ChartNoAxesCombined, FileSearch, LoaderCircle, LockKeyhole, MessageSquare, ShieldCheck } from 'lucide-react';
import App from './App';
import { authConfigurationError, clearAuthentication, initializeAuth, oktaAuth } from './auth';
import './AuthGate.css';

export default function AuthGate() {
  const [authState, setAuthState] = useState(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(authConfigurationError);

  useEffect(() => {
    if (!oktaAuth) return;
    let active = true;
    const update = (state) => { if (active) setAuthState(state); };
    const reportError = () => {
      if (active) setError('Your sign-in session could not be updated. Please sign in again.');
    };
    oktaAuth.authStateManager.subscribe(update);
    oktaAuth.tokenManager.on('error', reportError);
    initializeAuth().then(() => {
      if (active) {
        update(oktaAuth.authStateManager.getAuthState());
        setReady(true);
      }
    }).catch(() => {
      if (active) {
        setError('Okta sign-in could not be completed. Please retry or contact your administrator.');
        setReady(true);
      }
    });
    return () => {
      active = false;
      oktaAuth.authStateManager.unsubscribe(update);
      oktaAuth.tokenManager.off('error', reportError);
    };
  }, []);

  async function signIn() {
    setBusy(true);
    setError('');
    try {
      await oktaAuth.signInWithRedirect({ originalUri: '/dashboard' });
    } catch {
      setError('Unable to open Okta sign-in. Check the configuration and try again.');
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError('');
    try {
      const tokens = oktaAuth.tokenManager.getTokensSync();
      await clearAuthentication();
      await oktaAuth.signOut({
        ...tokens,
        postLogoutRedirectUri: window.location.origin,
        clearTokensBeforeRedirect: true,
        revokeAccessToken: true,
        revokeRefreshToken: true,
      });
    } catch {
      setError('Local access was cleared, but Okta logout failed. Close this tab and sign out of Okta.');
    } finally {
      await clearAuthentication();
      setBusy(false);
    }
  }

  if (ready && !busy && !error && authState?.isAuthenticated) {
    const identity = `${authState.idToken.claims.iss}|${authState.idToken.claims.sub}`;
    return <App key={identity} user={authState.idToken.claims} identity={identity} onSignOut={signOut} />;
  }

  return (
    <main className="auth-page">
      <div className="auth-background" aria-hidden="true">
        <span className="auth-aurora auth-aurora-mint" />
        <span className="auth-aurora auth-aurora-blue" />
        <span className="auth-aurora auth-aurora-gold" />
      </div>
      <section className="auth-card" aria-labelledby="sign-in-title" aria-busy={busy || (!ready && !error)}>
        <div className="auth-brand">
          <span className="auth-brand-icon"><ShieldCheck size={26} aria-hidden="true" /></span>
          <span>Credit Risk Analyzer<span className="auth-brand-caption">YOUR ANALYSIS WORKSPACE</span></span>
        </div>
        <p className="auth-eyebrow">WELCOME BACK</p>
        <h1 id="sign-in-title">Sign in to your workspace</h1>
        <ul className="auth-features" aria-label="Workspace features">
          <li><FileSearch size={19} aria-hidden="true" /><span>Document<br />analysis</span></li>
          <li><ChartNoAxesCombined size={19} aria-hidden="true" /><span>Risk<br />insights</span></li>
          <li><MessageSquare size={19} aria-hidden="true" /><span>AI<br />assistant</span></li>
        </ul>
        {error && <p className="auth-error" role="alert">{error}</p>}
        {((!ready && !error) || busy) && (
          <p className="auth-status" role="status">{busy ? 'Connecting to Okta...' : 'Checking your sign-in session...'}</p>
        )}
        <button className="auth-sign-in" type="button" onClick={signIn} disabled={busy || !oktaAuth || !ready}>
          <span>{busy ? 'Please wait...' : 'Sign in with Okta'}</span>
          {busy
            ? <LoaderCircle className="auth-spinner" size={20} aria-hidden="true" />
            : <ArrowRight className="auth-button-arrow" size={20} aria-hidden="true" />}
        </button>
        <p className="auth-security-note"><LockKeyhole size={15} aria-hidden="true" />Organization-managed access</p>
      </section>
      <p className="auth-page-note">One workspace. Clearer decisions.</p>
    </main>
  );
}
