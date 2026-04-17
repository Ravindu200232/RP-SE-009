import { AiOutlineShoppingCart, AiOutlineLogin } from "react-icons/ai";
import { HiMenu, HiX } from "react-icons/hi";
import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";

/* ─────────────────────────── styles ─────────────────────────── */
const HeaderStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    /* ROOT */
    .fh { font-family:'Outfit',sans-serif; position:fixed; top:0; left:0; right:0;
      z-index:1000; transition:background .35s,box-shadow .35s,height .35s; }

    .fh.fh-clear { background:transparent; box-shadow:none; height:88px; }
    .fh.fh-solid  { background:#fff; height:72px;
      box-shadow:0 1px 0 #eeebe3, 0 6px 28px rgba(0,0,0,.06); }

    .fh-inner { max-width:1300px; margin:0 auto; height:100%;
      display:flex; align-items:center; justify-content:space-between; padding:0 36px; }

    /* LOGO */
    .fh-logo { display:flex; align-items:center; gap:9px; text-decoration:none; }
    .fh-logo img { height:38px; width:auto; object-fit:contain; transition:opacity .2s; }
    .fh-logo:hover img { opacity:.78; }
    .fh-logotype { font-family:'Cormorant Garamond',serif; font-size:1.65rem;
      font-weight:600; letter-spacing:.02em; line-height:1; transition:color .3s; }
    .fh.fh-clear .fh-logotype { color:#fff; }
    .fh.fh-solid  .fh-logotype { color:#111; }
    .fh-logotype em { font-style:italic; color:#F59E0B; }

    /* DESKTOP NAV */
    .fh-nav { display:flex; align-items:center; gap:34px; }
    .fh-nl { position:relative; font-size:.82rem; font-weight:500; letter-spacing:.09em;
      text-transform:uppercase; text-decoration:none; padding-bottom:3px; transition:color .2s; }
    .fh-nl::after { content:''; position:absolute; bottom:0; left:0;
      width:0; height:1.5px; background:#F59E0B; transition:width .28s ease; }
    .fh-nl:hover::after, .fh-nl.is-active::after { width:100%; }
    .fh.fh-clear .fh-nl { color:rgba(255,255,255,.82); }
    .fh.fh-clear .fh-nl:hover { color:#fff; }
    .fh.fh-solid  .fh-nl { color:#555; }
    .fh.fh-solid  .fh-nl:hover { color:#111; }
    .fh-nl.is-active { color:#F59E0B !important; }

    /* SEPARATOR */
    .fh-sep { width:1px; height:18px; transition:background .35s; }
    .fh.fh-clear .fh-sep { background:rgba(255,255,255,.22); }
    .fh.fh-solid  .fh-sep { background:#e5e1d8; }

    /* ACTIONS */
    .fh-actions { display:flex; align-items:center; gap:18px; }

    /* ICON BTN */
    .fh-icon-btn { display:flex; align-items:center; justify-content:center;
      width:40px; height:40px; border-radius:50%; text-decoration:none; cursor:pointer;
      border:none; background:transparent; transition:background .2s; }
    .fh-icon-btn:hover { background:rgba(245,158,11,.12); }
    .fh-icon { font-size:1.35rem; transition:color .2s; }
    .fh.fh-clear .fh-icon { color:rgba(255,255,255,.85); }
    .fh.fh-solid  .fh-icon { color:#444; }
    .fh-icon-btn:hover .fh-icon { color:#F59E0B !important; }

    /* LOGIN PILL */
    .fh-login { display:inline-flex; align-items:center; gap:7px; font-size:.78rem;
      font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      text-decoration:none; padding:9px 22px; border:1.5px solid; transition:background .25s,color .25s,border-color .25s; }
    .fh.fh-clear .fh-login { border-color:rgba(255,255,255,.55); color:#fff; }
    .fh.fh-clear .fh-login:hover { background:#F59E0B; border-color:#F59E0B; color:#111; }
    .fh.fh-solid  .fh-login { border-color:#F59E0B; color:#F59E0B; }
    .fh.fh-solid  .fh-login:hover { background:#F59E0B; color:#111; }

    /* USER CHIP */
    .fh-user { display:flex; align-items:center; gap:10px; text-decoration:none; }
    .fh-user-name { font-size:.85rem; font-weight:500; transition:color .2s; }
    .fh.fh-clear .fh-user-name { color:rgba(255,255,255,.85); }
    .fh.fh-solid  .fh-user-name { color:#333; }
    .fh-avatar { width:38px; height:38px; border-radius:50%; object-fit:cover;
      border:2px solid #F59E0B; transition:transform .2s,box-shadow .2s; }
    .fh-user:hover .fh-avatar { transform:scale(1.08);
      box-shadow:0 0 0 4px rgba(245,158,11,.22); }

    /* HAMBURGER */
    .fh-burger { display:none !important; }

    /* ── DRAWER ── */
    .fh-overlay { position:fixed; inset:0; background:rgba(0,0,0,.46);
      z-index:998; opacity:0; pointer-events:none; transition:opacity .38s; }
    .fh-overlay.open { opacity:1; pointer-events:all; }

    .fh-drawer { position:fixed; top:0; right:-100%;
      width:min(320px,85vw); height:100dvh; background:#fff; z-index:999;
      display:flex; flex-direction:column;
      box-shadow:-10px 0 48px rgba(0,0,0,.13);
      transition:right .38s cubic-bezier(.25,.46,.45,.94); }
    .fh-drawer.open { right:0; }

    .fh-drawer-head { display:flex; align-items:center; justify-content:space-between;
      padding:24px 28px; border-bottom:1px solid #f0ece4; }
    .fh-drawer-brand { font-family:'Cormorant Garamond',serif; font-size:1.5rem;
      font-weight:600; color:#111; }
    .fh-drawer-brand em { font-style:italic; color:#F59E0B; }
    .fh-close { width:36px; height:36px; display:flex; align-items:center;
      justify-content:center; border-radius:50%; border:1px solid #e5e1d8;
      cursor:pointer; background:transparent; color:#555; font-size:1.05rem;
      transition:background .2s,color .2s; }
    .fh-close:hover { background:#111; color:#fff; border-color:#111; }

    .fh-drawer-nav { display:flex; flex-direction:column; padding:28px 28px; gap:0; flex:1; }
    .fh-dl { font-size:.88rem; font-weight:500; letter-spacing:.08em;
      text-transform:uppercase; color:#555; text-decoration:none;
      padding:15px 0; border-bottom:1px solid #f5f2ec;
      display:flex; align-items:center; justify-content:space-between;
      transition:color .2s,padding-left .2s; }
    .fh-dl::after { content:'→'; color:#F59E0B; opacity:0; transition:opacity .2s; }
    .fh-dl:hover { color:#111; padding-left:5px; }
    .fh-dl:hover::after { opacity:1; }
    .fh-dl.is-active { color:#F59E0B; }

    .fh-drawer-foot { padding:0 28px 0; display:flex; flex-direction:column; gap:10px; }
    .fh-drawer-cta { display:flex; align-items:center; justify-content:center; gap:8px;
      padding:15px; background:#F59E0B; color:#111; font-weight:600;
      font-size:.8rem; letter-spacing:.1em; text-transform:uppercase;
      text-decoration:none; transition:background .2s,color .2s; }
    .fh-drawer-cta:hover { background:#111; color:#F59E0B; }
    .fh-drawer-cart { display:flex; align-items:center; justify-content:space-between;
      padding:14px 0; border-top:1px solid #f0ece4; text-decoration:none;
      color:#555; font-size:.82rem; letter-spacing:.07em; text-transform:uppercase;
      font-weight:500; transition:color .2s; }
    .fh-drawer-cart:hover { color:#F59E0B; }
    .fh-cart-ic { font-size:1.2rem; color:#F59E0B; }

    /* RESPONSIVE */
    @media (max-width:768px) {
      .fh-nav, .fh-sep, .fh-login { display:none !important; }
      .fh-burger { display:flex !important; }
      .fh-inner { padding:0 20px; }
      .fh.fh-clear { height:72px; }
    }
  `}</style>
);

/* ─────────────────────────── data ─────────────────────────── */
const NAV = [
  { to: "/",           label: "Home"        },
  { to: "/contact",    label: "Contact"     },
  { to: "/restaurant", label: "Restaurants" },
  { to: "/item",       label: "Items"       },
];

/* ─────────────────────────── component ─────────────────────── */
export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled]  = useState(false);
  const [user, setUser]           = useState(null);
  const [token]                   = useState(localStorage.getItem("token"));
  const location = useLocation();

  /* scroll detection */
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 36);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  /* user hydration */
  useEffect(() => {
    if (token) {
      const stored = localStorage.getItem("user");
      if (stored) setUser(JSON.parse(stored));
    }
  }, [token]);

  /* close drawer on route change */
  useEffect(() => setMenuOpen(false), [location.pathname]);

  const isActive = (path) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  return (
    <>
      <HeaderStyles />

      {/* ── HEADER BAR ── */}
      <header className={`fh ${scrolled ? "fh-solid" : "fh-clear"}`}>
        <div className="fh-inner">

          {/* Logo */}
          <Link to="/" className="fh-logo">
            <img
              src="/logo.png"
              alt="FoodRush"
              onError={(e) => { e.target.style.display = "none"; }}
            />
            <span className="fh-logotype">
              Food<em>Rush</em>
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="fh-nav">
            {NAV.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={`fh-nl ${isActive(to) ? "is-active" : ""}`}
              >
                {label}
              </Link>
            ))}
          </nav>

          {/* Actions */}
          <div className="fh-actions">
            {/* Cart */}
            <Link to="/cart" className="fh-icon-btn" aria-label="Cart">
              <AiOutlineShoppingCart className="fh-icon" />
            </Link>

            <span className="fh-sep" />

            {/* Auth */}
            {user ? (
              <Link to="/profile" className="fh-user">
                <span className="fh-user-name hidden md:inline">{user.firstName}</span>
                <img
                  src={user.image || "/default-profile.png"}
                  alt="Profile"
                  className="fh-avatar"
                />
              </Link>
            ) : (
              <Link to="/login" className="fh-login">
                <AiOutlineLogin style={{ fontSize: "1rem" }} />
                Sign In
              </Link>
            )}

            {/* Hamburger — mobile only */}
            <button
              className="fh-icon-btn fh-burger"
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
            >
              <HiMenu className="fh-icon" />
            </button>
          </div>
        </div>
      </header>

      {/* ── MOBILE OVERLAY ── */}
      <div
        className={`fh-overlay ${menuOpen ? "open" : ""}`}
        onClick={() => setMenuOpen(false)}
      />

      {/* ── MOBILE DRAWER ── */}
      <aside className={`fh-drawer ${menuOpen ? "open" : ""}`}>
        <div className="fh-drawer-head">
          <span className="fh-drawer-brand">Food<em>Rush</em></span>
          <button className="fh-close" onClick={() => setMenuOpen(false)} aria-label="Close">
            <HiX />
          </button>
        </div>

        {/* User greeting inside drawer */}
        {user && (
          <div style={{
            display: "flex", alignItems: "center", gap: 12,
            padding: "20px 28px", borderBottom: "1px solid #f0ece4",
            background: "#FAFAF8"
          }}>
            <img
              src={user.image || "/default-profile.png"}
              alt="Profile"
              style={{ width: 42, height: 42, borderRadius: "50%", objectFit: "cover", border: "2px solid #F59E0B" }}
            />
            <div>
              <p style={{ fontWeight: 600, fontSize: ".9rem", color: "#111" }}>
                {user.firstName}
              </p>
              <p style={{ fontSize: ".75rem", color: "#999", fontWeight: 300 }}>
                My Account
              </p>
            </div>
          </div>
        )}

        <nav className="fh-drawer-nav">
          {NAV.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className={`fh-dl ${isActive(to) ? "is-active" : ""}`}
            >
              {label}
            </Link>
          ))}
        </nav>

        <div className="fh-drawer-foot">
          {user ? (
            <Link to="/profile" className="fh-drawer-cta">
              View Profile
            </Link>
          ) : (
            <Link to="/login" className="fh-drawer-cta">
              <AiOutlineLogin style={{ fontSize: "1.1rem" }} />
              Sign In
            </Link>
          )}
          <Link to="/cart" className="fh-drawer-cart">
            <span>View Cart</span>
            <AiOutlineShoppingCart className="fh-cart-ic" />
          </Link>
        </div>
      </aside>
    </>
  );
}