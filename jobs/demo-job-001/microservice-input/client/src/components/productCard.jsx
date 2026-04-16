import { Link } from "react-router-dom";

const CardStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    /* ── CARD ── */
    .pc-card {
      font-family: 'Outfit', sans-serif;
      position: relative;
      overflow: hidden;
      background: #fff;
      border: 1px solid #f0ece4;
      display: flex;
      flex-direction: column;
      transition: box-shadow .32s ease, transform .32s ease, border-color .28s ease;
      cursor: pointer;
    }
    .pc-card:hover {
      box-shadow: 0 20px 56px rgba(0,0,0,.1);
      transform: translateY(-5px);
      border-color: #e8e3d8;
    }

    /* gold top-bar sweep on hover */
    .pc-bar {
      position: absolute; top: 0; left: 0;
      height: 2.5px; width: 0;
      background: #F59E0B;
      transition: width .42s ease;
      z-index: 2;
    }
    .pc-card:hover .pc-bar { width: 100%; }

    /* ── IMAGE ── */
    .pc-img-wrap {
      position: relative;
      width: 100%;
      aspect-ratio: 4 / 3;
      overflow: hidden;
      background: #f5f2ec;
    }
    .pc-img {
      width: 100%; height: 100%;
      object-fit: cover;
      transition: transform .62s cubic-bezier(.25,.46,.45,.94), filter .38s;
      filter: brightness(.92);
    }
    .pc-card:hover .pc-img {
      transform: scale(1.07);
      filter: brightness(.78);
    }

    /* availability badge — floats top-right */
    .pc-avail {
      position: absolute; top: 12px; right: 12px;
      font-size: .6rem; font-weight: 600;
      letter-spacing: .16em; text-transform: uppercase;
      padding: 4px 10px;
      backdrop-filter: blur(6px);
      border: 1px solid;
    }
    .pc-avail.yes {
      background: rgba(0,0,0,.45);
      border-color: rgba(74,222,128,.5);
      color: #4ade80;
    }
    .pc-avail.no {
      background: rgba(0,0,0,.45);
      border-color: rgba(248,113,113,.5);
      color: #f87171;
    }

    /* category tag — floats bottom-left */
    .pc-cat-tag {
      position: absolute; bottom: 12px; left: 12px;
      font-size: .58rem; font-weight: 500;
      letter-spacing: .2em; text-transform: uppercase;
      padding: 3px 9px;
      background: rgba(245,158,11,.88);
      color: #111;
      opacity: 0;
      transform: translateY(6px);
      transition: opacity .3s, transform .3s;
    }
    .pc-card:hover .pc-cat-tag { opacity: 1; transform: none; }

    /* ── BODY ── */
    .pc-body {
      padding: 20px 20px 22px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      flex: 1;
    }

    .pc-name {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.25rem;
      font-weight: 400;
      color: #111;
      line-height: 1.2;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .pc-price {
      font-size: .92rem;
      font-weight: 600;
      color: #F59E0B;
      letter-spacing: .02em;
    }

    /* ── CTA ── */
    .pc-cta {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      margin-top: 14px;
      padding: 11px;
      background: #111;
      color: #fff;
      font-family: 'Outfit', sans-serif;
      font-size: .75rem;
      font-weight: 600;
      letter-spacing: .1em;
      text-transform: uppercase;
      text-decoration: none;
      border: 1.5px solid #111;
      transition: background .24s, color .24s;
    }
    .pc-cta:hover { background: #F59E0B; border-color: #F59E0B; color: #111; }
    .pc-cta-arrow {
      font-size: .8rem;
      transition: transform .2s;
    }
    .pc-cta:hover .pc-cta-arrow { transform: translateX(3px); }
  `}</style>
);

export default function ProductCard({ item }) {
  const imageUrl =
    item.images?.[0] ||
    "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&auto=format&fit=crop";

  return (
    <>
      <CardStyles />
      <div className="pc-card">
        {/* gold hover bar */}
        <div className="pc-bar" />

        {/* ── Image ── */}
        <div className="pc-img-wrap">
          <img
            className="pc-img"
            src={imageUrl}
            alt={item.name}
            onError={(e) => {
              e.target.src =
                "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&auto=format&fit=crop";
            }}
          />

          {/* availability badge */}
          <span className={`pc-avail ${item.available ? "yes" : "no"}`}>
            {item.available ? "Available" : "Sold Out"}
          </span>

          {/* category tag */}
          {item.category && (
            <span className="pc-cat-tag">
              {item.category.toUpperCase()}
            </span>
          )}
        </div>

        {/* ── Body ── */}
        <div className="pc-body">
          <h2 className="pc-name" title={item.name}>
            {item.name}
          </h2>
          <p className="pc-price">
            Rs.{parseFloat(item.price).toFixed(2)}
          </p>

          <Link to={`/product/${item._id}`} className="pc-cta">
            View Details
            <span className="pc-cta-arrow">→</span>
          </Link>
        </div>
      </div>
    </>
  );
}