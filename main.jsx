// src/main.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// ---------------------------------------------------------------------------
// Error Boundary — catches any render-time crash and shows a message instead
// of the blank white screen that would otherwise appear.
// ---------------------------------------------------------------------------
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary] Caught render error:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: '#0f1117',
          color: '#e2e8f0',
          fontFamily: 'DM Mono, monospace',
          padding: '2rem',
          textAlign: 'center',
          gap: '1rem',
        }}>
          <div style={{ fontSize: '2rem' }}>⚠</div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
            Something went wrong
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.875rem', maxWidth: '480px', margin: 0 }}>
            The platform encountered an unexpected error on startup. Open the browser
            console for details, then refresh the page to try again.
          </p>
          <pre style={{
            background: '#1e2232',
            border: '1px solid #334155',
            borderRadius: '6px',
            padding: '1rem',
            fontSize: '0.75rem',
            color: '#f87171',
            maxWidth: '640px',
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
            {this.state.error?.message ?? 'Unknown error'}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '0.5rem',
              padding: '0.5rem 1.5rem',
              background: '#6366f1',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontFamily: 'inherit',
            }}
          >
            Reload page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
