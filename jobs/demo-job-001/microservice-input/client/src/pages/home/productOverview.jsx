import axios from "axios";
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ImageSlider from "../../components/imageSlider";
import { addToCart, LoadCart } from "../../utils/card";
import toast from "react-hot-toast";
import { Rating } from "@smastrom/react-rating";
import "@smastrom/react-rating/style.css";
import Footer from "../../components/footer";

/* ── Styles ── */
const OverviewStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .ov-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; min-height:100vh; }

    /* ── LOADING / ERROR ── */
    .ov-state {
      min-height:70vh; display:flex; flex-direction:column;
      align-items:center; justify-content:center; gap:20px; text-align:center;
    }
    .ov-spinner {
      width:48px; height:48px; border-radius:50%;
      border:2px solid #f0ece4; border-top-color:#F59E0B;
      animation:ovSpin .8s linear infinite;
    }
    @keyframes ovSpin { to { transform:rotate(360deg); } }
    .ov-state-title {
      font-family:'Cormorant Garamond',serif;
      font-size:1.6rem; font-weight:300; color:#aaa; font-style:italic;
    }
    .ov-err { color:#f87171; }

    /* ── HERO STRIP ── */
    .ov-hero {
      position:relative; width:100%; height:260px; overflow:hidden; background:#111;
    }
    .ov-hero-img {
      width:100%; height:100%; object-fit:cover; filter:brightness(.28);
      transform:scale(1.04); animation:ovZoom 9s ease forwards;
    }
    @keyframes ovZoom { to { transform:scale(1); } }
    .ov-hero-body {
      position:absolute; inset:0;
      display:flex; flex-direction:column;
      align-items:center; justify-content:center;
      text-align:center; padding:0 20px;
      animation:ovUp .85s ease both;
    }
    @keyframes ovUp {
      from { opacity:0; transform:translateY(22px); }
      to   { opacity:1; transform:none; }
    }
    .ov-eyebrow {
      font-size:.7rem; letter-spacing:.38em; text-transform:uppercase;
      color:#F59E0B; font-weight:400; margin-bottom:10px;
    }
    .ov-hero-title {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(2rem,5vw,4rem); font-weight:300; color:#fff; line-height:1.1;
    }
    .ov-hero-title em { font-style:italic; color:#F59E0B; }

    /* ── BODY ── */
    .ov-body { max-width:1100px; margin:0 auto; padding:72px 24px 100px; }

    /* ── PRODUCT SECTION ── */
    .ov-product {
      display:grid; grid-template-columns:1fr 1fr; gap:56px;
      align-items:start; margin-bottom:72px;
    }
    @media(max-width:768px) {
      .ov-product { grid-template-columns:1fr; gap:36px; }
    }

    /* slider wrapper */
    .ov-slider-wrap {
      border:1px solid #f0ece4;
      overflow:hidden;
      box-shadow:0 8px 40px rgba(0,0,0,.07);
    }

    /* product info */
    .ov-info {}
    .ov-section-label {
      font-size:.68rem; letter-spacing:.32em; text-transform:uppercase;
      color:#F59E0B; font-weight:400; margin-bottom:10px; display:block;
    }
    .ov-product-title {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(2rem,4vw,3rem); font-weight:300; color:#111;
      line-height:1.1; margin-bottom:20px;
    }
    .ov-product-title em { font-style:italic; color:#F59E0B; }

    .ov-meta-row {
      display:flex; flex-wrap:wrap; gap:12px; margin-bottom:24px;
    }
    .ov-meta-chip {
      display:inline-flex; align-items:center; gap:6px;
      padding:7px 16px; border:1.5px solid #f0ece4;
      font-size:.75rem; font-weight:500; letter-spacing:.06em;
      text-transform:uppercase; color:#666;
      background:#FAFAF8;
    }
    .ov-meta-chip.gold { border-color:#F59E0B; color:#F59E0B; background:#fffbf0; }
    .ov-meta-chip.green { border-color:rgba(74,222,128,.4); color:#4ade80; background:rgba(74,222,128,.04); }
    .ov-meta-chip.red   { border-color:rgba(248,113,113,.4); color:#f87171; background:rgba(248,113,113,.04); }

    .ov-price {
      font-family:'Cormorant Garamond',serif;
      font-size:2.8rem; font-weight:300; color:#111;
      line-height:1; margin-bottom:6px;
    }
    .ov-price span { font-size:1.2rem; vertical-align:super; color:#aaa; font-weight:300; }

    .ov-desc {
      font-size:.92rem; color:#777; font-weight:300;
      line-height:1.75; margin-top:20px; margin-bottom:32px;
      padding-left:14px; border-left:2px solid #F59E0B;
    }

    /* Add to cart */
    .ov-atc {
      display:inline-flex; align-items:center; gap:10px;
      padding:16px 40px; background:#111; color:#fff;
      font-family:'Outfit',sans-serif;
      font-size:.85rem; font-weight:600;
      letter-spacing:.1em; text-transform:uppercase;
      border:1.5px solid #111; cursor:pointer;
      transition:background .24s,color .24s,border-color .24s,transform .2s;
    }
    .ov-atc:hover {
      background:#F59E0B; color:#111; border-color:#F59E0B;
      transform:translateY(-2px);
    }
    .ov-atc-icon { font-size:1.1rem; }

    /* ── RESTAURANT CARD ── */
    .ov-rest-section { margin-bottom:72px; }
    .ov-rest-head { margin-bottom:28px; }
    .ov-rest-title {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(1.6rem,3vw,2.4rem); font-weight:300; color:#111;
    }

    .ov-rest-card {
      display:grid; grid-template-columns:1fr 340px; gap:2px;
      border:1px solid #f0ece4; overflow:hidden;
      box-shadow:0 8px 40px rgba(0,0,0,.06);
    }
    @media(max-width:768px) { .ov-rest-card { grid-template-columns:1fr; } }

    .ov-rest-info {
      padding:36px 36px; background:#FAFAF8;
      display:flex; flex-direction:column; gap:0;
    }
    @media(max-width:480px) { .ov-rest-info { padding:24px 20px; } }

    .ov-rest-name {
      font-family:'Cormorant Garamond',serif;
      font-size:1.8rem; font-weight:400; color:#111;
      margin-bottom:20px; line-height:1.1;
    }
    .ov-rest-row {
      display:flex; align-items:flex-start; gap:12px;
      padding:12px 0; border-bottom:1px solid #eee8dc;
    }
    .ov-rest-row:last-of-type { border-bottom:none; }
    .ov-rest-icon { color:#F59E0B; font-size:1rem; flex-shrink:0; margin-top:1px; }
    .ov-rest-row-label {
      font-size:.65rem; letter-spacing:.2em; text-transform:uppercase;
      color:#bbb; font-weight:400; display:block; margin-bottom:2px;
    }
    .ov-rest-row-value { font-size:.9rem; font-weight:500; color:#333; }

    .ov-rest-btn {
      margin-top:28px; display:inline-flex; align-items:center; gap:8px;
      padding:13px 32px; background:transparent;
      border:1.5px solid #F59E0B; color:#F59E0B;
      font-family:'Outfit',sans-serif;
      font-size:.78rem; font-weight:600;
      letter-spacing:.1em; text-transform:uppercase;
      cursor:pointer;
      transition:background .24s,color .24s;
    }
    .ov-rest-btn:hover { background:#F59E0B; color:#111; }

    .ov-rest-img-wrap {
      position:relative; overflow:hidden; background:#111;
      min-height:260px;
    }
    .ov-rest-img {
      width:100%; height:100%; object-fit:cover;
      filter:brightness(.7);
      transition:transform .65s cubic-bezier(.25,.46,.45,.94), filter .4s;
    }
    .ov-rest-card:hover .ov-rest-img { transform:scale(1.06); filter:brightness(.5); }
    .ov-rest-no-img {
      width:100%; height:100%; min-height:260px;
      display:flex; align-items:center; justify-content:center;
      color:#aaa; font-size:.85rem; font-weight:300; background:#f5f2ec;
    }

    /* ── REVIEWS ── */
    .ov-reviews-section { }
    .ov-reviews-head { margin-bottom:36px; }
    .ov-reviews-title {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(1.6rem,3vw,2.4rem); font-weight:300; color:#111;
    }

    .ov-review-list { display:flex; flex-direction:column; gap:16px; margin-bottom:48px; }

    .ov-review-card {
      padding:28px 28px; border:1px solid #f0ece4; background:#FAFAF8;
      transition:box-shadow .3s,border-color .3s;
    }
    .ov-review-card:hover { box-shadow:0 8px 32px rgba(0,0,0,.06); border-color:#e5e0d5; }

    .ov-review-top { display:flex; align-items:center; gap:14px; margin-bottom:14px; }
    .ov-review-avatar {
      width:44px; height:44px; border-radius:50%; object-fit:cover;
      border:2px solid #F59E0B; flex-shrink:0;
    }
    .ov-review-name { font-weight:600; font-size:.92rem; color:#111; }
    .ov-review-date { font-size:.75rem; color:#bbb; font-weight:300; margin-top:2px; }
    .ov-review-comment {
      font-size:.9rem; color:#666; font-weight:300;
      line-height:1.7; margin-top:10px;
    }

    .ov-no-reviews {
      padding:40px; text-align:center;
      border:1px dashed #e8e4da; color:#bbb;
      font-family:'Cormorant Garamond',serif;
      font-size:1.3rem; font-weight:300; font-style:italic;
      margin-bottom:48px;
    }

    /* Write review form */
    .ov-write-review {
      border:1px solid #f0ece4; padding:40px;
      background:#fff; box-shadow:0 4px 24px rgba(0,0,0,.05);
    }
    @media(max-width:480px) { .ov-write-review { padding:24px 20px; } }

    .ov-write-title {
      font-family:'Cormorant Garamond',serif;
      font-size:1.7rem; font-weight:400; color:#111;
      margin-bottom:6px;
    }
    .ov-write-sub {
      font-size:.85rem; color:#aaa; font-weight:300; margin-bottom:28px; line-height:1.6;
    }
    .ov-rating-label {
      font-size:.68rem; letter-spacing:.28em; text-transform:uppercase;
      color:#888; font-weight:400; margin-bottom:10px; display:block;
    }
    .ov-textarea {
      width:100%; margin-top:24px; padding:16px 18px;
      border:1.5px solid #e8e4da; background:#FAFAF8;
      font-family:'Outfit',sans-serif;
      font-size:.9rem; font-weight:300; color:#333;
      resize:vertical; outline:none; line-height:1.7;
      transition:border-color .25s,box-shadow .25s,background .25s;
    }
    .ov-textarea::placeholder { color:#ccc; }
    .ov-textarea:focus {
      border-color:#F59E0B;
      box-shadow:0 0 0 3px rgba(245,158,11,.1);
      background:#fff;
    }
    .ov-submit {
      margin-top:16px; display:inline-flex; align-items:center; gap:8px;
      padding:15px 40px; background:#F59E0B; color:#111;
      font-family:'Outfit',sans-serif;
      font-size:.82rem; font-weight:600;
      letter-spacing:.1em; text-transform:uppercase;
      border:none; cursor:pointer;
      transition:background .24s,color .24s,transform .2s;
    }
    .ov-submit:hover { background:#111; color:#F59E0B; transform:translateY(-2px); }

    @media(max-width:640px) {
      .ov-hero { height:220px; }
      .ov-body  { padding:48px 16px 80px; }
    }
  `}</style>
);

export default function FoodItemOverview() {
  const { key } = useParams();
  const navigate = useNavigate();

  const [loadingStatus, setLoadingStatus] = useState("loading");
  const [foodItem, setFoodItem]           = useState({});
  const [restaurant, setRestaurant]       = useState(null);
  const [reviews, setReviews]             = useState([]);
  const [userRating, setUserRating]       = useState(0);
  const [userComment, setUserComment]     = useState("");
  const [refresh, setRefresh]             = useState(false);

  useEffect(() => {
    axios
      .get(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection/getOne/${key}`)
      .then((res) => {
        setFoodItem(res.data);
        setLoadingStatus("Loaded");
        if (res.data.restaurantId) {
          axios
            .get(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant/getOne/${res.data.restaurantId}`)
            .then((r) => setRestaurant(r.data))
            .catch((err) => console.error("Failed to load restaurant", err));
        }
      })
      .catch((err) => { console.error(err); setLoadingStatus("error"); });

    axios
      .get(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/reviews/${key}`)
      .then((res) => setReviews(res.data))
      .catch((err) => console.error(err));
  }, [refresh]);

  const handleAddReview = async () => {
    setRefresh(false);
    const token = localStorage.getItem("token");
    if (!token) { toast.error("Please log in to submit a review."); return; }
    try {
      const response = await axios.post(
        `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/reviews`,
        {
          productId: key,
          rating: userRating,
          comment: userComment,
          ownerId: restaurant.ownerId,
          restaurantName: restaurant.name,
          itemName: foodItem.name,
        },
        { headers: { Authorization: "Bearer " + token } }
      );
      setReviews((prev) => [...prev, response.data]);
      setUserRating(0);
      setUserComment("");
      toast.success("Review submitted successfully.");
      setRefresh(true);
    } catch (error) {
      console.error("Error submitting review:", error);
      toast.error("Failed to submit review.");
    }
  };

  /* ── hero bg: first food image or unsplash fallback ── */
  const heroBg =
    foodItem.images?.[0] ||
    "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1800&auto=format&fit=crop";

  return (
    <div className="ov-root">
      <OverviewStyles />

      {/* ── LOADING ── */}
      {loadingStatus === "loading" && (
        <div className="ov-state">
          <div className="ov-spinner" />
          <p className="ov-state-title">Loading dish details…</p>
        </div>
      )}

      {/* ── ERROR ── */}
      {loadingStatus === "error" && (
        <div className="ov-state">
          <p className="ov-state-title ov-err">
            Failed to load food details. Please try again later.
          </p>
        </div>
      )}

      {/* ── LOADED ── */}
      {loadingStatus === "Loaded" && (
        <>
          {/* Hero strip */}
          <section className="ov-hero">
            <img className="ov-hero-img" src={heroBg} alt={foodItem.name} />
            <div className="ov-hero-body">
              <p className="ov-eyebrow">FoodRush · Dish</p>
              <h1 className="ov-hero-title">
                <em>{foodItem.name}</em>
              </h1>
            </div>
          </section>

          <div className="ov-body">

            {/* ── PRODUCT DETAILS ── */}
            <div className="ov-product">
              {/* Image slider */}
              <div className="ov-slider-wrap">
                <ImageSlider images={foodItem.images} />
              </div>

              {/* Info */}
              <div className="ov-info">
                <span className="ov-section-label">Dish Details</span>
                <h2 className="ov-product-title">
                  {foodItem.name}
                </h2>

                {/* Meta chips */}
                <div className="ov-meta-row">
                  {foodItem.category && (
                    <span className="ov-meta-chip">
                      🍽 {foodItem.category}
                    </span>
                  )}
                  <span className={`ov-meta-chip ${foodItem.available ? "green" : "red"}`}>
                    {foodItem.available ? "✓ Available" : "✗ Unavailable"}
                  </span>
                </div>

                {/* Price */}
                <div className="ov-price">
                  <span>Rs.</span>
                  {parseFloat(foodItem.price).toFixed(2)}
                </div>

                {/* Description */}
                {foodItem.description && (
                  <p className="ov-desc">{foodItem.description}</p>
                )}

                {/* Add to cart */}
                <button
                  className="ov-atc"
                  onClick={() => {
                    addToCart(foodItem._id, 1);
                    toast.success("Added to Cart");
                    console.log(LoadCart());
                  }}
                >
                  <span className="ov-atc-icon">🛒</span>
                  Add to Cart
                </button>
              </div>
            </div>

            {/* ── RESTAURANT INFO ── */}
            {restaurant && (
              <div className="ov-rest-section">
                <div className="ov-rest-head">
                  <span className="ov-section-label">Served by</span>
                  <h2 className="ov-rest-title">About the Restaurant</h2>
                </div>

                <div className="ov-rest-card">
                  {/* Text */}
                  <div className="ov-rest-info">
                    <h3 className="ov-rest-name">{restaurant.name}</h3>

                    <div className="ov-rest-row">
                      <span className="ov-rest-icon">👤</span>
                      <div>
                        <span className="ov-rest-row-label">Owner</span>
                        <span className="ov-rest-row-value">{restaurant.ownerName}</span>
                      </div>
                    </div>
                    <div className="ov-rest-row">
                      <span className="ov-rest-icon">📍</span>
                      <div>
                        <span className="ov-rest-row-label">Address</span>
                        <span className="ov-rest-row-value">{restaurant.address}</span>
                      </div>
                    </div>
                    <div className="ov-rest-row">
                      <span className="ov-rest-icon">📞</span>
                      <div>
                        <span className="ov-rest-row-label">Phone</span>
                        <span className="ov-rest-row-value">{restaurant.phone}</span>
                      </div>
                    </div>

                    <button
                      className="ov-rest-btn"
                      onClick={() => {
                        if (restaurant?._id) {
                          navigate(`/restaurant/${restaurant._id}`, {
                            state: { packageDetails: restaurant },
                          });
                        } else {
                          toast.error("Restaurant details are not available.");
                        }
                      }}
                    >
                      View Restaurant →
                    </button>
                  </div>

                  {/* Image */}
                  <div className="ov-rest-img-wrap">
                    {restaurant.images?.length > 0 ? (
                      <img
                        className="ov-rest-img"
                        src={restaurant.images[0]}
                        alt={restaurant.name}
                      />
                    ) : (
                      <div className="ov-rest-no-img">No image available</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ── REVIEWS ── */}
            <div className="ov-reviews-section">
              <div className="ov-reviews-head">
                <span className="ov-section-label">What people say</span>
                <h2 className="ov-reviews-title">Customer Reviews</h2>
              </div>

              {/* Review list */}
              {reviews.length > 0 ? (
                <div className="ov-review-list">
                  {reviews.map((review) => (
                    <div key={review._id} className="ov-review-card">
                      <div className="ov-review-top">
                        <img
                          className="ov-review-avatar"
                          src={review.profilePicture}
                          alt={review.name}
                          onError={(e) => {
                            e.target.src =
                              "https://images.unsplash.com/photo-1527980965255-d3b416303d12?w=96&h=96&auto=format&fit=crop&crop=face";
                          }}
                        />
                        <div>
                          <p className="ov-review-name">{review.name}</p>
                          <p className="ov-review-date">
                            {new Date(review.data).toLocaleDateString("en-US", {
                              year: "numeric", month: "long", day: "numeric",
                            })}
                          </p>
                        </div>
                        <div style={{ marginLeft: "auto" }}>
                          <Rating style={{ maxWidth: 90 }} value={review.rating} readOnly />
                        </div>
                      </div>
                      <p className="ov-review-comment">{review.comment}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="ov-no-reviews">
                  No reviews yet — be the first to share your experience.
                </div>
              )}

              {/* Write review */}
              <div className="ov-write-review">
                <span className="ov-section-label">Share your experience</span>
                <h3 className="ov-write-title">Write a Review</h3>
                <p className="ov-write-sub">
                  Your feedback helps others discover great food.
                </p>

                <span className="ov-rating-label">Your Rating</span>
                <Rating
                  style={{ maxWidth: 140 }}
                  value={userRating}
                  onChange={setUserRating}
                />

                <textarea
                  className="ov-textarea"
                  rows={4}
                  placeholder="Share your experience with this dish…"
                  value={userComment}
                  onChange={(e) => setUserComment(e.target.value)}
                />

                <button className="ov-submit" onClick={handleAddReview}>
                  Submit Review →
                </button>
              </div>
            </div>

          </div>
        </>
      )}

      <Footer />
    </div>
  );
}