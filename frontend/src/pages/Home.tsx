import { Link } from "react-router-dom";

const steps = [
  ["01", "＋", "Submit a report", "Share the details you remember, with a photo if you have one."],
  ["02", "⌕", "AI looks for matches", "Available image, text and location signals help rank potential matches."],
  ["03", "♡", "Review privately", "Review candidates linked to your own lost-item report."],
  ["04", "✓", "Staff verify & reunite", "Authorised staff review ownership and coordinate handover."],
];

export default function Home() {
  return (
    <main>
      <section className="hero wrap">
        <div className="hero-copy">
          <span className="eyebrow">A smarter way to reunite belongings</span>
          <h1>Lost something?<br /><em>Let's help you find it.</em></h1>
          <p className="lead">Report a lost or found item. Our matching system compares available images, descriptions and locations to surface potential matches for review.</p>
          <div className="hero-actions">
            <Link className="btn btn-primary btn-lg" to="/report-lost">I lost an item <span>→</span></Link>
            <Link className="btn btn-light btn-lg" to="/report-found">I found an item <span>→</span></Link>
          </div>
          <div className="trust-line"><span>✓ Private matching</span><span>✓ Staff-supported recovery</span></div>
        </div>
        <div className="hero-art">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" />
          <div className="floating-card card-one"><span className="mini-icon">⌕</span><div><b>Smart matching</b><small>Image · Text · Location</small></div></div>
          <div className="object-illustration"><div className="bag-handle" /><div className="bag-body"><span className="bag-dot" /><span className="bag-label">FOUND</span></div></div>
          <div className="floating-card card-two"><span className="check-icon">✓</span><div><b>Verified recovery</b><small>With authorised staff</small></div></div>
        </div>
      </section>
      <section className="how-section" id="how"><div className="wrap">
        <div className="section-heading"><span className="eyebrow">Simple, secure, thoughtful</span><h2>From lost to found in four steps</h2>
          <p>Your information stays within authorised workflows. Found items are never displayed in a public catalogue.</p></div>
        <div className="steps">{steps.map(([n, icon, t, d]) => (
          <article className="step" key={n}><span>{n}</span><div className="step-icon">{icon}</div><h3>{t}</h3><p>{d}</p></article>))}</div>
      </div></section>
      <section className="privacy-band wrap"><div className="privacy-symbol">⌑</div>
        <div><h2>Your safety comes first</h2><p>AI scores indicate relevance, not proof of ownership. Finder and owner contact details are not shared. Ownership and recovery are handled by authorised staff.</p></div>
        <Link to="/register" className="text-link">Get started →</Link></section>
    </main>
  );
}
