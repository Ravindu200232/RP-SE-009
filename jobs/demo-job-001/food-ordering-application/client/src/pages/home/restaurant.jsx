import React, { useEffect, useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import Footer from "../../components/footer";

/* ── Styles ── */
const RestaurantStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .rs-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; }

    /* ── HERO ── */
    .rs-hero {
      position: relative; width: 100%; height: 380px; overflow: hidden;
    }
    .rs-hero-img {
      width: 100%; height: 100%; object-fit: cover; object-position: center;
      filter: brightness(.32);
      transform: scale(1.05);
      animation: rsZoom 9s ease forwards;
    }
    @keyframes rsZoom { to { transform: scale(1); } }
    .rs-hero-body {
      position: absolute; inset: 0;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      text-align: center; padding: 0 20px;
      animation: rsUp .85s ease both;
    }
    @keyframes rsUp {
      from { opacity:0; transform:translateY(26px); }
      to   { opacity:1; transform:none; }
    }
    .rs-eyebrow {
      font-size: .72rem; letter-spacing: .38em; text-transform: uppercase;
      color: #F59E0B; font-weight: 400; margin-bottom: 14px;
    }
    .rs-hero-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: clamp(2.8rem, 6vw, 5rem);
      font-weight: 300; color: #fff; line-height: 1.1;
    }
    .rs-hero-title em { font-style: italic; color: #F59E0B; }
    .rs-hero-sub {
      color: rgba(255,255,255,.65); font-size: .95rem; font-weight: 300;
      margin-top: 12px; max-width: 460px; line-height: 1.75;
    }

    /* ── BODY ── */
    .rs-body { max-width: 1240px; margin: 0 auto; padding: 80px 24px 100px; }

    .rs-header-row {
      display: flex; align-items: flex-end; justify-content: space-between;
      margin-bottom: 56px; flex-wrap: wrap; gap: 16px;
    }
    .rs-header-left {}
    .rs-section-label {
      font-size: .7rem; letter-spacing: .34em; text-transform: uppercase;
      color: #F59E0B; font-weight: 400; margin-bottom: 10px; display: block;
    }
    .rs-section-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: clamp(2rem, 3.5vw, 3rem);
      font-weight: 300; color: #111; line-height: 1.15;
    }
    .rs-count {
      font-size: .82rem; color: #aaa; font-weight: 300; margin-top: 6px;
    }
    .rs-count span { color: #F59E0B; font-weight: 500; }

    /* ── GRID ── */
    .rs-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
      gap: 2px;
    }

    /* ── CARD ── */
    .rs-card {
      position: relative; overflow: hidden; cursor: pointer;
      background: #111;
      transition: transform .3s;
    }
    .rs-card:hover { transform: translateY(-4px); z-index: 2; }

    .rs-card-img-wrap {
      position: relative; width: 100%; aspect-ratio: 3/4; overflow: hidden;
    }
    .rs-card-img {
      width: 100%; height: 100%; object-fit: cover;
      filter: brightness(.55);
      transition: transform .65s cubic-bezier(.25,.46,.45,.94), filter .4s;
    }
    .rs-card:hover .rs-card-img {
      transform: scale(1.08); filter: brightness(.38);
    }
    .rs-card-overlay {
      position: absolute; inset: 0;
      display: flex; flex-direction: column; justify-content: flex-end;
      padding: 28px 26px;
      background: linear-gradient(to top, rgba(0,0,0,.82) 0%, transparent 55%);
    }
    .rs-card-name {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.7rem; font-weight: 400; color: #fff; line-height: 1.15;
      margin-bottom: 6px;
    }
    .rs-card-desc {
      font-size: .8rem; color: rgba(255,255,255,.68);
      font-weight: 300; line-height: 1.6;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .rs-card-cta {
      display: inline-flex; align-items: center; gap: 6px;
      margin-top: 14px;
      font-size: .72rem; letter-spacing: .2em; text-transform: uppercase;
      color: #F59E0B; font-weight: 500;
      opacity: 0; transform: translateY(8px);
      transition: opacity .3s, transform .3s;
    }
    .rs-card:hover .rs-card-cta { opacity: 1; transform: none; }
    .rs-card-cta::after { content: '→'; }

    /* ── SKELETON ── */
    .rs-skel {
      aspect-ratio: 3/4;
      background: linear-gradient(90deg, #f5f2ec 25%, #ede9e0 50%, #f5f2ec 75%);
      background-size: 200% 100%;
      animation: rsSkel 1.5s infinite;
    }
    @keyframes rsSkel {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }

    /* ── EMPTY STATE ── */
    .rs-empty {
      grid-column: 1 / -1;
      padding: 80px 0; text-align: center;
    }
    .rs-empty-icon {
      font-size: 3.5rem; margin-bottom: 20px; opacity: .25;
    }
    .rs-empty-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: 2rem; font-weight: 300; color: #333;
    }
    .rs-empty-sub {
      font-size: .9rem; color: #aaa; font-weight: 300; margin-top: 8px;
    }

    @media (max-width: 640px) {
      .rs-grid { gap: 4px; }
      .rs-hero { height: 300px; }
    }
  `}</style>
);

/* ── Skeleton Card ── */
function SkeletonCard() {
  return <div className="rs-skel" />;
}

/* ── Main Component ── */
export default function Restaurant() {
  const [packages, setPackages] = useState([]);
  const [loading, setLoading]   = useState(true);
  const backendUrl = import.meta.env.VITE_BACKEND_URL;
  const navigate   = useNavigate();

  useEffect(() => {
    const fetchPackages = async () => {
      try {
        const token = localStorage.getItem("token");
        const response = await axios.get(
          `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setPackages(response.data);
      } catch (error) {
        console.error("Error fetching packages", error);
      } finally {
        setLoading(false);
      }
    };
    fetchPackages();
  }, [backendUrl]);

  const handleItemClick = (item) => {
    navigate(`/restaurant//${item._id}`, { state: { packageDetails: item } });
  };

  return (
    <div className="rs-root">
      <RestaurantStyles />

      {/* ── HERO ── */}
      <section className="rs-hero">
        <img
          className="rs-hero-img"
          src="https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1800&auto=format&fit=crop"
          alt="Restaurants"
        />
        <div className="rs-hero-body">
          <p className="rs-eyebrow">Discover &amp; Dine</p>
          <h1 className="rs-hero-title">
            Our <em>Restaurants</em>
          </h1>
          <p className="rs-hero-sub">
            Explore handpicked dining destinations — each with its own
            unique character, menu, and experience.
          </p>
        </div>
      </section>

      {/* ── BODY ── */}
      <div className="rs-body">
        <div className="rs-header-row">
          <div className="rs-header-left">
            <span className="rs-section-label">Browse all venues</span>
            <h2 className="rs-section-title">
              Choose your<br />restaurant
            </h2>
            {!loading && (
              <p className="rs-count">
                <span>{packages.length}</span> venue{packages.length !== 1 ? "s" : ""} available
              </p>
            )}
          </div>
        </div>

        {/* ── GRID ── */}
        <div className="rs-grid">
          {loading
            ? Array.from({ length: 8 }).map((_, idx) => (
                <SkeletonCard key={idx} />
              ))
            : packages.length === 0
            ? (
              <div className="rs-empty">
                <div className="rs-empty-icon">🍽️</div>
                <h3 className="rs-empty-title">No restaurants found</h3>
                <p className="rs-empty-sub">Check back soon — new venues are on the way.</p>
              </div>
            )
            : packages.map((item) => (
                <div
                  key={item._id}
                  className="rs-card"
                  onClick={() => handleItemClick(item)}
                >
                  <div className="rs-card-img-wrap">
                    <img
                      className="rs-card-img"
                      src={item.images?.[0] || "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&auto=format&fit=crop"}
                      alt={item.name}
                    />
                    <div className="rs-card-overlay">
                      <h3 className="rs-card-name">{item.name}</h3>
                      <p className="rs-card-desc">{item.description}</p>
                      <span className="rs-card-cta">View restaurant</span>
                    </div>
                  </div>
                </div>
              ))
          }
        </div>
      </div>

      <Footer />
    </div>
  );
}