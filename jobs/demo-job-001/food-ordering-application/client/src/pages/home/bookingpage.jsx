import { useEffect, useState } from "react";
import { LoadCart } from "../../utils/card";
import BookingItem from "../../components/bookingitem";
import axios from "axios";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

/* ── Styles ── */
const CartStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .cp-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; min-height:100vh; }

    /* ── HERO ── */
    .cp-hero {
      position:relative; width:100%; height:260px; overflow:hidden; background:#111;
    }
    .cp-hero-img {
      width:100%; height:100%; object-fit:cover; filter:brightness(.28);
      transform:scale(1.04); animation:cpZoom 9s ease forwards;
    }
    @keyframes cpZoom { to { transform:scale(1); } }
    .cp-hero-body {
      position:absolute; inset:0;
      display:flex; flex-direction:column;
      align-items:center; justify-content:center;
      text-align:center; padding:0 20px;
      animation:cpUp .85s ease both;
    }
    @keyframes cpUp {
      from { opacity:0; transform:translateY(22px); }
      to   { opacity:1; transform:none; }
    }
    .cp-eyebrow {
      font-size:.7rem; letter-spacing:.38em; text-transform:uppercase;
      color:#F59E0B; font-weight:400; margin-bottom:12px;
    }
    .cp-hero-title {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(2.4rem,5vw,4rem); font-weight:300; color:#fff; line-height:1.1;
    }
    .cp-hero-title em { font-style:italic; color:#F59E0B; }

    /* ── BODY ── */
    .cp-body {
      max-width:980px; margin:0 auto;
      padding:72px 24px 140px;
      display:grid;
      grid-template-columns:1fr 340px;
      gap:40px;
      align-items:start;
    }
    @media(max-width:768px) {
      .cp-body { grid-template-columns:1fr; gap:28px; padding:48px 16px 120px; }
    }

    /* ── LEFT: item list ── */
    .cp-left {}
    .cp-section-label {
      font-size:.68rem; letter-spacing:.32em; text-transform:uppercase;
      color:#F59E0B; font-weight:400; margin-bottom:10px; display:block;
    }
    .cp-section-title {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(1.6rem,3vw,2.2rem); font-weight:300; color:#111;
      margin-bottom:28px;
    }

    .cp-item-list { display:flex; flex-direction:column; gap:2px; }

    /* wrap each BookingItem */
    .cp-item-wrap {
      border:1px solid #f0ece4; background:#FAFAF8;
      transition:border-color .25s, box-shadow .25s;
    }
    .cp-item-wrap:hover {
      border-color:#e5e0d5;
      box-shadow:0 6px 24px rgba(0,0,0,.05);
    }

    /* ── EMPTY CART ── */
    .cp-empty {
      padding:64px 0; text-align:center;
      border:1px dashed #e8e4da;
    }
    .cp-empty-icon { font-size:3rem; opacity:.22; margin-bottom:14px; }
    .cp-empty-title {
      font-family:'Cormorant Garamond',serif;
      font-size:1.8rem; font-weight:300; color:#777; font-style:italic;
    }
    .cp-empty-sub { font-size:.85rem; color:#bbb; font-weight:300; margin-top:6px; }

    /* ── RIGHT: order summary ── */
    .cp-summary {
      border:1px solid #f0ece4;
      background:#fff;
      box-shadow:0 8px 40px rgba(0,0,0,.06);
      position:sticky;
      top:100px;
    }
    .cp-summary-head {
      padding:28px 28px 22px;
      border-bottom:1px solid #f0ece4;
    }
    .cp-summary-title {
      font-family:'Cormorant Garamond',serif;
      font-size:1.5rem; font-weight:400; color:#111;
    }

    .cp-summary-body { padding:24px 28px; }

    .cp-summary-row {
      display:flex; align-items:center; justify-content:space-between;
      padding:10px 0; border-bottom:1px solid #f5f2ec;
      font-size:.88rem; color:#666; font-weight:300;
    }
    .cp-summary-row:last-of-type { border-bottom:none; }
    .cp-summary-row strong { color:#111; font-weight:500; }

    .cp-divider { height:1px; background:#f0ece4; margin:16px 0; }

    .cp-total-row {
      display:flex; align-items:center; justify-content:space-between;
      padding:12px 0;
    }
    .cp-total-label {
      font-size:.72rem; letter-spacing:.28em; text-transform:uppercase;
      color:#aaa; font-weight:400;
    }
    .cp-total-amount {
      font-family:'Cormorant Garamond',serif;
      font-size:2.2rem; font-weight:300; color:#111; line-height:1;
    }
    .cp-total-amount span { font-size:1rem; vertical-align:super; color:#aaa; font-weight:300; }

    .cp-summary-foot { padding:0 28px 28px; display:flex; flex-direction:column; gap:10px; }

    /* buttons */
    .cp-btn-primary {
      width:100%; padding:16px;
      background:#111; color:#fff;
      font-family:'Outfit',sans-serif;
      font-size:.82rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      border:none; cursor:pointer;
      display:flex; align-items:center; justify-content:center; gap:8px;
      transition:background .24s,color .24s,transform .2s;
    }
    .cp-btn-primary:hover { background:#F59E0B; color:#111; transform:translateY(-2px); }

    .cp-btn-outline {
      width:100%; padding:14px;
      background:transparent; color:#555;
      border:1.5px solid #e8e4da;
      font-family:'Outfit',sans-serif;
      font-size:.78rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      cursor:pointer;
      display:flex; align-items:center; justify-content:center; gap:8px;
      transition:border-color .22s,color .22s;
    }
    .cp-btn-outline:hover { border-color:#F59E0B; color:#F59E0B; }

    /* ── LOADING TOTAL ── */
    .cp-total-loading {
      display:inline-block; width:80px; height:24px;
      background:linear-gradient(90deg,#f5f2ec 25%,#ede9e0 50%,#f5f2ec 75%);
      background-size:200% 100%;
      animation:cpSkel 1.5s infinite; vertical-align:middle;
    }
    @keyframes cpSkel {
      0% { background-position:200% 0; }
      100% { background-position:-200% 0; }
    }

    /* ── FLOATING address btn (mobile) ── */
    .cp-fab {
      position:fixed; bottom:28px; right:24px;
      display:flex; align-items:center; gap:8px;
      padding:14px 24px;
      background:#F59E0B; color:#111;
      font-family:'Outfit',sans-serif;
      font-size:.78rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
      border:none; cursor:pointer;
      box-shadow:0 8px 28px rgba(245,158,11,.4);
      transition:background .22s,color .22s,transform .2s;
      z-index:100;
    }
    .cp-fab:hover { background:#111; color:#F59E0B; transform:translateY(-3px); }
    /* hide fab on desktop (address btn is in summary) */
    @media(min-width:769px) { .cp-fab { display:none; } }
  `}</style>
);

export function BookingPage() {
  const [cart, setCart]     = useState(LoadCart());
  const [total, setTotal]   = useState(null); // null = loading
  const navigate            = useNavigate();

  function reloadCart() {
    setCart(LoadCart());
    calculateTotal();
  }

  function calculateTotal() {
    const cartInfo = LoadCart();
    console.log(cartInfo);
    axios
      .post(`${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders/quote`, cartInfo)
      .then((res) => {
        console.log(res.data.orderItem);
        setTotal(res.data.total);
      })
      .catch((err) => {
        console.log(err);
        setTotal(0);
      });
    console.log("cart", LoadCart());
  }

  useEffect(() => { calculateTotal(); }, []);

  function handleBookingCreation() {
    const cart  = LoadCart();
    const token = localStorage.getItem("token");
    console.log("load", LoadCart());
    console.log(token);

    axios
      .post(`${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders`, cart, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((res) => {
        console.log("res", res.data.orders);
        const sendData = res.data.orders;
        localStorage.removeItem("cart");
        toast.success("Booking Created");
        setCart(LoadCart());
        if (res.data) {
          navigate("/bookingconfirmation", { state: { sendData } });
        } else {
          toast.error("Invalid booking details received.");
        }
      })
      .catch((err) => {
        console.log(err);
        toast.success("Please Login");
      });
  }

  const itemCount = cart.orderItem.length;

  return (
    <div className="cp-root">
      <CartStyles />

      {/* ── HERO ── */}
      <section className="cp-hero">
        <img
          className="cp-hero-img"
          src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1800&auto=format&fit=crop"
          alt="Cart"
        />
        <div className="cp-hero-body">
          <p className="cp-eyebrow">Review your order</p>
          <h1 className="cp-hero-title">
            Your <em>Cart</em>
          </h1>
        </div>
      </section>

      {/* ── BODY GRID ── */}
      <div className="cp-body">

        {/* ── LEFT: Items ── */}
        <div className="cp-left">
          <span className="cp-section-label">
            {itemCount} item{itemCount !== 1 ? "s" : ""} in cart
          </span>
          <h2 className="cp-section-title">Order Items</h2>

          {itemCount > 0 ? (
            <div className="cp-item-list">
              {cart.orderItem.map((item) => (
                <div key={item.key} className="cp-item-wrap">
                  <BookingItem
                    itemKey={item.key}
                    qty={item.qty}
                    refresh={reloadCart}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="cp-empty">
              <div className="cp-empty-icon">🛒</div>
              <h3 className="cp-empty-title">Your cart is empty</h3>
              <p className="cp-empty-sub">
                Browse our menu and add something delicious.
              </p>
            </div>
          )}
        </div>

        {/* ── RIGHT: Summary ── */}
        <div className="cp-summary">
          <div className="cp-summary-head">
            <span className="cp-section-label" style={{ marginBottom:6 }}>Order Summary</span>
            <h3 className="cp-summary-title">Price Details</h3>
          </div>

          <div className="cp-summary-body">
            <div className="cp-summary-row">
              <span>Items</span>
              <strong>{itemCount}</strong>
            </div>
            <div className="cp-summary-row">
              <span>Delivery</span>
              <strong style={{ color:"#4ade80" }}>Free</strong>
            </div>

            <div className="cp-divider" />

            <div className="cp-total-row">
              <span className="cp-total-label">Total</span>
              <span className="cp-total-amount">
                {total === null ? (
                  <span className="cp-total-loading" />
                ) : (
                  <><span>Rs.</span>{total.toFixed(2)}</>
                )}
              </span>
            </div>
          </div>

          <div className="cp-summary-foot">
            <button
              className="cp-btn-primary"
              onClick={handleBookingCreation}
              disabled={itemCount === 0}
              style={ itemCount === 0 ? { opacity:.45, cursor:"not-allowed" } : {} }
            >
              🛍 Place Order
            </button>

            <button
              className="cp-btn-outline"
              onClick={() => navigate("/location")}
            >
              📍 Update Address
            </button>
          </div>
        </div>

      </div>

      {/* ── FAB for mobile: update address ── */}
      <button className="cp-fab" onClick={() => navigate("/location")}>
        📍 Update Address
      </button>
    </div>
  );
}