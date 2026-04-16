import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import axios from "axios";
import toast from "react-hot-toast";

/* ── Styles ── */
const DetailsStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .rd-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; min-height:100vh; }

    /* ── HERO SLIDESHOW ── */
    .rd-hero {
      position: relative; width: 100%; height: 500px; overflow: hidden; background: #111;
    }
    .rd-hero-img {
      position: absolute; inset: 0;
      width: 100%; height: 100%; object-fit: cover;
      filter: brightness(.38);
      transform: scale(1.04);
      animation: rdZoom 9s ease forwards;
      transition: opacity .9s ease;
    }
    @keyframes rdZoom { to { transform: scale(1); } }

    /* dots */
    .rd-dots {
      position: absolute; bottom: 28px; left: 50%; transform: translateX(-50%);
      display: flex; gap: 8px;
    }
    .rd-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: rgba(255,255,255,.35);
      border: 1.5px solid rgba(255,255,255,.5);
      cursor: pointer;
      transition: background .3s, transform .3s;
    }
    .rd-dot.active { background: #F59E0B; border-color: #F59E0B; transform: scale(1.3); }

    /* hero content */
    .rd-hero-body {
      position: absolute; inset: 0;
      display: flex; flex-direction: column;
      align-items: center; justify-content: flex-end;
      padding: 0 24px 56px;
      text-align: center;
      background: linear-gradient(to top, rgba(0,0,0,.75) 0%, transparent 55%);
      animation: rdUp .9s ease both;
    }
    @keyframes rdUp {
      from { opacity:0; transform:translateY(24px); }
      to   { opacity:1; transform:none; }
    }
    .rd-eyebrow {
      font-size: .7rem; letter-spacing: .36em; text-transform: uppercase;
      color: #F59E0B; font-weight: 400; margin-bottom: 10px;
    }
    .rd-hero-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: clamp(2.4rem, 5.5vw, 4.5rem);
      font-weight: 300; color: #fff; line-height: 1.1;
    }
    .rd-hero-title em { font-style: italic; color: #F59E0B; }
    .rd-status-badge {
      display: inline-flex; align-items: center; gap: 6px;
      margin-top: 16px; padding: 6px 18px;
      font-size: .72rem; letter-spacing: .18em; text-transform: uppercase; font-weight: 600;
      border: 1.5px solid;
    }
    .rd-status-badge.open   { border-color: #4ade80; color: #4ade80; }
    .rd-status-badge.closed { border-color: #f87171; color: #f87171; }
    .rd-status-dot {
      width: 6px; height: 6px; border-radius: 50%;
      animation: rdPulse 1.5s infinite;
    }
    .open .rd-status-dot   { background: #4ade80; }
    .closed .rd-status-dot { background: #f87171; animation: none; }
    @keyframes rdPulse {
      0%,100% { opacity:1; } 50% { opacity:.4; }
    }

    /* ── BODY ── */
    .rd-body { max-width: 1160px; margin: 0 auto; padding: 72px 24px 100px; }

    /* ── INFO ROW ── */
    .rd-info-row {
      display: grid; grid-template-columns: 1fr 1fr 1fr;
      gap: 2px; margin-bottom: 72px;
    }
    @media (max-width: 768px) {
      .rd-info-row { grid-template-columns: 1fr; gap: 4px; }
    }
    .rd-info-card {
      padding: 30px 28px; background: #FAFAF8;
      border: 1px solid #f0ece4;
      display: flex; flex-direction: column; gap: 6px;
      transition: box-shadow .3s, transform .3s, border-color .3s;
    }
    .rd-info-card:hover {
      box-shadow: 0 12px 36px rgba(0,0,0,.07);
      transform: translateY(-3px); border-color: #F59E0B;
    }
    .rd-info-icon { font-size: 1.4rem; color: #F59E0B; margin-bottom: 4px; }
    .rd-info-label {
      font-size: .65rem; letter-spacing: .28em; text-transform: uppercase;
      color: #bbb; font-weight: 400;
    }
    .rd-info-value { font-size: .96rem; font-weight: 500; color: #222; }

    /* Description block */
    .rd-desc-block {
      padding: 40px; border: 1px solid #f0ece4; background: #fff;
      margin-bottom: 72px;
      box-shadow: 0 4px 24px rgba(0,0,0,.04);
    }
    .rd-desc-label {
      font-size: .68rem; letter-spacing: .32em; text-transform: uppercase;
      color: #F59E0B; font-weight: 400; margin-bottom: 14px; display: block;
    }
    .rd-desc-text {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.4rem; font-weight: 300; color: #333;
      line-height: 1.7; font-style: italic;
    }

    /* ── COLLECTIONS ── */
    .rd-collections-head {
      margin-bottom: 44px;
    }
    .rd-section-label {
      font-size: .68rem; letter-spacing: .32em; text-transform: uppercase;
      color: #F59E0B; font-weight: 400; margin-bottom: 10px; display: block;
    }
    .rd-section-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: clamp(1.8rem, 3vw, 2.8rem);
      font-weight: 300; color: #111; line-height: 1.15;
    }

    /* ── DISH GRID ── */
    .rd-dish-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 2px;
    }
    .rd-dish-card {
      position: relative; overflow: hidden; cursor: pointer;
      display: block; text-decoration: none;
      background: #111;
      transition: transform .3s;
    }
    .rd-dish-card:hover { transform: translateY(-4px); z-index: 2; }
    .rd-dish-img-wrap { position: relative; width: 100%; aspect-ratio: 4/3; overflow: hidden; }
    .rd-dish-img {
      width: 100%; height: 100%; object-fit: cover;
      filter: brightness(.52);
      transition: transform .65s cubic-bezier(.25,.46,.45,.94), filter .4s;
    }
    .rd-dish-card:hover .rd-dish-img { transform: scale(1.08); filter: brightness(.38); }
    .rd-dish-overlay {
      position: absolute; inset: 0;
      display: flex; flex-direction: column; justify-content: flex-end;
      padding: 22px 22px;
      background: linear-gradient(to top, rgba(0,0,0,.82) 0%, transparent 55%);
    }
    .rd-dish-name {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.45rem; font-weight: 400; color: #fff; line-height: 1.15;
      margin-bottom: 4px;
    }
    .rd-dish-desc {
      font-size: .78rem; color: rgba(255,255,255,.65); font-weight: 300;
      line-height: 1.55;
      display: -webkit-box; -webkit-line-clamp: 2;
      -webkit-box-orient: vertical; overflow: hidden;
      margin-bottom: 10px;
    }
    .rd-dish-footer {
      display: flex; align-items: center; justify-content: space-between;
      margin-top: 8px;
    }
    .rd-dish-price {
      font-size: .88rem; font-weight: 600; color: #F59E0B;
    }
    .rd-avail-badge {
      font-size: .65rem; letter-spacing: .15em; text-transform: uppercase;
      font-weight: 600; padding: 4px 10px;
    }
    .rd-avail-badge.yes { color: #4ade80; border: 1px solid rgba(74,222,128,.4); }
    .rd-avail-badge.no  { color: #f87171; border: 1px solid rgba(248,113,113,.4); }

    .rd-dish-cta {
      display: inline-flex; align-items: center; gap: 5px;
      font-size: .68rem; letter-spacing: .2em; text-transform: uppercase;
      color: #F59E0B; font-weight: 500;
      opacity: 0; transform: translateY(6px);
      transition: opacity .3s, transform .3s;
      margin-top: 4px;
    }
    .rd-dish-card:hover .rd-dish-cta { opacity: 1; transform: none; }
    .rd-dish-cta::after { content: '→'; }

    /* ── LOADING / EMPTY ── */
    .rd-loading {
      min-height: 60vh; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      text-align: center; gap: 20px;
    }
    .rd-spinner {
      width: 44px; height: 44px; border-radius: 50%;
      border: 2px solid #f0ece4;
      border-top-color: #F59E0B;
      animation: rdSpin .8s linear infinite;
    }
    @keyframes rdSpin { to { transform: rotate(360deg); } }
    .rd-loading-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.6rem; font-weight: 300; color: #aaa;
    }

    .rd-empty {
      padding: 60px 0; text-align: center;
    }
    .rd-empty-icon { font-size: 3rem; opacity: .25; margin-bottom: 16px; }
    .rd-empty-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.8rem; font-weight: 300; color: #555;
    }
    .rd-empty-sub { font-size: .88rem; color: #aaa; font-weight: 300; margin-top: 6px; }

    @media (max-width: 640px) {
      .rd-hero { height: 380px; }
      .rd-body { padding: 48px 16px 80px; }
      .rd-desc-block { padding: 28px 22px; }
      .rd-dish-grid { gap: 4px; }
    }
  `}</style>
);

export default function RestaurantDetails() {
  const location = useLocation();
  const id = location.state?.packageDetails?._id;

  const backendUrl = import.meta.env.VITE_BACKEND_URL;
  const [restaurant, setRestaurant]           = useState(null);
  const [collections, setCollections]         = useState([]);
  const [loading, setLoading]                 = useState(true);
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  useEffect(() => {
    const fetchRestaurant = async () => {
      if (!id) return setLoading(false);
      try {
        const res = await axios.get(
          `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant/getOne/${id}`
        );
        setRestaurant(res.data);
        const collRes = await axios.get(
          `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection/getAll/${id}`
        );
        setCollections(collRes.data || []);
      } catch (err) {
        console.error("Error fetching data:", err);
        toast.error("Failed to load restaurant or collections.");
      } finally {
        setLoading(false);
      }
    };
    fetchRestaurant();
  }, [id]);

  /* auto-advance slideshow */
  useEffect(() => {
    if (!restaurant?.images?.length) return;
    const interval = setInterval(() => {
      setCurrentImageIndex((p) =>
        p === restaurant.images.length - 1 ? 0 : p + 1
      );
    }, 3000);
    return () => clearInterval(interval);
  }, [restaurant]);

  /* ── loading state ── */
  if (loading) {
    return (
      <div className="rd-root">
        <DetailsStyles />
        <div className="rd-loading">
          <div className="rd-spinner" />
          <p className="rd-loading-title">Loading restaurant…</p>
        </div>
      </div>
    );
  }

  /* ── not found ── */
  if (!restaurant) {
    return (
      <div className="rd-root">
        <DetailsStyles />
        <div className="rd-loading">
          <div className="rd-empty-icon">🍽️</div>
          <h2 className="rd-empty-title">Restaurant not found</h2>
          <p className="rd-empty-sub">This venue may have moved or been removed.</p>
        </div>
      </div>
    );
  }

  const heroImg =
    restaurant.images?.[currentImageIndex] ||
    "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1800&auto=format&fit=crop";

  return (
    <div className="rd-root">
      <DetailsStyles />

      {/* ── HERO SLIDESHOW ── */}
      <section className="rd-hero">
        <img
          key={currentImageIndex}
          className="rd-hero-img"
          src={heroImg}
          alt={restaurant.name}
        />

        <div className="rd-hero-body">
          <p className="rd-eyebrow">FoodRush · Restaurant</p>
          <h1 className="rd-hero-title">
            <em>{restaurant.name}</em>
          </h1>
          <span className={`rd-status-badge ${restaurant.isOpen ? "open" : "closed"}`}>
            <span className="rd-status-dot" />
            {restaurant.isOpen ? "Open Now" : "Currently Closed"}
          </span>
        </div>

        {/* dots */}
        {restaurant.images?.length > 1 && (
          <div className="rd-dots">
            {restaurant.images.map((_, idx) => (
              <span
                key={idx}
                className={`rd-dot ${idx === currentImageIndex ? "active" : ""}`}
                onClick={() => setCurrentImageIndex(idx)}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── BODY ── */}
      <div className="rd-body">

        {/* Info cards row */}
        <div className="rd-info-row">
          <div className="rd-info-card">
            <span className="rd-info-icon">👤</span>
            <span className="rd-info-label">Owner</span>
            <span className="rd-info-value">{restaurant.ownerName}</span>
          </div>
          <div className="rd-info-card">
            <span className="rd-info-icon">📍</span>
            <span className="rd-info-label">Address</span>
            <span className="rd-info-value">{restaurant.address}</span>
          </div>
          <div className="rd-info-card">
            <span className="rd-info-icon">📞</span>
            <span className="rd-info-label">Phone</span>
            <span className="rd-info-value">{restaurant.phone}</span>
          </div>
        </div>

        {/* Description */}
        {restaurant.description && (
          <div className="rd-desc-block">
            <span className="rd-desc-label">About this restaurant</span>
            <p className="rd-desc-text">"{restaurant.description}"</p>
          </div>
        )}

        {/* Collections */}
        {collections.length > 0 ? (
          <>
            <div className="rd-collections-head">
              <span className="rd-section-label">Explore the menu</span>
              <h2 className="rd-section-title">
                Available <em style={{ fontStyle:"italic", color:"#F59E0B" }}>Dishes</em>
              </h2>
            </div>

            <div className="rd-dish-grid">
              {collections.map((item) => (
                <Link key={item._id} to={`/product/${item._id}`} className="rd-dish-card">
                  <div className="rd-dish-img-wrap">
                    <img
                      className="rd-dish-img"
                      src={
                        item.images?.[0] ||
                        "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&auto=format&fit=crop"
                      }
                      alt={item.name}
                    />
                    <div className="rd-dish-overlay">
                      <h3 className="rd-dish-name">{item.name}</h3>
                      <p className="rd-dish-desc">{item.description}</p>
                      <div className="rd-dish-footer">
                        <span className="rd-dish-price">
                          ₹{parseFloat(item.price).toFixed(2)}
                        </span>
                        <span className={`rd-avail-badge ${item.available ? "yes" : "no"}`}>
                          {item.available ? "Available" : "Unavailable"}
                        </span>
                      </div>
                      <span className="rd-dish-cta">View dish</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </>
        ) : (
          <div className="rd-empty">
            <div className="rd-empty-icon">🍽️</div>
            <h3 className="rd-empty-title">No dishes yet</h3>
            <p className="rd-empty-sub">
              This restaurant hasn't added any items to their menu.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}