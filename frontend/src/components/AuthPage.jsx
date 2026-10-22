import React, { useState } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../api';

const PASSWORD_MIN_LENGTH = 12;

/**
 * Render the account sign-up and login screens.
 */
export default function AuthPage({ page, search, onNavigate, onAuthenticated }) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState(
    page === 'login' && new URLSearchParams(search).get('signup') === 'success'
      ? 'Account created successfully. Please login with your new account.'
      : ''
  );
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const isSignup = page === 'signup';

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Enter a valid email address.');
      return;
    }
    if (isSignup && !fullName.trim()) {
      setError('Enter your full name.');
      return;
    }
    if (!password) {
      setError('Enter your password.');
      return;
    }
    if (isSignup && password.length < PASSWORD_MIN_LENGTH) {
      setError(`Password must be at least ${PASSWORD_MIN_LENGTH} characters.`);
      return;
    }
    if (isSignup && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      if (isSignup) {
        await axios.post(`${API_BASE_URL}/api/auth/signup`, {
          full_name: fullName,
          email,
          password,
          confirm_password: confirmPassword,
        });
        setMessage('Account created successfully. Please login with your new account.');
        onNavigate('/login?signup=success');
      } else {
        const response = await axios.post(`${API_BASE_URL}/api/auth/login`, { email, password });
        onAuthenticated(response.data.user);
      }
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      const validationMessage = Array.isArray(detail)
        ? detail[0]?.msg
        : detail;
      setError(validationMessage || 'Unable to complete your request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-heading">
        <a className="auth-brand" href="/" onClick={(event) => { event.preventDefault(); onNavigate('/'); }}>
          <span className="auth-brand-mark" aria-hidden="true">R</span>
          <span>Credit Risk Analyzer</span>
        </a>
        <h1 id="auth-heading">{isSignup ? 'Create your account' : 'Welcome back'}</h1>
        <p className="auth-description">
          {isSignup
            ? 'Create an account to access your credit risk workspace.'
            : 'Sign in to continue to your credit risk workspace.'}
        </p>

        {message && <div className="auth-message" role="status">{message}</div>}
        {error && <div className="auth-error" role="alert">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {isSignup && (
            <label>
              Full Name
              <input
                type="text"
                name="fullName"
                autoComplete="name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                maxLength={120}
                required
              />
            </label>
          )}

          <label>
            Email
            <input
              type="email"
              name="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              maxLength={254}
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              name="password"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={isSignup ? PASSWORD_MIN_LENGTH : 1}
              maxLength={1024}
              required
            />
            {isSignup && <span className="auth-field-hint">Use at least {PASSWORD_MIN_LENGTH} characters.</span>}
          </label>

          {isSignup && (
            <label>
              Confirm Password
              <input
                type="password"
                name="confirmPassword"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={PASSWORD_MIN_LENGTH}
                maxLength={1024}
                required
              />
            </label>
          )}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? 'Please wait…' : isSignup ? 'Create Account' : 'Login'}
          </button>
        </form>

        <p className="auth-footer">
          {isSignup
            ? <>Already have an account? <a href="/login" onClick={(event) => { event.preventDefault(); onNavigate('/login'); }}>Login</a></>
            : <>New to Credit Risk Analyzer? <a href="/signup" onClick={(event) => { event.preventDefault(); onNavigate('/signup'); }}>Create an account</a></>}
        </p>
      </section>
    </main>
  );
}
