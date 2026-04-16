import { MdDeleteForever } from "react-icons/md";
import { AiFillDownSquare, AiFillUpSquare } from "react-icons/ai";
import axios from "axios";
import { useEffect, useState } from "react";
import { addToCart, removeFromCart } from "../utils/card";

/* ── Styles ── */
const BookingItemStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    /* ── ITEM ROW ── */
    .bi-row {
      font-family: 'Outfit', sans-serif;
      display: grid;
      grid-template-columns: 88px 1fr auto auto;
      gap: 0;
      align-items: stretch;
      background: #fff;
      transition: background .2s;
    }
    .bi-row:hover { background: #FFFDF7; }

    /* ── IMAGE ── */
    .bi-img-wrap {
      width: 88px;
      aspect-ratio: 1;
      overflow: hidden;
      flex-shrink: 0;
    }
    .bi-img {
      width: 100%; height: 100%; object-fit: cover;
      transition: transform .55s cubic-bezier(.25,.46,.45,.94);
    }
    .bi-row:hover .bi-img { transform: scale(1.07); }

    /* ── INFO ── */
    .bi-info {
      padding: 18px 20px;
      display: flex; flex-direction: column;
      justify-content: center; gap: 4px;
      border-right: 1px solid #f0ece4;
    }
    .bi-name {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.15rem; font-weight: 400; color: #111;
      line-height: 1.2;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      max-width: 300px;
    }
    .bi-desc {
      font-size: .78rem; color: #aaa; font-weight: 300;
      line-height: 1.55;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      max-width: 300px;
    }
    .bi-unit-price {
      font-size: .78rem; color: #888; font-weight: 300; margin-top: 2px;
    }
    .bi-unit-price strong { color: #F59E0B; font-weight: 600; }

    /* ── QTY CONTROL ── */
    .bi-qty {
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 0 20px; gap: 6px;
      border-right: 1px solid #f0ece4;
    }
    .bi-qty-btn {
      display: flex; align-items: center; justify-content: center;
      width: 28px; height: 28px;
      border: 1.5px solid #e8e4da; background: #FAFAF8;
      color: #888; cursor: pointer;
      font-size: .9rem;
      transition: border-color .2s, background .2s, color .2s;
    }
    .bi-qty-btn:hover { border-color: #F59E0B; color: #F59E0B; background: #fffbf0; }
    .bi-qty-btn.danger:hover { border-color: #e5595a; color: #e5595a; background: #fff5f5; }
    .bi-qty-num {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.35rem; font-weight: 400; color: #111;
      line-height: 1; min-width: 24px; text-align: center;
    }

    /* ── TOTAL + DELETE ── */
    .bi-right {
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 18px 20px; gap: 10px;
    }
    .bi-total {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.4rem; font-weight: 300; color: #111;
      line-height: 1; white-space: nowrap;
    }
    .bi-total span { font-size: .75rem; color: #aaa; vertical-align: super; font-weight: 300; }
    .bi-delete {
      display: flex; align-items: center; justify-content: center;
      width: 32px; height: 32px;
      border: 1.5px solid #f0ece4; background: transparent;
      color: #ccc; cursor: pointer;
      font-size: 1.1rem;
      transition: border-color .2s, background .2s, color .2s;
    }
    .bi-delete:hover { border-color: #e5595a; background: #fff5f5; color: #e5595a; }

    /* ── SKELETON ── */
    .bi-skel {
      display: grid; grid-template-columns: 88px 1fr auto auto;
      background: #fff;
    }
    .bi-skel-img {
      width: 88px; aspect-ratio: 1;
      background: linear-gradient(90deg,#f5f2ec 25%,#ede9e0 50%,#f5f2ec 75%);
      background-size: 200% 100%;
      animation: biSkel 1.5s infinite;
    }
    .bi-skel-body {
      padding: 18px 20px; display: flex; flex-direction: column; gap: 9px;
      justify-content: center;
    }
    .bi-skel-line {
      border-radius: 2px;
      background: linear-gradient(90deg,#f5f2ec 25%,#ede9e0 50%,#f5f2ec 75%);
      background-size: 200% 100%;
      animation: biSkel 1.5s infinite;
    }
    @keyframes biSkel {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }

    /* ── ERROR ── */
    .bi-error {
      padding: 16px 20px;
      display: flex; align-items: center; gap: 10px;
      font-size: .82rem; font-family:'Outfit',sans-serif;
      color: #f87171; background: rgba(248,113,113,.06);
      border-left: 3px solid #f87171;
    }

    /* responsive */
    @media (max-width: 560px) {
      .bi-row { grid-template-columns: 72px 1fr auto; }
      .bi-right { padding: 14px 14px; }
      .bi-info { padding: 14px 14px; }
      .bi-qty  { padding: 0 12px; }
      .bi-name { max-width: 160px; }
      .bi-desc { display: none; }
    }
  `}</style>
);

export default function BookingItem({ itemKey, qty, refresh }) {
  console.log("itemkey", itemKey);
  const [item, setItem]     = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    if (status === "loading") {
      axios
        .get(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection/getOne/${itemKey}`)
        .then((res) => {
          setItem(res.data);
          setStatus("success");
          console.log(res.data);
        })
        .catch((err) => {
          console.log(err);
          setStatus("error");
          removeFromCart(itemKey);
          refresh();
        });
    }
  }, [status, itemKey, refresh]);

  /* ── skeleton ── */
  if (status === "loading") {
    return (
      <>
        <BookingItemStyles />
        <div className="bi-skel">
          <div className="bi-skel-img" />
          <div className="bi-skel-body">
            <div className="bi-skel-line" style={{ height: 16, width: "55%" }} />
            <div className="bi-skel-line" style={{ height: 12, width: "80%" }} />
            <div className="bi-skel-line" style={{ height: 12, width: "35%" }} />
          </div>
        </div>
      </>
    );
  }

  /* ── error ── */
  if (status === "error") {
    return (
      <>
        <BookingItemStyles />
        <div className="bi-error">
          ⚠ Failed to load item. It has been removed from your cart.
        </div>
      </>
    );
  }

  const unitPrice  = parseFloat(item?.price) || 0;
  const totalPrice = (unitPrice * qty).toFixed(2);

  return (
    <>
      <BookingItemStyles />
      <div className="bi-row">

        {/* ── Image ── */}
        <div className="bi-img-wrap">
          <img
            className="bi-img"
            src={
              item?.images?.[0] ||
              "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=200&auto=format&fit=crop"
            }
            alt={item?.name}
            onError={(e) => {
              e.target.src =
                "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=200&auto=format&fit=crop";
            }}
          />
        </div>

        {/* ── Info ── */}
        <div className="bi-info">
          <h3 className="bi-name">{item?.name}</h3>
          <p className="bi-desc">{item?.description}</p>
          <p className="bi-unit-price">
            Unit price: <strong>Rs.{unitPrice.toFixed(2)}</strong>
          </p>
        </div>

        {/* ── Qty Controls ── */}
        <div className="bi-qty">
          <button
            className="bi-qty-btn"
            onClick={() => { addToCart(itemKey, 1); refresh(); }}
            aria-label="Increase quantity"
          >
            <AiFillUpSquare />
          </button>

          <span className="bi-qty-num">{qty}</span>

          <button
            className={`bi-qty-btn ${qty === 1 ? "danger" : ""}`}
            onClick={() => {
              if (qty === 1) {
                removeFromCart(itemKey);
              } else {
                addToCart(itemKey, -1);
              }
              refresh();
            }}
            aria-label="Decrease quantity"
          >
            <AiFillDownSquare />
          </button>
        </div>

        {/* ── Total + Delete ── */}
        <div className="bi-right">
          <div className="bi-total">
            <span>Rs.</span>{totalPrice}
          </div>
          <button
            className="bi-delete"
            onClick={() => { removeFromCart(itemKey); refresh(); }}
            aria-label="Remove item"
          >
            <MdDeleteForever />
          </button>
        </div>

      </div>
    </>
  );
}