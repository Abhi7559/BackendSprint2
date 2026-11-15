'use client';

import { useState, useEffect } from 'react';

export default function HomePage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Auth state
  const [token, setToken] = useState('');
  const [currentUser, setCurrentUser] = useState(null);
  const [authInitialized, setAuthInitialized] = useState(false);

  // Login form state
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // App data state
  const [films, setFilms] = useState([]);
  const [selectedFilmId, setSelectedFilmId] = useState('');
  const [rating, setRating] = useState(5);
  const [reviewBody, setReviewBody] = useState('');
  const [statusMessage, setStatusMessage] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Helper to decode JWT payload without external library
  const decodeJwtPayload = (jwtToken) => {
    try {
      const parts = jwtToken.split('.');
      if (parts.length !== 3) return null;
      const base64Url = parts[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch {
      return null;
    }
  };

  // Restore stored session on mount
  useEffect(() => {
    try {
      const savedToken = localStorage.getItem('access_token');
      if (savedToken) {
        const payload = decodeJwtPayload(savedToken);
        const nowSec = Math.floor(Date.now() / 1000);
        if (payload && payload.exp && payload.exp > nowSec) {
          setToken(savedToken);
          setCurrentUser({
            username: payload.username || 'User',
            role: (payload.role || 'viewer').toLowerCase(),
          });
        } else {
          localStorage.removeItem('access_token');
        }
      }
    } catch (e) {
      console.error('Session restore error:', e);
    } finally {
      setAuthInitialized(true);
    }
  }, []);

  // Login handler
  const handleLogin = async (e, customCredentials = null) => {
    if (e && e.preventDefault) e.preventDefault();
    setLoginError('');
    setIsLoggingIn(true);

    const creds = customCredentials || {
      username: loginUsername.trim(),
      password: loginPassword,
    };

    if (!creds.username || !creds.password) {
      setLoginError('Please enter both username and password.');
      setIsLoggingIn(false);
      return;
    }

    try {
      const res = await fetch(`${apiUrl}/api/v1/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds),
      });

      const data = await res.json();

      if (res.ok && data.access_token) {
        const payload = decodeJwtPayload(data.access_token);
        const userObj = {
          username: payload?.username || creds.username,
          role: (payload?.role || 'viewer').toLowerCase(),
        };
        setToken(data.access_token);
        setCurrentUser(userObj);
        localStorage.setItem('access_token', data.access_token);
        setLoginUsername('');
        setLoginPassword('');
      } else {
        const errorText =
          (typeof data.detail === 'string' ? data.detail : null) ||
          (typeof data.detail?.detail === 'string' ? data.detail.detail : null) ||
          (typeof data.message === 'string' ? data.message : null) ||
          'Invalid username or password.';
        setLoginError(errorText);
      }
    } catch (err) {
      setLoginError(`Network / Connection error: ${err.message}`);
    } finally {
      setIsLoggingIn(false);
    }
  };

  // Logout handler
  const handleLogout = async () => {
    if (token) {
      try {
        await fetch(`${apiUrl}/api/v1/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
        });
      } catch (err) {
        console.error('Logout error:', err);
      }
    }
    setToken('');
    setCurrentUser(null);
    localStorage.removeItem('access_token');
    setFilms([]);
    setStatusMessage(null);
    setIsModalOpen(false);
  };

  // Quick fill preset roles
  const fillPreset = (role) => {
    if (role === 'admin') {
      setLoginUsername('Abhishek1');
      setLoginPassword('AdminPassword123!');
    } else if (role === 'critic') {
      setLoginUsername('critic_user');
      setLoginPassword('CriticPassword123!');
    } else if (role === 'viewer') {
      setLoginUsername('viewer_user');
      setLoginPassword('ViewerPassword123!');
    }
    setLoginError('');
  };

  // Fetch films when logged in
  useEffect(() => {
    if (!token) return;
    async function loadFilms() {
      try {
        const res = await fetch(`${apiUrl}/api/v1/films`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (res.ok) {
          const data = await res.json();
          setFilms(data.items || []);
          if (data.items?.length > 0) {
            setSelectedFilmId(data.items[0].id);
          }
        }
      } catch (err) {
        console.error('Failed to load films:', err);
      }
    }
    loadFilms();
  }, [apiUrl, token]);

  // Review submission handler
  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (!selectedFilmId) return;

    setIsSubmitting(true);
    setStatusMessage(null);

    try {
      const response = await fetch(`${apiUrl}/api/v1/films/${selectedFilmId}/reviews`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          rating: Number(rating),
          body: reviewBody,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        const selectedFilm = films.find((f) => f.id === selectedFilmId);
        const filmTitle = selectedFilm ? selectedFilm.title : 'Film';
        setStatusMessage({
          type: 'success',
          text: `Review for "${filmTitle}" submitted successfully! Ratings and catalogue are now updated.`,
        });
        setReviewBody('');

        // Refresh the catalogue iframe
        setTimeout(() => {
          const iframe = document.querySelector('iframe');
          if (iframe) iframe.src = iframe.src;
        }, 1000);
      } else {
        let errorText = 'Unable to submit review. Please try again.';
        if (Array.isArray(data.detail)) {
          // Pydantic validation error list
          const firstErr = data.detail[0];
          if (firstErr?.loc?.includes('body') && firstErr?.type?.includes('short')) {
            errorText = 'Review body is too short. Please write at least 50 characters.';
          } else {
            errorText = firstErr?.msg || 'Please check your inputs and try again.';
          }
        } else if (typeof data.detail === 'string') {
          errorText = data.detail;
        } else if (typeof data.detail?.detail === 'string') {
          errorText = data.detail.detail;
        } else if (typeof data.message === 'string') {
          errorText = data.message;
        }

        if (data.type === 'DuplicateReviewError' || (typeof errorText === 'string' && errorText.toLowerCase().includes('already reviewed'))) {
          const selectedFilm = films.find((f) => f.id === selectedFilmId);
          errorText = selectedFilm
            ? `You have already reviewed "${selectedFilm.title}". Each user can only review a film once.`
            : 'You have already reviewed this film.';
        }

        setStatusMessage({
          type: 'error',
          text: errorText,
        });
      }
    } catch (err) {
      setStatusMessage({
        type: 'error',
        text: `Network connection issue. Please check your connection and try again.`,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Wait until localStorage check completes
  if (!authInitialized) {
    return (
      <main style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0b0f19', color: '#94a3b8' }}>
        <p>Loading application...</p>
      </main>
    );
  }

  // Role Badge Color Mapper
  const getRoleBadgeStyle = (role) => {
    switch (role) {
      case 'admin':
        return { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444', textBg: '#ef4444' };
      case 'critic':
        return { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6', textBg: '#3b82f6' };
      case 'viewer':
      default:
        return { bg: 'rgba(34, 197, 94, 0.15)', border: '#22c55e', textBg: '#22c55e' };
    }
  };

  // -------------------------------------------------------------
  // LOGIN SCREEN (Shown if unauthenticated)
  // -------------------------------------------------------------
  if (!token || !currentUser) {
    return (
      <main
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'radial-gradient(ellipse at top, #1e1b4b 0%, #0b0f19 70%)',
          color: '#f8fafc',
          fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          padding: '1.5rem',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '460px',
            background: 'rgba(19, 28, 46, 0.95)',
            border: '1px solid #334155',
            borderRadius: '1rem',
            padding: '2.25rem',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(12px)',
          }}
        >
          {/* Logo / Header */}
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <div
              style={{
                width: '56px',
                height: '56px',
                margin: '0 auto 1rem auto',
                background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                borderRadius: '1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.8rem',
                boxShadow: '0 8px 20px rgba(99, 102, 241, 0.35)',
              }}
            >
              🎬
            </div>
            <h1 style={{ fontSize: '1.65rem', fontWeight: 800, margin: '0 0 0.5rem 0', letterSpacing: '-0.02em', color: '#f8fafc' }}>
              Film Review Platform
            </h1>
            <p style={{ fontSize: '0.875rem', color: '#94a3b8', margin: 0 }}>
              Sign in with your <strong>Admin</strong>, <strong>Critic</strong>, or <strong>Viewer</strong> account
            </p>
          </div>

          {/* Quick Preset Selector Buttons */}
          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
              Quick Select Role:
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => fillPreset('admin')}
                style={{
                  padding: '0.55rem 0.5rem',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  color: '#fca5a5',
                  borderRadius: '0.5rem',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.25)')}
                onMouseOut={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)')}
              >
                👑 Admin
              </button>
              <button
                type="button"
                onClick={() => fillPreset('critic')}
                style={{
                  padding: '0.55rem 0.5rem',
                  background: 'rgba(59, 130, 246, 0.1)',
                  border: '1px solid rgba(59, 130, 246, 0.4)',
                  color: '#93c5fd',
                  borderRadius: '0.5rem',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = 'rgba(59, 130, 246, 0.25)')}
                onMouseOut={(e) => (e.currentTarget.style.background = 'rgba(59, 130, 246, 0.1)')}
              >
                ✍️ Critic
              </button>
              <button
                type="button"
                onClick={() => fillPreset('viewer')}
                style={{
                  padding: '0.55rem 0.5rem',
                  background: 'rgba(34, 197, 94, 0.1)',
                  border: '1px solid rgba(34, 197, 94, 0.4)',
                  color: '#86efac',
                  borderRadius: '0.5rem',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = 'rgba(34, 197, 94, 0.25)')}
                onMouseOut={(e) => (e.currentTarget.style.background = 'rgba(34, 197, 94, 0.1)')}
              >
                👀 Viewer
              </button>
            </div>
          </div>

          {/* Login Form */}
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', color: '#cbd5e1', marginBottom: '0.4rem', fontWeight: 500 }}>
                Username
              </label>
              <input
                id="login-username"
                type="text"
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                placeholder="e.g. Abhishek1, critic_user, or viewer_user"
                required
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  borderRadius: '0.5rem',
                  background: '#0b0f19',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  outline: 'none',
                  fontSize: '0.9rem',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', color: '#cbd5e1', marginBottom: '0.4rem', fontWeight: 500 }}>
                Password
              </label>
              <input
                id="login-password"
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                placeholder="Enter password"
                required
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  borderRadius: '0.5rem',
                  background: '#0b0f19',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  outline: 'none',
                  fontSize: '0.9rem',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            {/* Error Message */}
            {loginError && (
              <div
                style={{
                  padding: '0.75rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.82rem',
                  background: 'rgba(239, 68, 68, 0.15)',
                  color: '#fca5a5',
                  border: '1px solid #ef4444',
                }}
              >
                {loginError}
              </div>
            )}

            <button
              id="login-submit-btn"
              type="submit"
              disabled={isLoggingIn}
              style={{
                marginTop: '0.5rem',
                width: '100%',
                padding: '0.8rem',
                background: isLoggingIn ? '#4338ca' : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                color: '#ffffff',
                border: 'none',
                borderRadius: '0.5rem',
                fontSize: '0.95rem',
                fontWeight: 600,
                cursor: isLoggingIn ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 14px rgba(79, 70, 229, 0.4)',
                transition: 'all 0.15s ease',
              }}
            >
              {isLoggingIn ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Quick hint table */}
          <div
            style={{
              marginTop: '1.75rem',
              padding: '0.85rem',
              background: 'rgba(15, 23, 42, 0.6)',
              borderRadius: '0.5rem',
              border: '1px solid #1e293b',
              fontSize: '0.75rem',
              color: '#94a3b8',
            }}
          >
            <div style={{ fontWeight: 600, color: '#cbd5e1', marginBottom: '0.35rem' }}>Demo Accounts:</div>
            <div style={{ padding: '0.2rem 0' }}>
              <span>👑 Admin: <code>Abhishek1</code></span>
            </div>
            <div style={{ padding: '0.2rem 0' }}>
              <span>✍️ Critic: <code>critic_user</code></span>
            </div>
            <div style={{ padding: '0.2rem 0' }}>
              <span>👀 Viewer: <code>viewer_user</code></span>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // -------------------------------------------------------------
  // AUTHENTICATED PORTAL VIEW
  // -------------------------------------------------------------
  const roleStyle = getRoleBadgeStyle(currentUser.role);
  const canCreateReview = currentUser.role === 'admin' || currentUser.role === 'critic';

  return (
    <main style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#0b0f19', color: '#f1f5f9', fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
      <header
        style={{
          padding: '1rem 2rem',
          background: '#0f172a',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          position: 'sticky',
          top: 0,
          zIndex: 40,
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.25rem', margin: 0, fontWeight: 700, color: '#f8fafc' }}>
            Staff Film Review Portal <span style={{ fontSize: '0.85rem', color: '#818cf8', fontWeight: 500 }}>(Next.js Client)</span>
          </h1>
          <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
            Live CORS Cross-Origin Requests, RBAC Enforcement & Background Recalculation
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          {/* User & Role Badge */}
          <div
            id="user-badge"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: roleStyle.bg,
              border: `1px solid ${roleStyle.border}`,
              padding: '0.35rem 0.75rem',
              borderRadius: '9999px',
              fontSize: '0.8rem',
            }}
          >
            <span style={{ fontSize: '0.85rem' }}>
              {currentUser.role === 'admin' ? '👑' : currentUser.role === 'critic' ? '✍️' : '👀'}
            </span>
            <span style={{ color: '#f8fafc', fontWeight: 600 }}>{currentUser.username}</span>
            <span
              style={{
                textTransform: 'uppercase',
                fontSize: '0.65rem',
                fontWeight: 700,
                letterSpacing: '0.05em',
                background: roleStyle.textBg,
                color: '#ffffff',
                padding: '0.1rem 0.45rem',
                borderRadius: '9999px',
              }}
            >
              {currentUser.role}
            </span>
          </div>

          {/* Create Review Action (Visible only to Admin & Critic, or shows tooltip if Viewer) */}
          {canCreateReview ? (
            <button
              id="create-review-btn"
              onClick={() => {
                setStatusMessage(null);
                setIsModalOpen(true);
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: '#4f46e5',
                color: '#ffffff',
                padding: '0.65rem 1.25rem',
                borderRadius: '0.5rem',
                fontWeight: 600,
                fontSize: '0.9rem',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 4px 14px rgba(79, 70, 229, 0.4)',
                transition: 'all 0.2s ease',
              }}
              onMouseOver={(e) => (e.currentTarget.style.background = '#4338ca')}
              onMouseOut={(e) => (e.currentTarget.style.background = '#4f46e5')}
            >
              <span style={{ fontSize: '1.1rem', lineHeight: 1 }}>+</span> Create Review
            </button>
          ) : (
            <div
              style={{
                fontSize: '0.78rem',
                color: '#94a3b8',
                background: 'rgba(30, 41, 59, 0.7)',
                padding: '0.45rem 0.75rem',
                borderRadius: '0.5rem',
                border: '1px dashed #334155',
              }}
              title="Viewer accounts have read-only access (reviews restricted to Admins and Critics)"
            >
              Read-Only Mode (Viewer)
            </div>
          )}

          {/* Logout Button */}
          <button
            id="logout-btn"
            type="button"
            onClick={handleLogout}
            style={{
              background: '#1e293b',
              color: '#cbd5e1',
              border: '1px solid #334155',
              padding: '0.55rem 0.9rem',
              borderRadius: '0.5rem',
              fontSize: '0.8rem',
              cursor: 'pointer',
              fontWeight: 500,
              transition: 'all 0.15s ease',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
              e.currentTarget.style.borderColor = '#ef4444';
              e.currentTarget.style.color = '#fca5a5';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = '#1e293b';
              e.currentTarget.style.borderColor = '#334155';
              e.currentTarget.style.color = '#cbd5e1';
            }}
            title="Log out of session"
          >
            Log Out
          </button>
        </div>
      </header>

      {/* MAIN VIEW: FULL-WIDTH FILM CATALOGUE */}
      <div style={{ flex: 1, padding: '1.25rem', display: 'flex', flexDirection: 'column' }}>
        <section
          style={{
            flex: 1,
            background: '#131c2e',
            border: '1px solid #1e293b',
            borderRadius: '0.75rem',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <iframe
            src={`http://localhost:8000/ui/films`}
            title="Live HTMX Film Catalogue"
            style={{
              width: '100%',
              height: '100%',
              minHeight: '780px',
              border: 'none',
              flex: 1,
            }}
          />
        </section>
      </div>

      {/* POPUP MODAL FOR SUBMITTING FILM REVIEW */}
      {isModalOpen && canCreateReview && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsModalOpen(false);
          }}
        >
          <div
            style={{
              background: '#131c2e',
              border: '1px solid #334155',
              borderRadius: '1rem',
              width: '100%',
              maxWidth: '520px',
              padding: '1.75rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
              position: 'relative',
              animation: 'fadeIn 0.2s ease-out',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
              <div>
                <h2 style={{ fontSize: '1.3rem', margin: 0, fontWeight: 700, color: '#f8fafc' }}>
                  Submit a Film Review
                </h2>
                <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0.3rem 0 0 0' }}>
                  Posting review as <strong>{currentUser.username}</strong> ({currentUser.role})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  fontSize: '1.5rem',
                  lineHeight: 1,
                  cursor: 'pointer',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '0.25rem',
                }}
                title="Close modal"
              >
                &times;
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleSubmitReview} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
              {/* Film Selector */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '0.4rem', fontWeight: 500 }}>
                  Select Film
                </label>
                <select
                  id="film-selector"
                  value={selectedFilmId}
                  onChange={(e) => setSelectedFilmId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.7rem',
                    borderRadius: '0.5rem',
                    background: '#0b0f19',
                    border: '1px solid #334155',
                    color: '#f8fafc',
                    outline: 'none',
                    fontSize: '0.9rem',
                  }}
                >
                  {films.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.title} ({f.release_year}) - {f.genre}
                    </option>
                  ))}
                </select>
              </div>

              {/* Rating Input */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '0.4rem', fontWeight: 500 }}>
                  Rating (1 - 5 Stars)
                </label>
                <input
                  id="rating-input"
                  type="number"
                  min="1"
                  max="5"
                  value={rating}
                  onChange={(e) => setRating(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '0.7rem',
                    borderRadius: '0.5rem',
                    background: '#0b0f19',
                    border: '1px solid #334155',
                    color: '#f8fafc',
                    boxSizing: 'border-box',
                    fontSize: '0.9rem',
                  }}
                />
              </div>

              {/* Review Body */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                  <label htmlFor="review-body" style={{ fontSize: '0.85rem', color: '#cbd5e1', fontWeight: 500 }}>
                    Review Feedback
                  </label>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: reviewBody.length >= 50 ? '#4ade80' : reviewBody.length > 0 ? '#f59e0b' : '#94a3b8',
                    }}
                  >
                    {reviewBody.length} / 50 characters minimum
                  </span>
                </div>
                <textarea
                  id="review-body"
                  rows={4}
                  value={reviewBody}
                  onChange={(e) => setReviewBody(e.target.value)}
                  placeholder="Share your thoughts about the film (minimum 50 characters)..."
                  required
                  style={{
                    width: '100%',
                    padding: '0.7rem',
                    borderRadius: '0.5rem',
                    background: '#0b0f19',
                    border: '1px solid #334155',
                    color: '#f8fafc',
                    boxSizing: 'border-box',
                    resize: 'vertical',
                    fontSize: '0.9rem',
                    fontFamily: 'inherit',
                  }}
                />
              </div>

              {/* Status Message */}
              {statusMessage && (
                <div
                  style={{
                    padding: '0.75rem',
                    borderRadius: '0.5rem',
                    fontSize: '0.85rem',
                    background: statusMessage.type === 'success' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    color: statusMessage.type === 'success' ? '#4ade80' : '#f87171',
                    border: `1px solid ${statusMessage.type === 'success' ? '#22c55e' : '#ef4444'}`,
                  }}
                >
                  {statusMessage.text}
                </div>
              )}

              {/* Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  style={{
                    padding: '0.65rem 1.25rem',
                    background: '#1e293b',
                    color: '#cbd5e1',
                    border: '1px solid #334155',
                    borderRadius: '0.5rem',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !token}
                  style={{
                    background: '#4f46e5',
                    color: '#fff',
                    padding: '0.65rem 1.5rem',
                    border: 'none',
                    borderRadius: '0.5rem',
                    fontWeight: 600,
                    cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  }}
                >
                  {isSubmitting ? 'Submitting...' : 'Post Review'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
