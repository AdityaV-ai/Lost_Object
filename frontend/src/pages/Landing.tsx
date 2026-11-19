import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icon";
import { Logo, ThemeButton } from "../components/Layout";

const SIGNALS = [
  ["image", "Photo ↔ photo", "A CLIP vision model compares the object type, shape and colour profile of both photos."],
  ["search", "Words ↔ photo", "When you have no photo, your written description is compared with the finder's photo, so text-only reports still match."],
  ["edit", "Text ↔ text", "Names, categories, colours, brands and features are compared with TF-IDF and a synonym list (“flask” ≈ “bottle”)."],
  ["pin", "Location", "The distance between the two places, decaying smoothly over a few hundred metres."],
] as const;

const FEATURES = [
  ["image", "Photo-first found reports", "A finder only needs a photo, a category and a name to report an item."],
  ["shield", "Private by default", "There is no public list of found items. A candidate is shown only to the owner of the matching lost report."],
  ["check", "Staff-verified handover", "Claims go to staff with the owner's proof. Nothing is released on a score alone."],
  ["box", "Custody tracking", "Every found item records where it is: left in place, with the finder, or at a drop point."],
  ["bell", "Notifications", "Owners are told about a new candidate as soon as it is reported. Finders hear when a deposit is confirmed."],
  ["download", "Analytics and exports", "Staff see trends and the recovery rate, and can export CSV reports."],
] as const;

const FAQ = [
  ["Does a high score mean the item is mine?", "No. The score says how much two reports look alike. Staff verify ownership before anything is handed over."],
  ["Can the finder see my name?", "No. Finders never see owner details. Staff see both sides only to run the recovery."],
  ["What if I have no photo of my lost item?", "Describe it. The description is compared with finders' photos, with the text of their reports and with the location."],
  ["Is the location required?", "No. When both reports have coordinates the distance contributes to the ranking; otherwise that signal is simply left out."],
  ["Do I get emails?", "Not yet. Notifications appear in the app (bell icon and Notifications tab)."],
];

export default function Landing() {
  const { user } = useAuth();
  return (
    <>
      <header className="nav-public"><div className="in">
        <Logo />
        <nav><a href="#how">How it works</a><a href="#features">Features</a><a href="#privacy">Privacy</a><a href="#faq">FAQ</a></nav>
        <ThemeButton />
        {user ? <Link className="btn btn-primary" to="/dashboard">Open app</Link> : (<>
          <Link className="btn btn-ghost" to="/login">Log in</Link><Link className="btn btn-primary" to="/register">Sign up</Link></>)}
      </div></header>
      <div className="land">
        <section className="hero">
          <span className="chip green"><span className="dot" />Lost &amp; found for campuses</span>
          <h1>Lost something? <em>Get it back.</em></h1>
          <p>FindBack compares every lost report with every found item — photo, description and place — and tells the owner privately when there is a likely candidate. Staff verify the claim before anything changes hands.</p>
          <div className="row" style={{ marginTop: 26 }}>
            <Link className="btn btn-primary btn-lg" to="/report-lost">Report a lost item →</Link>
            <Link className="btn btn-lg" to="/report-found">I found something</Link>
          </div>
        </section>
        <section className="section" id="how">
          <span className="chip blue">How it works</span><h2>Four signals, one ranked list</h2>
          <p className="muted">Whatever information exists is used. Missing information is left out, never guessed.</p>
          <div className="cards3">{SIGNALS.map(([i, t, d]) => (
            <div className="card" key={t}><div className="fico"><Icon name={i} /></div><h3>{t}</h3><p>{d}</p></div>))}</div>
        </section>
        <section className="section" id="features">
          <span className="chip blue">Features</span><h2>Built around the recovery</h2>
          <div className="cards3">{FEATURES.map(([i, t, d]) => (
            <div className="card" key={t}><div className="fico"><Icon name={i} /></div><h3>{t}</h3><p>{d}</p></div>))}</div>
        </section>
        <section className="section" id="privacy">
          <span className="chip green">Privacy</span><h2>Private by design</h2>
          <p className="muted" style={{ maxWidth: 720 }}>A lost-and-found board is an open invitation to false claims. FindBack keeps found items out of sight and puts a person in the loop: scores indicate relevance, not ownership, and finders and owners never see each other's details.</p>
        </section>
        <section className="section faq" id="faq">
          <span className="chip blue">FAQ</span><h2>Questions</h2>
          {FAQ.map(([q, a]) => <details key={q}><summary>{q}</summary><p>{a}</p></details>)}
        </section>
        <footer className="foot">© FindBack · Institutional recovery platform</footer>
      </div>
    </>
  );
}
