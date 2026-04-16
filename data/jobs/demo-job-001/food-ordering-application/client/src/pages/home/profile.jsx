import { useEffect, useRef, useState } from "react";
import axios from "axios";
import Swal from "sweetalert2";
import mediaUpload from "../../utils/mediaUpload";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

/* ── Styles ── */
const ProfileStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .pf-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; min-height:100vh; }

    /* ── HERO BANNER ── */
    .pf-hero {
      position:relative; width:100%; height:300px; overflow:hidden; background:#111;
    }
    .pf-hero-img {
      width:100%; height:100%; object-fit:cover; filter:brightness(.25);
      transform:scale(1.04); animation:pfZoom 9s ease forwards;
    }
    @keyframes pfZoom { to { transform:scale(1); } }
    .pf-hero-body {
      position:absolute; inset:0;
      display:flex; flex-direction:column; align-items:center; justify-content:flex-end;
      padding-bottom:0;
    }
    /* avatar sits on the seam between hero and body */
    .pf-avatar-ring {
      width:110px; height:110px; border-radius:50%;
      border:3px solid #F59E0B;
      overflow:hidden; cursor:pointer;
      background:#f5f2ec;
      box-shadow:0 8px 32px rgba(0,0,0,.25);
      transform:translateY(55px);
      transition:box-shadow .3s, transform .3s;
      flex-shrink:0;
    }
    .pf-avatar-ring:hover {
      box-shadow:0 0 0 5px rgba(245,158,11,.3), 0 8px 32px rgba(0,0,0,.25);
      transform:translateY(55px) scale(1.04);
    }
    .pf-avatar-img { width:100%; height:100%; object-fit:cover; }
    .pf-avatar-overlay {
      position:absolute; inset:0; background:rgba(0,0,0,.45);
      display:flex; align-items:center; justify-content:center;
      opacity:0; transition:opacity .25s;
      border-radius:50%;
    }
    .pf-avatar-ring:hover .pf-avatar-overlay { opacity:1; }
    .pf-avatar-hint { font-size:.65rem; letter-spacing:.15em; text-transform:uppercase; color:#fff; font-weight:500; }

    /* ── BODY ── */
    .pf-body { max-width:1000px; margin:0 auto; padding:80px 24px 100px; }

    /* name + logout row */
    .pf-name-row {
      display:flex; align-items:center; justify-content:space-between;
      margin-bottom:56px; flex-wrap:wrap; gap:16px;
    }
    .pf-name-block {}
    .pf-eyebrow {
      font-size:.68rem; letter-spacing:.34em; text-transform:uppercase;
      color:#F59E0B; font-weight:400; margin-bottom:6px; display:block;
    }
    .pf-display-name {
      font-family:'Cormorant Garamond',serif;
      font-size:clamp(2rem,4vw,3rem); font-weight:300; color:#111; line-height:1.1;
    }
    .pf-display-name em { font-style:italic; color:#F59E0B; }
    .pf-logout {
      display:inline-flex; align-items:center; gap:7px;
      padding:10px 24px; border:1.5px solid #e5595a; color:#e5595a;
      font-family:'Outfit',sans-serif;
      font-size:.78rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      cursor:pointer; background:transparent;
      transition:background .22s,color .22s;
    }
    .pf-logout:hover { background:#e5595a; color:#fff; }

    /* ── SECTION CARD ── */
    .pf-card {
      border:1px solid #f0ece4; padding:40px;
      background:#fff; box-shadow:0 4px 28px rgba(0,0,0,.05);
      margin-bottom:32px;
    }
    @media(max-width:480px) { .pf-card { padding:24px 18px; } }
    .pf-card-label {
      font-size:.68rem; letter-spacing:.32em; text-transform:uppercase;
      color:#F59E0B; font-weight:400; margin-bottom:10px; display:block;
    }
    .pf-card-title {
      font-family:'Cormorant Garamond',serif;
      font-size:1.7rem; font-weight:400; color:#111; margin-bottom:28px;
    }

    /* ── FORM GRID ── */
    .pf-form-grid {
      display:grid; grid-template-columns:1fr 1fr; gap:16px;
    }
    @media(max-width:640px) { .pf-form-grid { grid-template-columns:1fr; } }
    .pf-form-full { grid-column:1/-1; }

    .pf-field { display:flex; flex-direction:column; gap:6px; }
    .pf-field-label {
      font-size:.65rem; letter-spacing:.24em; text-transform:uppercase;
      color:#bbb; font-weight:400;
    }
    .pf-input {
      padding:13px 16px;
      border:1.5px solid #e8e4da; background:#FAFAF8;
      font-family:'Outfit',sans-serif; font-size:.9rem; font-weight:300; color:#333;
      outline:none;
      transition:border-color .25s,box-shadow .25s,background .25s;
    }
    .pf-input::placeholder { color:#ccc; }
    .pf-input:focus {
      border-color:#F59E0B;
      box-shadow:0 0 0 3px rgba(245,158,11,.1); background:#fff;
    }
    .pf-input:disabled { background:#f5f5f2; color:#aaa; cursor:not-allowed; }

    .pf-addr-wrap { position:relative; }
    .pf-addr-btn {
      position:absolute; right:12px; top:50%; transform:translateY(-50%);
      font-size:.68rem; letter-spacing:.18em; text-transform:uppercase;
      color:#F59E0B; font-weight:600; background:transparent;
      border:none; cursor:pointer; padding:4px 8px;
      transition:color .2s;
    }
    .pf-addr-btn:hover { color:#111; }

    /* ── BUTTONS ── */
    .pf-btn-row { display:flex; gap:12px; flex-wrap:wrap; margin-top:28px; }
    .pf-btn-gold {
      display:inline-flex; align-items:center; gap:7px;
      padding:13px 32px; background:#F59E0B; color:#111;
      font-family:'Outfit',sans-serif;
      font-size:.8rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      border:none; cursor:pointer;
      transition:background .24s,color .24s,transform .2s;
    }
    .pf-btn-gold:hover { background:#111; color:#F59E0B; transform:translateY(-2px); }
    .pf-btn-red {
      display:inline-flex; align-items:center; gap:7px;
      padding:13px 32px; background:transparent; color:#e5595a;
      border:1.5px solid #e5595a;
      font-family:'Outfit',sans-serif;
      font-size:.8rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      cursor:pointer;
      transition:background .22s,color .22s;
    }
    .pf-btn-red:hover { background:#e5595a; color:#fff; }
    .pf-btn-outline {
      display:inline-flex; align-items:center; gap:7px;
      padding:13px 32px; background:transparent; color:#333;
      border:1.5px solid #e8e4da;
      font-family:'Outfit',sans-serif;
      font-size:.8rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
      cursor:pointer;
      transition:border-color .22s,color .22s;
    }
    .pf-btn-outline:hover { border-color:#111; color:#111; }

    /* ── DELIVERY HISTORY ── */
    .pf-delivery-list { display:flex; flex-direction:column; gap:16px; }
    .pf-delivery-card {
      border:1px solid #f0ece4; background:#FAFAF8; overflow:hidden;
      transition:box-shadow .3s,border-color .3s;
    }
    .pf-delivery-card:hover { box-shadow:0 8px 32px rgba(0,0,0,.06); border-color:#e5e0d5; }

    .pf-delivery-top {
      display:grid; grid-template-columns:72px 1fr auto;
      gap:20px; align-items:center; padding:22px 24px;
    }
    @media(max-width:560px) {
      .pf-delivery-top { grid-template-columns:56px 1fr; }
      .pf-delivery-actions { grid-column:1/-1; }
    }
    .pf-delivery-thumb {
      width:72px; height:72px; object-fit:cover; flex-shrink:0;
    }
    .pf-delivery-info {}
    .pf-delivery-name {
      font-family:'Cormorant Garamond',serif;
      font-size:1.2rem; font-weight:400; color:#111; margin-bottom:4px;
    }
    .pf-delivery-meta {
      font-size:.78rem; color:#888; font-weight:300; line-height:1.65;
    }
    .pf-delivery-meta strong { color:#555; font-weight:500; }
    .pf-status-badge {
      display:inline-block; padding:4px 12px;
      font-size:.62rem; letter-spacing:.18em; text-transform:uppercase; font-weight:600;
      border:1.5px solid;
    }
    .pf-status-badge.delivered { border-color:rgba(74,222,128,.5); color:#4ade80; }
    .pf-status-badge.pending   { border-color:rgba(245,158,11,.5);  color:#F59E0B; }
    .pf-status-badge.other     { border-color:rgba(148,163,184,.4); color:#94a3b8; }

    .pf-delivery-actions { display:flex; flex-direction:column; align-items:flex-end; gap:10px; }
    .pf-view-map {
      font-size:.72rem; letter-spacing:.16em; text-transform:uppercase;
      color:#F59E0B; font-weight:600; background:transparent;
      border:none; cursor:pointer; padding:0;
      display:flex; align-items:center; gap:5px;
      transition:color .2s;
    }
    .pf-view-map:hover { color:#111; }

    /* map container */
    .pf-map-wrap {
      border-top:1px solid #f0ece4;
      height:280px; width:100%;
    }

    /* ── LOADING ── */
    .pf-loading {
      min-height:60vh; display:flex; flex-direction:column;
      align-items:center; justify-content:center; gap:20px;
    }
    .pf-spinner {
      width:44px; height:44px; border-radius:50%;
      border:2px solid #f0ece4; border-top-color:#F59E0B;
      animation:pfSpin .8s linear infinite;
    }
    @keyframes pfSpin { to { transform:rotate(360deg); } }
    .pf-loading-text {
      font-family:'Cormorant Garamond',serif;
      font-size:1.4rem; font-weight:300; color:#aaa; font-style:italic;
    }

    .pf-empty {
      padding:40px; text-align:center;
      border:1px dashed #e8e4da;
      color:#ccc;
      font-family:'Cormorant Garamond',serif;
      font-size:1.2rem; font-weight:300; font-style:italic;
    }

    @media(max-width:640px) {
      .pf-body { padding:60px 16px 80px; }
    }
  `}</style>
);

/* ── status badge helper ── */
function StatusBadge({ status = "" }) {
  const cls =
    status.toLowerCase() === "delivered"
      ? "delivered"
      : status.toLowerCase() === "pending"
      ? "pending"
      : "other";
  return <span className={`pf-status-badge ${cls}`}>{status}</span>;
}

export function Profile() {
  const [user, setUser]           = useState(null);
  const fileInputRef              = useRef();
  const [formData, setFormData]   = useState({
    email: "", firstName: "", lastName: "", address: "", phone: "", image: "",
  });
  const [passwords, setPasswords] = useState({ oldPassword: "", newPassword: "" });

  const [deliveries, setDeliveries]               = useState([]);
  const [deliveriesLoading, setDeliveriesLoading] = useState(true);
  const [expandedDeliveryId, setExpandedDeliveryId] = useState(null);
  const mapRefs = useRef({});

  /* ── hydrate from localStorage ── */
  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      const parsed = JSON.parse(storedUser);
      setUser(parsed);
      setFormData({
        email: parsed.email, firstName: parsed.firstName,
        lastName: parsed.lastName, address: parsed.address,
        phone: parsed.phone, image: parsed.image,
      });
    }
  }, []);

  /* ── fetch deliveries ── */
  useEffect(() => {
    const fetchDeliveries = async () => {
      try {
        const token = localStorage.getItem("token");
        const response = await axios.get(
          `${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/delivery`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setDeliveries(response.data.filter((d) => d.customerEmail === user?.email));
      } catch {
        Swal.fire("Error", "Could not fetch delivery history.", "error");
      } finally {
        setDeliveriesLoading(false);
      }
    };
    if (user) fetchDeliveries();
  }, [user]);

  /* ── driver location ── */
  const handleDriverLocation = async (deliveryId) => {
    try {
      const res = await axios.get(
        `${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/delivery/loc/${deliveryId}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } }
      );
      const delivery = res.data;
      setDeliveries((prev) =>
        prev.map((d) => (d._id === deliveryId ? { ...d, lat: delivery.lat, lng: delivery.lng } : d))
      );
      setExpandedDeliveryId(deliveryId);
    } catch {
      Swal.fire("Error", "Could not fetch driver location.", "error");
    }
  };

  /* ── render map ── */
  useEffect(() => {
    if (expandedDeliveryId && mapRefs.current[expandedDeliveryId]) {
      const delivery = deliveries.find((d) => d._id === expandedDeliveryId);
      if (!delivery?.lat || !delivery?.lng) return;
      const mapContainer = mapRefs.current[expandedDeliveryId];
      mapContainer.innerHTML = "";
      const map = L.map(mapContainer).setView([delivery.lat, delivery.lng], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);
      L.marker([delivery.lat, delivery.lng]).addTo(map).bindPopup("Driver's Location").openPopup();
    }
  }, [expandedDeliveryId, deliveries]);

  const handleChange         = (e) => setFormData((p) => ({ ...p, [e.target.name]: e.target.value }));
  const handlePasswordChange = (e) => setPasswords((p) => ({ ...p, [e.target.name]: e.target.value }));

  const handleUpdate = async () => {
    try {
      const token = localStorage.getItem("token");
      await axios.put(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/update/${user.id}`,
        formData,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      Swal.fire("Success", "Profile updated!", "success");
      localStorage.setItem("user", JSON.stringify({ ...user, ...formData }));
      setUser({ ...user, ...formData });
    } catch {
      Swal.fire("Error", "Failed to update profile.", "error");
    }
  };

  const handleDelete = async () => {
    const confirm = await Swal.fire({
      title: "Delete your account?", icon: "warning",
      showCancelButton: true, confirmButtonText: "Yes, delete",
    });
    if (confirm.isConfirmed) {
      try {
        const token = localStorage.getItem("token");
        await axios.delete(
          `${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/${user.id}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        localStorage.clear();
        Swal.fire("Deleted", "Account removed.", "success");
        window.location.href = "/";
      } catch {
        Swal.fire("Error", "Delete failed.", "error");
      }
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const uploadedUrl = await mediaUpload(file);
      setFormData((p) => ({ ...p, image: uploadedUrl }));
      Swal.fire("Success", "Image uploaded.", "success");
    } catch {
      Swal.fire("Error", "Image upload failed.", "error");
    }
  };

  const getLocation = () => {
    navigator.geolocation?.getCurrentPosition(
      async ({ coords }) => {
        const res = await axios.get(
          `https://nominatim.openstreetmap.org/reverse?lat=${coords.latitude}&lon=${coords.longitude}&format=json`
        );
        setFormData((p) => ({ ...p, address: res.data?.display_name || "" }));
        Swal.fire("Success", "Location fetched!", "success");
      },
      () => Swal.fire("Error", "Geolocation not allowed or failed.", "error")
    );
  };

  const handleLogout = () => {
    localStorage.clear();
    Swal.fire("Logged out", "See you again!", "success");
    window.location.href = "/login";
  };

  const handleChangePassword = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.put(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/update/password/${user.id}`,
        passwords,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      Swal.fire("Success", res.data.message, "success");
      setPasswords({ oldPassword: "", newPassword: "" });
    } catch (err) {
      Swal.fire("Error", err.response?.data?.message || "Failed to change password", "error");
    }
  };

  /* ── loading ── */
  if (!user) {
    return (
      <div className="pf-root">
        <ProfileStyles />
        <div className="pf-loading">
          <div className="pf-spinner" />
          <p className="pf-loading-text">Loading your profile…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pf-root">
      <ProfileStyles />

      {/* ── HERO with avatar on seam ── */}
      <section className="pf-hero">
        <img
          className="pf-hero-img"
          src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1800&auto=format&fit=crop"
          alt="Profile background"
        />
        <div className="pf-hero-body">
          <div
            className="pf-avatar-ring"
            style={{ position: "relative" }}
            onClick={() => fileInputRef.current.click()}
          >
            <img
              className="pf-avatar-img"
              src={formData.image || "https://images.unsplash.com/photo-1527980965255-d3b416303d12?w=220&h=220&auto=format&fit=crop&crop=face"}
              alt="Profile"
            />
            <div className="pf-avatar-overlay">
              <span className="pf-avatar-hint">Change</span>
            </div>
          </div>
        </div>
      </section>
      <input type="file" ref={fileInputRef} onChange={handleImageUpload} className="hidden" />

      {/* ── BODY ── */}
      <div className="pf-body">

        {/* Name + logout */}
        <div className="pf-name-row">
          <div className="pf-name-block">
            <span className="pf-eyebrow">My Account</span>
            <h1 className="pf-display-name">
              {formData.firstName} <em>{formData.lastName}</em>
            </h1>
          </div>
          <button className="pf-logout" onClick={handleLogout}>
            ↩ Sign Out
          </button>
        </div>

        {/* ── PERSONAL INFO ── */}
        <div className="pf-card">
          <span className="pf-card-label">Personal information</span>
          <h2 className="pf-card-title">Edit Profile</h2>

          <div className="pf-form-grid">
            <div className="pf-field">
              <label className="pf-field-label">First Name</label>
              <input name="firstName" value={formData.firstName} onChange={handleChange}
                placeholder="First Name" className="pf-input" />
            </div>
            <div className="pf-field">
              <label className="pf-field-label">Last Name</label>
              <input name="lastName" value={formData.lastName} onChange={handleChange}
                placeholder="Last Name" className="pf-input" />
            </div>
            <div className="pf-field">
              <label className="pf-field-label">Email</label>
              <input name="email" value={formData.email} disabled className="pf-input" />
            </div>
            <div className="pf-field">
              <label className="pf-field-label">Phone</label>
              <input name="phone" value={formData.phone} onChange={handleChange}
                placeholder="Phone number" className="pf-input" />
            </div>
            <div className="pf-field pf-form-full">
              <label className="pf-field-label">Address</label>
              <div className="pf-addr-wrap">
                <input name="address" value={formData.address} onChange={handleChange}
                  placeholder="Your address" className="pf-input" style={{ width:"100%", paddingRight:130 }} />
                <button className="pf-addr-btn" onClick={getLocation}>
                  📍 Use Location
                </button>
              </div>
            </div>
          </div>

          <div className="pf-btn-row">
            <button className="pf-btn-gold" onClick={handleUpdate}>Save Changes</button>
            <button className="pf-btn-red" onClick={handleDelete}>Delete Account</button>
          </div>
        </div>

        {/* ── CHANGE PASSWORD ── */}
        <div className="pf-card">
          <span className="pf-card-label">Security</span>
          <h2 className="pf-card-title">Change Password</h2>

          <div className="pf-form-grid">
            <div className="pf-field">
              <label className="pf-field-label">Current Password</label>
              <input type="password" name="oldPassword" value={passwords.oldPassword}
                onChange={handlePasswordChange} placeholder="••••••••" className="pf-input" />
            </div>
            <div className="pf-field">
              <label className="pf-field-label">New Password</label>
              <input type="password" name="newPassword" value={passwords.newPassword}
                onChange={handlePasswordChange} placeholder="••••••••" className="pf-input" />
            </div>
          </div>

          <div className="pf-btn-row">
            <button className="pf-btn-gold" onClick={handleChangePassword}>
              Update Password
            </button>
          </div>
        </div>

        {/* ── DELIVERY HISTORY ── */}
        <div className="pf-card">
          <span className="pf-card-label">Orders</span>
          <h2 className="pf-card-title">Delivery History</h2>

          {deliveriesLoading ? (
            <div style={{ display:"flex", alignItems:"center", gap:14, padding:"20px 0" }}>
              <div className="pf-spinner" style={{ width:32, height:32 }} />
              <span style={{ color:"#aaa", fontSize:".88rem", fontWeight:300 }}>
                Fetching your orders…
              </span>
            </div>
          ) : deliveries.length === 0 ? (
            <div className="pf-empty">No delivery history found.</div>
          ) : (
            <div className="pf-delivery-list">
              {deliveries.map((delivery) => (
                <div key={delivery._id} className="pf-delivery-card">
                  <div className="pf-delivery-top">
                    {/* thumbnail */}
                    <img
                      className="pf-delivery-thumb"
                      src={delivery.itemImage || "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=144&auto=format&fit=crop"}
                      alt={delivery.orderName}
                      onError={(e) => {
                        e.target.src = "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=144&auto=format&fit=crop";
                      }}
                    />

                    {/* info */}
                    <div className="pf-delivery-info">
                      <p className="pf-delivery-name">{delivery.orderName}</p>
                      <p className="pf-delivery-meta">
                        <strong>Order ID:</strong> {delivery.orderId}<br />
                        <strong>Address:</strong> {delivery.address}<br />
                        <strong>Driver:</strong> {delivery.driverName} · {delivery.driverPhone}<br />
                        <strong>ETA:</strong>{" "}
                        {new Date(delivery.estimatedTime).toLocaleString("en-US", {
                          month: "short", day: "numeric", year: "numeric",
                          hour: "2-digit", minute: "2-digit",
                        })}
                      </p>
                    </div>

                    {/* actions */}
                    <div className="pf-delivery-actions">
                      <StatusBadge status={delivery.status} />
                      <button
                        className="pf-view-map"
                        onClick={() => handleDriverLocation(delivery._id)}
                      >
                        {expandedDeliveryId === delivery._id ? "▲ Hide Map" : "📍 Track Driver"}
                      </button>
                    </div>
                  </div>

                  {/* leaflet map */}
                  {expandedDeliveryId === delivery._id && (
                    <div
                      className="pf-map-wrap"
                      ref={(el) => (mapRefs.current[delivery._id] = el)}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}