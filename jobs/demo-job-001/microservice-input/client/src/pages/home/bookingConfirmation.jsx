import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

const ConfirmStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .bc-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; min-height:100vh; }

    /* ── HERO ── */
    .bc-hero {
      position:relative; width:100%; height:280px; overflow:hidden; background:#111;
    }
    .bc-hero-img {
      width:100%; height:100%; object-fit:cover; filter:brightness(.28);
      transform:scale(1.05); animation:bcZoom 9s ease forwards;
    }
    @keyframes bcZoom { to { transform:scale(1); } }
    .bc-hero-body {
      position:absolute; inset:0;
      display:flex; flex-direction:column;
      align-items:center; justify-content:center;
      text-align:center; padding:0 20px;
      animation:bcUp .85s ease both;
    }
    @keyframes bcUp {
      from { opacity:0; transform:translateY(22px); }
      to   { opacity:1; transform:none; }
    }
    .bc-eyebrow {
      font-size:.7rem; letter-spacing:.38em; text-transform:uppercase;
      color:#4ade80; font-weight:400; margin-bottom:12px;
    }
    .bc-hero-title {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(2.4rem,5vw,4rem); font-weight:300; color:#fff; line-height:1.1;
    }
    .bc-hero-title em { font-style:italic; color:#F59E0B; }

    /* ── BODY ── */
    .bc-body {
      max-width:860px; margin:0 auto;
      padding:64px 24px 100px;
      display:grid;
      grid-template-columns:1fr 300px;
      gap:36px; align-items:start;
    }
    @media(max-width:768px) {
      .bc-body { grid-template-columns:1fr; gap:24px; padding:48px 16px 80px; }
    }

    /* ── SECTION LABELS ── */
    .bc-section-label {
      font-size:.68rem; letter-spacing:.32em; text-transform:uppercase;
      color:#F59E0B; font-weight:400; margin-bottom:10px; display:block;
    }
    .bc-section-title {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(1.5rem,3vw,2rem); font-weight:300; color:#111;
      margin-bottom:24px;
    }

    /* ── SUCCESS BADGE ── */
    .bc-badge {
      display:inline-flex; align-items:center; gap:8px;
      padding:8px 20px; margin-bottom:28px;
      border:1.5px solid rgba(74,222,128,.4);
      background:rgba(74,222,128,.06);
      font-size:.72rem; letter-spacing:.2em; text-transform:uppercase;
      font-weight:600; color:#4ade80;
    }
    .bc-badge-dot {
      width:6px; height:6px; border-radius:50%; background:#4ade80;
      animation:bcPulse 1.5s infinite;
    }
    @keyframes bcPulse { 0%,100%{opacity:1} 50%{opacity:.3} }

    /* ── ORDER META CARD ── */
    .bc-meta-card {
      border:1px solid #f0ece4; background:#FAFAF8;
      margin-bottom:28px;
    }
    .bc-meta-row {
      display:flex; align-items:flex-start; gap:14px;
      padding:16px 22px; border-bottom:1px solid #f0ece4;
    }
    .bc-meta-row:last-child { border-bottom:none; }
    .bc-meta-icon { color:#F59E0B; font-size:1rem; margin-top:2px; flex-shrink:0; }
    .bc-meta-label {
      font-size:.64rem; letter-spacing:.22em; text-transform:uppercase;
      color:#bbb; font-weight:400; display:block; margin-bottom:2px;
    }
    .bc-meta-value { font-size:.9rem; font-weight:500; color:#333; }

    /* ── ITEM LIST ── */
    .bc-item-list { display:flex; flex-direction:column; gap:2px; }
    .bc-item-row {
      display:grid; grid-template-columns:72px 1fr auto;
      background:#fff; border:1px solid #f0ece4;
      transition:border-color .25s, box-shadow .25s;
    }
    .bc-item-row:hover { border-color:#e5e0d5; box-shadow:0 4px 16px rgba(0,0,0,.05); }

    .bc-item-img { width:72px; aspect-ratio:1; object-fit:cover; }
    .bc-item-info { padding:14px 16px; }
    .bc-item-name {
      font-family:'Cormorant Garamond',serif;
      font-size:1.05rem; font-weight:400; color:#111;
      margin-bottom:4px; line-height:1.2;
    }
    .bc-item-meta { font-size:.75rem; color:#aaa; font-weight:300; line-height:1.6; }
    .bc-item-meta strong { color:#666; font-weight:500; }
    .bc-item-price {
      padding:14px 16px;
      display:flex; align-items:center; justify-content:flex-end;
      font-family:'Cormorant Garamond',serif;
      font-size:1.15rem; font-weight:300; color:#111; white-space:nowrap;
    }
    .bc-item-price span { font-size:.7rem; color:#aaa; vertical-align:super; font-weight:300; }

    /* ── SUMMARY CARD (right) ── */
    .bc-summary {
      border:1px solid #f0ece4;
      box-shadow:0 8px 40px rgba(0,0,0,.06);
      position:sticky; top:100px;
    }
    .bc-summary-head {
      padding:24px 24px 18px; border-bottom:1px solid #f0ece4;
    }
    .bc-summary-title {
      font-family:'Cormorant Garamond',serif;
      font-size:1.4rem; font-weight:400; color:#111;
    }
    .bc-summary-body { padding:20px 24px; }
    .bc-sum-row {
      display:flex; align-items:center; justify-content:space-between;
      padding:9px 0; border-bottom:1px solid #f5f2ec;
      font-size:.85rem; color:#666; font-weight:300;
    }
    .bc-sum-row:last-of-type { border-bottom:none; }
    .bc-sum-row strong { color:#111; font-weight:500; }
    .bc-divider { height:1px; background:#f0ece4; margin:14px 0; }
    .bc-total-row {
      display:flex; align-items:center; justify-content:space-between;
    }
    .bc-total-label {
      font-size:.68rem; letter-spacing:.26em; text-transform:uppercase;
      color:#aaa; font-weight:400;
    }
    .bc-total-amount {
      font-family:'Cormorant Garamond',serif;
      font-size:2rem; font-weight:300; color:#111; line-height:1;
    }
    .bc-total-amount span { font-size:.85rem; color:#aaa; vertical-align:super; font-weight:300; }

    .bc-summary-foot { padding:0 24px 24px; display:flex; flex-direction:column; gap:10px; }

    /* ── BUTTONS ── */
    .bc-btn-primary {
      width:100%; padding:15px;
      background:#111; color:#fff;
      font-family:'Outfit',sans-serif;
      font-size:.8rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      border:none; cursor:pointer;
      display:flex; align-items:center; justify-content:center; gap:8px;
      transition:background .24s,color .24s,transform .2s;
    }
    .bc-btn-primary:hover { background:#F59E0B; color:#111; transform:translateY(-2px); }
    .bc-btn-ghost {
      width:100%; padding:13px;
      background:transparent; color:#999;
      border:1.5px solid #e8e4da;
      font-family:'Outfit',sans-serif;
      font-size:.78rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      cursor:pointer;
      display:flex; align-items:center; justify-content:center; gap:7px;
      transition:border-color .22s,color .22s;
    }
    .bc-btn-ghost:hover { border-color:#aaa; color:#555; }

    /* ── NOT FOUND ── */
    .bc-notfound {
      min-height:70vh; display:flex; flex-direction:column;
      align-items:center; justify-content:center; gap:16px; text-align:center;
    }
    .bc-notfound-icon { font-size:3rem; opacity:.2; }
    .bc-notfound-title {
      font-family:'Cormorant Garamond',serif;
      font-size:2rem; font-weight:300; color:#777; font-style:italic;
    }
    .bc-notfound-sub { font-size:.88rem; color:#bbb; font-weight:300; }
  `}</style>
);

export default function BookingConfirmation() {
  const location = useLocation();
  const navigate  = useNavigate();
  const [orderItems, setOrderItems] = useState([]);

  useEffect(() => {
    const bookingData = location.state?.sendData || [];
    setOrderItems(bookingData);
  }, [location.state]);

  /* ── not found ── */
  if (!location.state?.sendData) {
    return (
      <div className="bc-root">
        <ConfirmStyles />
        <div className="bc-notfound">
          <div className="bc-notfound-icon">📋</div>
          <h2 className="bc-notfound-title">Booking details not found</h2>
          <p className="bc-notfound-sub">This page requires an active booking session.</p>
        </div>
      </div>
    );
  }

  const totalAmount = orderItems.reduce((sum, item) => sum + item.totalAmount, 0);

  const handleProceedToPayment = () => {
    navigate("/payment", {
      state: {
        amount: totalAmount,
        bookingIds: orderItems.map((item) => item.orderId),
      },
    });
  };

  return (
    <div className="bc-root">
      <ConfirmStyles />

      {/* ── HERO ── */}
      <section className="bc-hero">
        <img
          className="bc-hero-img"
          src="https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1800&auto=format&fit=crop"
          alt="Order confirmed"
        />
        <div className="bc-hero-body">
          <p className="bc-eyebrow">✓ Order Placed</p>
          <h1 className="bc-hero-title">
            Booking <em>Confirmed</em>
          </h1>
        </div>
      </section>

      {/* ── BODY ── */}
      <div className="bc-body">

        {/* ── LEFT ── */}
        <div>
          {/* success badge */}
          <div className="bc-badge">
            <span className="bc-badge-dot" />
            Your order is confirmed
          </div>

          {/* order meta */}
          <div className="bc-meta-card">
            <div className="bc-meta-row">
              <span className="bc-meta-icon">✉</span>
              <div>
                <span className="bc-meta-label">Email</span>
                <span className="bc-meta-value">{orderItems[0]?.email}</span>
              </div>
            </div>
            <div className="bc-meta-row">
              <span className="bc-meta-icon">📍</span>
              <div>
                <span className="bc-meta-label">Delivery Address</span>
                <span className="bc-meta-value">{orderItems[0]?.address}</span>
              </div>
            </div>
          </div>

          {/* items */}
          <span className="bc-section-label">Items Ordered</span>
          <div className="bc-item-list">
            {orderItems.map((item, index) => (
              <div key={index} className="bc-item-row">
                <img
                  className="bc-item-img"
                  src={
                    item.image ||
                    "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=144&auto=format&fit=crop"
                  }
                  alt={item.Item_name}
                  onError={(e) => {
                    e.target.src =
                      "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=144&auto=format&fit=crop";
                  }}
                />
                <div className="bc-item-info">
                  <h3 className="bc-item-name">{item.Item_name}</h3>
                  <p className="bc-item-meta">
                    <strong>Order ID:</strong> {item.orderId}<br />
                    <strong>Qty:</strong> {item.quantity} ·{" "}
                    <strong>Unit:</strong> Rs.{parseFloat(item.price).toFixed(2)}
                  </p>
                </div>
                <div className="bc-item-price">
                  <span>Rs.</span>
                  {parseFloat(item.price * item.quantity).toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── RIGHT: Summary ── */}
        <div className="bc-summary">
          <div className="bc-summary-head">
            <span className="bc-section-label" style={{ marginBottom:6 }}>Order Summary</span>
            <h3 className="bc-summary-title">Price Breakdown</h3>
          </div>

          <div className="bc-summary-body">
            <div className="bc-sum-row">
              <span>Items</span>
              <strong>{orderItems.length}</strong>
            </div>
            <div className="bc-sum-row">
              <span>Delivery</span>
              <strong style={{ color:"#4ade80" }}>Free</strong>
            </div>

            <div className="bc-divider" />

            <div className="bc-total-row">
              <span className="bc-total-label">Total</span>
              <span className="bc-total-amount">
                <span>Rs.</span>{totalAmount.toFixed(2)}
              </span>
            </div>
          </div>

          <div className="bc-summary-foot">
            <button className="bc-btn-primary" onClick={handleProceedToPayment}>
              💳 Proceed to Payment
            </button>
            <button className="bc-btn-ghost" onClick={() => navigate(-1)}>
              ← Cancel
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}