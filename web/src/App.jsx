import { useEffect, useState } from "react";
import Portfolio from "./views/Portfolio.jsx";
import Risk from "./views/Risk.jsx";
import Policy from "./views/Policy.jsx";
import Loans from "./views/Loans.jsx";
import Monitoring from "./views/Monitoring.jsx";

const VIEWS = [
  { key: "portfolio", label: "Portfolio review", navLabel: "Portfolio", component: Portfolio },
  { key: "risk", label: "Risk review", navLabel: "Risk", component: Risk },
  { key: "policy", label: "Policy decision", navLabel: "Policy", component: Policy },
  { key: "loans", label: "Loan review", navLabel: "Loans", component: Loans },
  { key: "monitoring", label: "Control monitoring", navLabel: "Monitoring", component: Monitoring },
];

const keyFromHash = () => {
  const key = window.location.hash.replace("#/", "").replace("#", "");
  return VIEWS.some((view) => view.key === key) ? key : "portfolio";
};

export default function App() {
  const [active, setActive] = useState(keyFromHash);

  // The hash is the source of truth, so a deep link, a reload and the browser's
  // back button all land in the same place.
  useEffect(() => {
    const sync = () => setActive(keyFromHash());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  const navigate = (key) => {
    window.location.hash = `#/${key}`;
    setActive(key);
    window.scrollTo({ top: 0 });
  };

  const view = VIEWS.find((candidate) => candidate.key === active) ?? VIEWS[0];
  const View = view.component;

  return (
    <div className="app">
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <div className="register-head">
          <div className="brand">
            <p className="brand-kicker">Credit policy workpaper / VL-2018-10</p>
            <p className="brand-name">Vehicle Loan Strategy</p>
          </div>
          <dl className="review-register" aria-label="Review register">
            <div><dt>Evidence</dt><dd>Aug-Oct 2018</dd></div>
            <div><dt>Owner</dt><dd>Credit policy</dd></div>
            <div><dt>Status</dt><dd><span className="status-mark" aria-hidden="true" />Review required</dd></div>
            <div><dt>Use</dt><dd>Portfolio + records</dd></div>
          </dl>
        </div>
        <nav aria-label="Views">
          <ul>
            {VIEWS.map((candidate) => (
              <li key={candidate.key}>
                <button
                  type="button"
                  aria-current={candidate.key === active ? "page" : undefined}
                  onClick={() => navigate(candidate.key)}
                >
                  {candidate.navLabel}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main id="main">
        <p className="page-reference">Review schedule / {String(VIEWS.findIndex((item) => item.key === active) + 1).padStart(2, "0")}</p>
        <h1>{view.label}</h1>
        <View onNavigate={navigate} />
      </main>

      <footer className="footer">
        <p><strong>Use boundary:</strong> full-data portfolio analysis with bounded, pseudonymous record review. No applicant approval, decline, or pricing decision.</p>
        <p className="footer-source">233,154 authorized source records. Evidence reproduces <code>artifacts/strategy_summary.json</code>.</p>
      </footer>
    </div>
  );
}
