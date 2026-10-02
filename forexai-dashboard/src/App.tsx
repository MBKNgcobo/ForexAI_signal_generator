import {
  useState,
} from "react";

import "./App.css";

import Dashboard from "./pages/Dashboard";
import Login from "./components/auth/Login";
import SignalHistory from "./components/signals/SignalHistory";

import {
  getAuthSession,
} from "./auth/authStorage";

import type {
  AuthSession,
} from "./auth/authStorage";

type AppView =
  | "dashboard"
  | "history";

function App() {
  const [
    session,
    setSession,
  ] = useState<AuthSession | null>(
    getAuthSession()
  );

  const [
    view,
    setView,
  ] = useState<AppView>(
    "dashboard"
  );

  function handleLogin(
    newSession: AuthSession
  ) {
    setSession(newSession);
  }

  if (!session) {
    return (
      <div className="app app--auth">
        <div className="auth-shell">
          <div className="auth-brand">
            <span className="brand-mark">
              F
            </span>

            <div>
              <strong>
                ForexAI
              </strong>

              <span>
                Multi-Agent Market Intelligence
              </span>
            </div>
          </div>

          <Login
            onLogin={handleLogin}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="app">

      {/* ======================================================
          SIDEBAR
          ====================================================== */}

      <aside className="sidebar">

        <div className="sidebar-brand">

          <div className="brand-mark">
            F
          </div>

          <div>
            <strong>
              ForexAI
            </strong>

            <span>
              Market Intelligence
            </span>
          </div>

        </div>


        <nav className="sidebar-nav">

          <span className="nav-label">
            Workspace
          </span>

          <button
            type="button"
            className={
              view === "dashboard"
                ? "nav-button nav-button--active"
                : "nav-button"
            }
            onClick={() =>
              setView("dashboard")
            }
          >
            <span className="nav-icon">
              ◫
            </span>

            Dashboard
          </button>


          <button
            type="button"
            className={
              view === "history"
                ? "nav-button nav-button--active"
                : "nav-button"
            }
            onClick={() =>
              setView("history")
            }
          >
            <span className="nav-icon">
              ≡
            </span>

            Signal History
          </button>

        </nav>


        <div className="sidebar-footer">

          <span className="nav-label">
            System
          </span>

          <div className="system-status">
            <span className="status-dot" />

            <span>
              AI services online
            </span>
          </div>

        </div>

      </aside>


      {/* ======================================================
          MAIN APPLICATION
          ====================================================== */}

      <div className="app-main">

        <header className="topbar">

          <div>
            <span className="topbar-eyebrow">
              FOREX ANALYTICS
            </span>

            <h1>
              {view === "dashboard"
                ? "Market Dashboard"
                : "Signal History"}
            </h1>
          </div>


          <div className="topbar-status">

            <span className="status-dot" />

            <span>
              Live system
            </span>

          </div>

        </header>


        <main className="page-content">

          {view === "dashboard" ? (
            <Dashboard />
          ) : (
            <SignalHistory />
          )}

        </main>

      </div>

    </div>
  );
}

export default App;