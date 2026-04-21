import axios from "axios";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import ProductCard from "../../components/productCard";
import Footer from "../../components/footer";

/* ── Styles ── */
const ItemStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .it-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; }

    /* ── HERO ── */
    .it-hero {
      position: relative; width: 100%; height: 340px; overflow: hidden;
    }
    .it-hero-img {
      width: 100%; height: 100%; object-fit: cover; object-position: center;
      filter: brightness(.3);
      transform: scale(1.05);
      animation: itZoom 9s ease forwards;
    }
    @keyframes itZoom { to { transform: scale(1); } }
    .it-hero-body {
      position: absolute; inset: 0;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      text-align: center; padding: 0 20px;
      animation: itUp .85s ease both;
    }
    @keyframes itUp {
      from { opacity:0; transform:translateY(24px); }
      to   { opacity:1; transform:none; }
    }
    .it-eyebrow {
      font-size: .72rem; letter-spacing: .38em; text-transform: uppercase;
      color: #F59E0B; font-weight: 400; margin-bottom: 14px;
    }
    .it-hero-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: clamp(2.8rem, 6vw, 5rem);
      font-weight: 300; color: #fff; line-height: 1.1;
    }
    .it-hero-title em { font-style: italic; color: #F59E0B; }
    .it-hero-sub {
      color: rgba(255,255,255,.65); font-size: .95rem; font-weight: 300;
      margin-top: 12px; max-width: 440px; line-height: 1.75;
    }

    /* ── TOOLBAR ── */
    .it-toolbar {
      max-width: 1240px; margin: 0 auto;
      padding: 48px 24px 0;
      display: flex; align-items: center; justify-content: space-between;
      flex-wrap: wrap; gap: 20px;
    }

    /* Search */
    .it-search-wrap {
      position: relative; flex: 1; min-width: 220px; max-width: 420px;
    }
    .it-search-icon {
      position: absolute; left: 16px; top: 50%; transform: translateY(-50%);
      font-size: 1rem; color: #bbb; pointer-events: none;
    }
    .it-search {
      width: 100%; padding: 14px 18px 14px 44px;
      border: 1.5px solid #e8e4da;
      background: #FAFAF8;
      font-family: 'Outfit', sans-serif;
      font-size: .88rem; font-weight: 300; color: #333;
      outline: none;
      transition: border-color .25s, box-shadow .25s, background .25s;
    }
    .it-search::placeholder { color: #bbb; }
    .it-search:focus {
      border-color: #F59E0B;
      box-shadow: 0 0 0 3px rgba(245,158,11,.1);
      background: #fff;
    }

    /* Filter chips */
    .it-filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .it-filter-label {
      font-size: .68rem; letter-spacing: .28em; text-transform: uppercase;
      color: #bbb; font-weight: 400; margin-right: 4px;
    }
    .it-chip-wrap { position: relative; }
    .it-chip-input {
      position: absolute; opacity: 0; width: 0; height: 0;
    }
    .it-chip {
      display: inline-flex; align-items: center; gap: 7px;
      padding: 9px 18px;
      border: 1.5px solid #e8e4da;
      background: #fff;
      font-family: 'Outfit', sans-serif;
      font-size: .78rem; font-weight: 500;
      letter-spacing: .07em; text-transform: uppercase;
      color: #888; cursor: pointer;
      transition: border-color .22s, background .22s, color .22s, box-shadow .22s;
      user-select: none;
    }
    .it-chip:hover { border-color: #F59E0B; color: #F59E0B; }
    .it-chip-input:checked + .it-chip {
      background: #F59E0B; border-color: #F59E0B;
      color: #111; box-shadow: 0 4px 16px rgba(245,158,11,.25);
    }
    .it-chip-dot {
      width: 6px; height: 6px; border-radius: 50%;
      background: currentColor; opacity: .6;
      transition: opacity .2s;
    }
    .it-chip-input:checked + .it-chip .it-chip-dot { opacity: 1; }

    /* Results count */
    .it-meta-row {
      max-width: 1240px; margin: 0 auto;
      padding: 24px 24px 0;
      display: flex; align-items: center; justify-content: space-between;
      border-bottom: 1px solid #f0ece4; padding-bottom: 20px;
    }
    .it-result-count {
      font-size: .78rem; color: #aaa; font-weight: 300;
    }
    .it-result-count strong { color: #F59E0B; font-weight: 600; }
    .it-section-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.1rem; font-weight: 400; color: #333; font-style: italic;
    }

    /* ── GRID ── */
    .it-grid {
      max-width: 1240px; margin: 0 auto;
      padding: 40px 24px 80px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 24px;
    }

    /* ── LOADING SPINNER ── */
    .it-loading {
      grid-column: 1/-1;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 80px 0; gap: 20px;
    }
    .it-spinner {
      width: 44px; height: 44px; border-radius: 50%;
      border: 2px solid #f0ece4;
      border-top-color: #F59E0B;
      animation: itSpin .8s linear infinite;
    }
    @keyframes itSpin { to { transform: rotate(360deg); } }
    .it-loading-text {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.4rem; font-weight: 300; color: #aaa; font-style: italic;
    }

    /* ── SKELETON ── */
    .it-skel {
      border: 1px solid #f0ece4; overflow: hidden;
    }
    .it-skel-img {
      width: 100%; aspect-ratio: 4/3;
      background: linear-gradient(90deg, #f5f2ec 25%, #ede9e0 50%, #f5f2ec 75%);
      background-size: 200% 100%;
      animation: itSkelAnim 1.5s infinite;
    }
    .it-skel-body { padding: 18px; display: flex; flex-direction: column; gap: 10px; }
    .it-skel-line {
      border-radius: 2px;
      background: linear-gradient(90deg, #f5f2ec 25%, #ede9e0 50%, #f5f2ec 75%);
      background-size: 200% 100%;
      animation: itSkelAnim 1.5s infinite;
    }
    @keyframes itSkelAnim {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }

    /* ── EMPTY STATE ── */
    .it-empty {
      grid-column: 1/-1;
      padding: 80px 0; text-align: center;
    }
    .it-empty-icon { font-size: 3.5rem; opacity: .2; margin-bottom: 16px; }
    .it-empty-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: 2rem; font-weight: 300; color: #555;
    }
    .it-empty-sub { font-size: .88rem; color: #bbb; font-weight: 300; margin-top: 6px; }

    @media (max-width: 640px) {
      .it-hero { height: 280px; }
      .it-toolbar { flex-direction: column; align-items: stretch; }
      .it-search-wrap { max-width: 100%; }
    }
  `}</style>
);

/* ── Skeleton Card ── */
function SkeletonCard() {
  return (
    <div className="it-skel">
      <div className="it-skel-img" />
      <div className="it-skel-body">
        <div className="it-skel-line" style={{ height: 20, width: "70%" }} />
        <div className="it-skel-line" style={{ height: 13, width: "100%" }} />
        <div className="it-skel-line" style={{ height: 13, width: "80%" }} />
      </div>
    </div>
  );
}

const FILTERS = [
  { value: "fastfood",    label: "Fast Food"    },
  { value: "familymeals", label: "Family Meals" },
  { value: "dessert",     label: "Dessert"      },
];

export default function Item() {
  const [state, setState]               = useState("loading");
  const [items, setItems]               = useState([]);
  const [filteredItems, setFilteredItems] = useState([]);
  const [searchTerm, setSearchTerm]     = useState("");
  const [categoryFilters, setCategoryFilters] = useState([]);

  useEffect(() => {
    if (state === "loading") {
      axios
        .get(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection`)
        .then((res) => {
          const allItems = res.data;
          setItems(allItems);
          setFilteredItems(allItems);
          setState("success");
          console.log(res);
        })
        .catch((err) => {
          toast.error(err?.response?.data?.error || "An error occurred");
          setState("error");
        });
    }
  }, []);

  const handleSearch = (e) => {
    const value = e.target.value.toLowerCase();
    setSearchTerm(value);
    filterItems(value, categoryFilters);
  };

  const handleFilterChange = (e) => {
    const { value, checked } = e.target;
    const updatedFilters = checked
      ? [...categoryFilters, value]
      : categoryFilters.filter((c) => c !== value);
    setCategoryFilters(updatedFilters);
    filterItems(searchTerm, updatedFilters);
  };

  const filterItems = (searchValue, selectedCategories) => {
    let filtered = items;
    if (searchValue) {
      filtered = filtered.filter((item) =>
        item.name.toLowerCase().includes(searchValue)
      );
    }
    if (selectedCategories.length > 0) {
      filtered = filtered.filter((item) =>
        selectedCategories.includes(item.category?.toLowerCase())
      );
    }
    setFilteredItems(filtered);
  };

  return (
    <div className="it-root">
      <ItemStyles />

      {/* ── HERO ── */}
      <section className="it-hero">
        <img
          className="it-hero-img"
          src="https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=1800&auto=format&fit=crop"
          alt="Food items"
        />
        <div className="it-hero-body">
          <p className="it-eyebrow">Browse the collection</p>
          <h1 className="it-hero-title">
            All <em>Items</em>
          </h1>
          <p className="it-hero-sub">
            Search, filter, and discover your next favourite meal from
            our full collection of dishes.
          </p>
        </div>
      </section>

      {/* ── TOOLBAR ── */}
      <div className="it-toolbar">
        {/* Search */}
        <div className="it-search-wrap">
          <span className="it-search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search items…"
            value={searchTerm}
            onChange={handleSearch}
            className="it-search"
          />
        </div>

        {/* Filter chips */}
        <div className="it-filters">
          <span className="it-filter-label">Filter</span>
          {FILTERS.map(({ value, label }) => (
            <div className="it-chip-wrap" key={value}>
              <input
                type="checkbox"
                id={`chip-${value}`}
                className="it-chip-input"
                value={value}
                onChange={handleFilterChange}
              />
              <label htmlFor={`chip-${value}`} className="it-chip">
                <span className="it-chip-dot" />
                {label}
              </label>
            </div>
          ))}
        </div>
      </div>

      {/* ── META ROW ── */}
      {state === "success" && (
        <div className="it-meta-row">
          <p className="it-result-count">
            Showing <strong>{filteredItems.length}</strong> of {items.length} items
          </p>
          <span className="it-section-title">
            {categoryFilters.length > 0
              ? categoryFilters.join(", ")
              : searchTerm
              ? `"${searchTerm}"`
              : "All dishes"}
          </span>
        </div>
      )}

      {/* ── GRID ── */}
      <div className="it-grid">

        {/* Loading skeletons */}
        {state === "loading" &&
          Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)
        }

        {/* Empty state */}
        {state === "success" && filteredItems.length === 0 && (
          <div className="it-empty">
            <div className="it-empty-icon">🍽️</div>
            <h3 className="it-empty-title">No items found</h3>
            <p className="it-empty-sub">
              Try adjusting your search or clearing the filters.
            </p>
          </div>
        )}

        {/* Items */}
        {state === "success" &&
          filteredItems.map((item) => (
            <div key={item._id || item.key}>
              <ProductCard item={item} />
            </div>
          ))
        }
      </div>

      <Footer />
    </div>
  );
}