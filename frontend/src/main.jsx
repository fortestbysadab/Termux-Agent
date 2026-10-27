import { Component } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

/**
 * A render error must never leave the user staring at a blank page: the whole
 * console is one tree, so we catch, explain, and offer a reload (the backend
 * and the session data are untouched).
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Console crashed', error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="crash">
        <div className="crash-card">
          <h1>The console hit an unexpected error</h1>
          <p>
            Your sessions, files and connectors are safe — they live in the agent&apos;s database,
            not in this page.
          </p>
          <pre>{String(this.state.error?.message || this.state.error)}</pre>
          <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
            Reload the console
          </button>
        </div>
      </div>
    );
  }
}

createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
