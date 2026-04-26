import { MdMoney } from "react-icons/md";
import { BiDiamond } from "react-icons/bi";
import { AiOutlineStar } from "react-icons/ai";
import { Link } from "react-router-dom";
import Footer from "../../components/footer";

/* ── Inline styles injected once ── */
const Styles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .fr-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; overflow-x:hidden; }

    /* HERO */
    .fr-hero { position:relative; width:100%; height:100vh; overflow:hidden; }
    .fr-hero-img { width:100%; height:100%; object-fit:cover; object-position:center;
      filter:brightness(.42); transform:scale(1.05);
      animation:frZoom 9s ease forwards; }
    @keyframes frZoom { to { transform:scale(1); } }
    .fr-hero-body { position:absolute; inset:0; display:flex; flex-direction:column;
      align-items:center; justify-content:center; text-align:center; padding:0 20px;
      animation:frUp .9s ease both; }
    @keyframes frUp { from{opacity:0;transform:translateY(30px)} to{opacity:1;transform:none} }
    .fr-eyebrow { font-size:.75rem; letter-spacing:.38em; text-transform:uppercase;
      color:#F59E0B; margin-bottom:20px; font-weight:400; }
    .fr-hero-title { font-family:'Cormorant Garamond',serif; font-size:clamp(3rem,8vw,7rem);
      font-weight:300; line-height:1.05; color:#fff; max-width:900px; }
    .fr-hero-title em { font-style:italic; color:#F59E0B; }
    .fr-hero-sub { color:rgba(255,255,255,.68); font-size:clamp(.95rem,1.4vw,1.1rem);
      font-weight:300; margin-top:18px; max-width:500px; line-height:1.75; }
    .fr-hero-scroll { position:absolute; bottom:28px; left:50%; transform:translateX(-50%);
      display:flex; flex-direction:column; align-items:center; gap:8px;
      color:rgba(255,255,255,.4); font-size:.65rem; letter-spacing:.22em; text-transform:uppercase; }
    .fr-scroll-line { width:1px; height:44px;
      background:linear-gradient(to bottom,transparent,rgba(255,255,255,.45));
      animation:frScroll 1.7s ease-in-out infinite; }
    @keyframes frScroll {
      0%   {transform:scaleY(0);transform-origin:top}
      50%  {transform:scaleY(1);transform-origin:top}
      51%  {transform-origin:bottom}
      100% {transform:scaleY(0);transform-origin:bottom}
    }

    /* BUTTONS */
    .btn-gold { display:inline-flex; align-items:center; gap:8px;
      background:#F59E0B; color:#111; font-family:'Outfit',sans-serif;
      font-weight:600; font-size:.85rem; letter-spacing:.1em; text-transform:uppercase;
      padding:16px 40px; text-decoration:none;
      transition:background .25s,color .25s,transform .2s; }
    .btn-gold:hover { background:#111; color:#F59E0B; transform:translateY(-2px); }
    .btn-ghost { display:inline-flex; align-items:center; gap:8px;
      border:1.5px solid #F59E0B; color:#F59E0B; font-family:'Outfit',sans-serif;
      font-weight:500; font-size:.85rem; letter-spacing:.1em; text-transform:uppercase;
      padding:15px 36px; text-decoration:none;
      transition:background .25s,color .25s; }
    .btn-ghost:hover { background:#F59E0B; color:#111; }
    .btn-ghost-dark { border-color:#fff; color:#fff; }
    .btn-ghost-dark:hover { background:#fff; color:#111; }

    /* SECTION LABELS */
    .fr-label { font-size:.72rem; letter-spacing:.35em; text-transform:uppercase;
      color:#F59E0B; font-weight:400; }
    .fr-h2 { font-family:'Cormorant Garamond',serif; font-weight:300;
      line-height:1.12; color:#111; }

    /* CATEGORY */
    .fr-cat { background:#fff; padding:100px 20px; text-align:center; }
    .fr-cat-head { max-width:680px; margin:0 auto 60px; }
    .fr-cat-head .fr-h2 { font-size:clamp(2.2rem,4vw,3.5rem); }
    .fr-cat-head p { color:#777; font-size:1rem; font-weight:300; margin-top:12px; line-height:1.7; }
    .fr-cat-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
      gap:3px; max-width:1200px; margin:0 auto; }
    .fr-card { position:relative; overflow:hidden; aspect-ratio:3/4; }
    .fr-card img { width:100%; height:100%; object-fit:cover; filter:brightness(.5);
      transition:transform .65s cubic-bezier(.25,.46,.45,.94),filter .4s; }
    .fr-card:hover img { transform:scale(1.08); filter:brightness(.38); }
    .fr-card-overlay { position:absolute; inset:0; display:flex; flex-direction:column;
      justify-content:flex-end; padding:34px 30px; text-align:left;
      background:linear-gradient(to top,rgba(0,0,0,.75) 0%,transparent 55%); }
    .fr-card-title { font-family:'Cormorant Garamond',serif; font-size:2.1rem;
      font-weight:400; color:#fff; line-height:1.1; }
    .fr-card-desc { font-size:.86rem; color:rgba(255,255,255,.72); margin-top:8px;
      line-height:1.65; font-weight:300; max-width:270px; }
    .fr-card-link { display:inline-flex; align-items:center; gap:6px; margin-top:16px;
      font-size:.75rem; letter-spacing:.2em; text-transform:uppercase;
      color:#F59E0B; font-weight:500; text-decoration:none; transition:gap .2s; }
    .fr-card-link:hover { gap:12px; }
    .fr-card-link::after { content:'→'; }

    /* POSTER */
    .fr-poster { position:relative; width:100%; height:clamp(380px,55vw,600px); overflow:hidden; }
    .fr-poster img { width:100%; height:100%; object-fit:cover; filter:brightness(.32);
      transition:transform 8s ease; }
    .fr-poster:hover img { transform:scale(1.04); }
    .fr-poster-body { position:absolute; inset:0; display:flex; flex-direction:column;
      align-items:center; justify-content:center; text-align:center; padding:0 20px; }
    .fr-poster-body .fr-h2 { font-size:clamp(2rem,5vw,4rem); color:#fff; max-width:680px; }
    .fr-poster-body p { color:rgba(255,255,255,.68); font-size:clamp(.95rem,1.4vw,1.1rem);
      font-weight:300; margin-top:14px; max-width:480px; line-height:1.7; }

    /* WHY */
    .fr-why { background:#FAFAF8; padding:100px 20px; }
    .fr-why-inner { max-width:1100px; margin:0 auto; }
    .fr-why-head { display:flex; flex-direction:column; align-items:center;
      text-align:center; margin-bottom:72px; }
    .fr-why-head .fr-h2 { font-size:clamp(2rem,3.5vw,3.2rem); }
    .fr-why-head p { color:#777; font-size:1rem; font-weight:300; max-width:500px;
      line-height:1.7; margin-top:12px; }
    .fr-why-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:32px; }
    .fr-why-card { background:#fff; border:1px solid #EEEBE3; padding:42px 32px;
      position:relative; overflow:hidden;
      transition:box-shadow .3s,transform .3s; }
    .fr-why-card:hover { box-shadow:0 24px 64px rgba(0,0,0,.07); transform:translateY(-5px); }
    .fr-why-bar { position:absolute; top:0; left:0; height:3px; width:0;
      background:#F59E0B; transition:width .45s ease; }
    .fr-why-card:hover .fr-why-bar { width:100%; }
    .fr-why-num { font-family:'Cormorant Garamond',serif; font-size:4.5rem;
      font-weight:300; color:#F59E0B; opacity:.18; line-height:1; margin-bottom:-10px; }
    .fr-why-icon { font-size:2rem; color:#F59E0B; margin-bottom:14px; }
    .fr-why-card h3 { font-family:'Cormorant Garamond',serif; font-size:1.65rem;
      font-weight:600; color:#111; margin-bottom:12px; }
    .fr-why-card p { color:#777; font-size:.9rem; line-height:1.75; font-weight:300; }

    /* TESTIMONIAL */
    .fr-testi { background:#111; padding:110px 20px; text-align:center; position:relative; overflow:hidden; }
    .fr-testi::before { content:'"'; font-family:'Cormorant Garamond',serif;
      font-size:32rem; color:rgba(245,158,11,.05); position:absolute;
      top:-60px; left:50%; transform:translateX(-50%); line-height:1; pointer-events:none; }
    .fr-testi-inner { position:relative; max-width:750px; margin:0 auto; }
    .fr-stars { display:flex; justify-content:center; gap:5px; margin-bottom:30px; }
    .fr-stars span { color:#F59E0B; font-size:1.1rem; }
    .fr-testi-text { font-family:'Cormorant Garamond',serif;
      font-size:clamp(1.5rem,3vw,2.4rem); font-weight:300; font-style:italic;
      color:#fff; line-height:1.55; }
    .fr-testi-author { margin-top:40px; display:flex; align-items:center;
      justify-content:center; gap:14px; }
    .fr-avatar { width:50px; height:50px; border-radius:50%; object-fit:cover;
      border:2px solid #F59E0B; }
    .fr-author-name { font-weight:600; font-size:.88rem; color:#fff; text-align:left; }
    .fr-author-role { font-size:.76rem; color:rgba(255,255,255,.4); font-weight:300; }

    /* CTA */
    .fr-cta { background:#fff; padding:110px 20px; display:flex; flex-direction:column;
      align-items:center; text-align:center; }
    .fr-cta .fr-h2 { font-size:clamp(2.2rem,4.5vw,4rem); max-width:600px; }
    .fr-cta p { color:#777; font-size:1rem; font-weight:300; margin-top:16px;
      max-width:420px; line-height:1.7; }
    .fr-cta-btns { display:flex; gap:16px; margin-top:48px; flex-wrap:wrap; justify-content:center; }

    @media(max-width:640px) {
      .fr-cat-grid { gap:4px; }
      .fr-why-grid { gap:20px; }
      .fr-cta-btns { flex-direction:column; align-items:center; }
    }
  `}</style>
);

export default function Home() {
  return (
    <div className="fr-root w-full">
      <Styles />

      {/* ── HERO ── */}
      <section className="fr-hero">
        <img
          className="fr-hero-img"
          src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1800&auto=format&fit=crop"
          alt="Gourmet food spread"
        />
        <div className="fr-hero-body">
          <p className="fr-eyebrow">Welcome to FoodRush</p>
          <h1 className="fr-hero-title">
            Extraordinary food,<br /><em>delivered.</em>
          </h1>
          <p className="fr-hero-sub">
            Fresh, chef-crafted meals brought to your door — hot, fast, and always
            unforgettable.
          </p>
          <Link to="/menu" className="btn-gold" style={{ marginTop: 40 }}>
            Explore Menu
          </Link>
        </div>
        <div className="fr-hero-scroll">
          <div className="fr-scroll-line" />
          <span>Scroll</span>
        </div>
      </section>

      {/* ── CATEGORIES ── */}
      <section className="fr-cat">
        <div className="fr-cat-head">
          <p className="fr-label" style={{ marginBottom: 14 }}>Our Specialties</p>
          <h2 className="fr-h2" style={{ fontSize: 'clamp(2.2rem,4vw,3.5rem)' }}>
            Craving something<br />delicious?
          </h2>
          <p>From street-food classics to family feasts — we have it all.</p>
        </div>

        <div className="fr-cat-grid">
          <div className="fr-card">
            <img
              src="https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800&auto=format&fit=crop"
              alt="Fast Food"
            />
            <div className="fr-card-overlay">
              <h3 className="fr-card-title">Fast Food</h3>
              <p className="fr-card-desc">
                Burgers, fries, wraps and more — delivered hot and fresh.
              </p>
              <Link to="/menu" className="fr-card-link">Order now</Link>
            </div>
          </div>

          <div className="fr-card">
            <img
              src="https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=800&auto=format&fit=crop"
              alt="Family Meals"
            />
            <div className="fr-card-overlay">
              <h3 className="fr-card-title">Family Meals</h3>
              <p className="fr-card-desc">
                Generous combos perfect for sharing with the people you love.
              </p>
              <Link to="/menu" className="fr-card-link">Order now</Link>
            </div>
          </div>

          <div className="fr-card">
            <img
              src="https://images.unsplash.com/photo-1551024601-bec78aea704b?w=800&auto=format&fit=crop"
              alt="Desserts"
            />
            <div className="fr-card-overlay">
              <h3 className="fr-card-title">Desserts</h3>
              <p className="fr-card-desc">
                Cakes, pastries and ice creams to satisfy your sweet tooth.
              </p>
              <Link to="/menu" className="fr-card-link">Order now</Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── POSTER BANNER ── */}
      <section className="fr-poster">
        <img
          src="https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1800&auto=format&fit=crop"
          alt="Bulk ordering for events"
        />
        <div className="fr-poster-body">
          <p className="fr-label" style={{ marginBottom: 14 }}>Bulk Orders</p>
          <h2 className="fr-h2" style={{ fontSize: 'clamp(2rem,5vw,4rem)', color: '#fff', maxWidth: 680 }}>
            Need food for a party<br />or meeting?
          </h2>
          <p>
            We've got you covered with bulk ordering options and guaranteed
            on-time delivery.
          </p>
          <Link to="/order" className="btn-ghost btn-ghost-dark" style={{ marginTop: 36 }}>
            Order Now
          </Link>
        </div>
      </section>

      {/* ── WHY FOODRUSH ── */}
      <section className="fr-why">
        <div className="fr-why-inner">
          <div className="fr-why-head">
            <p className="fr-label" style={{ marginBottom: 14 }}>Why Us</p>
            <h2 className="fr-h2" style={{ fontSize: 'clamp(2rem,3.5vw,3.2rem)' }}>
              Why choose FoodRush?
            </h2>
            <p>
              Your hunger is our priority. We deliver fresh, hot meals to your
              doorstep — every single time.
            </p>
          </div>

          <div className="fr-why-grid">
            <div className="fr-why-card">
              <div className="fr-why-bar" />
              <div className="fr-why-num">01</div>
              <div className="fr-why-icon"><AiOutlineStar /></div>
              <h3>Reliable Delivery</h3>
              <p>
                Count on us to bring your food right when you need it —
                hot, fresh, and never late.
              </p>
            </div>

            <div className="fr-why-card">
              <div className="fr-why-bar" />
              <div className="fr-why-num">02</div>
              <div className="fr-why-icon"><BiDiamond /></div>
              <h3>Premium Quality</h3>
              <p>
                We use the finest ingredients and partner with top chefs
                to bring you extraordinary meals.
              </p>
            </div>

            <div className="fr-why-card">
              <div className="fr-why-bar" />
              <div className="fr-why-num">03</div>
              <div className="fr-why-icon"><MdMoney /></div>
              <h3>Great Value</h3>
              <p>
                Exceptional food at honest prices — because a great meal
                should never break the bank.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── TESTIMONIAL ── */}
      <section className="fr-testi">
        <div className="fr-testi-inner">
          <div className="fr-stars">
            {[...Array(5)].map((_, i) => <span key={i}>★</span>)}
          </div>
          <p className="fr-testi-text">
            "The food was delivered on time and tasted amazing! It made our
            family dinner extra special. Highly recommended!"
          </p>
          <div className="fr-testi-author">
            <img
              className="fr-avatar"
              src="https://images.unsplash.com/photo-1527980965255-d3b416303d12?w=96&h=96&auto=format&fit=crop&crop=face"
              alt="James Wilson"
            />
            <div>
              <p className="fr-author-name">James Wilson</p>
              <p className="fr-author-role">Loyal Customer</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── CALL TO ACTION ── */}
      <section className="fr-cta">
        <p className="fr-label" style={{ marginBottom: 14 }}>Get Started</p>
        <h2 className="fr-h2" style={{ fontSize: 'clamp(2.2rem,4.5vw,4rem)', maxWidth: 600 }}>
          Ready to order from<br />FoodRush?
        </h2>
        <p>
          Browse our full menu or place your order right now and experience
          the difference.
        </p>
        <div className="fr-cta-btns">
          <Link to="/menu" className="btn-gold">View Menu</Link>
          <Link to="/item" className="btn-ghost">Order Now</Link>
        </div>
      </section>

      <Footer />
    </div>
  );
}