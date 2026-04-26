import { HiLocationMarker } from "react-icons/hi";
import { AiOutlineMail } from "react-icons/ai";
import { BiPhoneCall } from "react-icons/bi";
import Footer from "../../components/footer";
import { useEffect, useState } from "react";
import axios from "axios";
import Swal from "sweetalert2";

/* ── Styles ── */
const ContactStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&display=swap');

    .ct-root { font-family:'Outfit',sans-serif; background:#fff; color:#111; }

    /* ── HERO BANNER ── */
    .ct-hero {
      position: relative;
      width: 100%;
      height: 340px;
      overflow: hidden;
    }
    .ct-hero-img {
      width: 100%; height: 100%;
      object-fit: cover; object-position: center;
      filter: brightness(.35);
      transform: scale(1.04);
      animation: ctZoom 9s ease forwards;
    }
    @keyframes ctZoom { to { transform: scale(1); } }
    .ct-hero-body {
      position: absolute; inset: 0;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      text-align: center; padding: 0 20px;
      animation: ctUp .8s ease both;
    }
    @keyframes ctUp {
      from { opacity:0; transform:translateY(24px); }
      to   { opacity:1; transform:none; }
    }
    .ct-label {
      font-size: .72rem; letter-spacing: .38em; text-transform: uppercase;
      color: #F59E0B; font-weight: 400; margin-bottom: 14px;
    }
    .ct-hero-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: clamp(2.6rem, 6vw, 4.5rem);
      font-weight: 300; color: #fff; line-height: 1.1;
    }
    .ct-hero-title em { font-style: italic; color: #F59E0B; }
    .ct-hero-sub {
      color: rgba(255,255,255,.68); font-size: 1rem;
      font-weight: 300; margin-top: 12px; max-width: 480px; line-height: 1.7;
    }

    /* ── BODY ── */
    .ct-body {
      max-width: 1160px; margin: 0 auto;
      padding: 80px 24px 100px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 56px;
      align-items: start;
    }
    @media (max-width: 768px) {
      .ct-body { grid-template-columns: 1fr; gap: 40px; padding: 56px 20px 80px; }
    }

    /* ── LEFT PANEL ── */
    .ct-left {}
    .ct-section-label {
      font-size: .7rem; letter-spacing: .34em; text-transform: uppercase;
      color: #F59E0B; font-weight: 400; margin-bottom: 12px;
      display: block;
    }
    .ct-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: clamp(2rem, 3.5vw, 3rem);
      font-weight: 300; color: #111; line-height: 1.15;
      margin-bottom: 16px;
    }
    .ct-desc {
      color: #777; font-size: .95rem; font-weight: 300;
      line-height: 1.75; margin-bottom: 44px; max-width: 400px;
    }

    /* Contact info cards */
    .ct-info-list { display: flex; flex-direction: column; gap: 20px; }
    .ct-info-card {
      display: flex; align-items: center; gap: 18px;
      padding: 20px 24px;
      border: 1px solid #f0ece4;
      background: #FAFAF8;
      transition: box-shadow .3s, transform .3s, border-color .3s;
    }
    .ct-info-card:hover {
      box-shadow: 0 12px 40px rgba(0,0,0,.07);
      transform: translateY(-3px);
      border-color: #F59E0B;
    }
    .ct-info-icon-wrap {
      width: 48px; height: 48px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      background: #fff; border: 1.5px solid #F59E0B;
      color: #F59E0B; font-size: 1.3rem;
    }
    .ct-info-text {}
    .ct-info-label {
      font-size: .68rem; letter-spacing: .22em; text-transform: uppercase;
      color: #aaa; font-weight: 400; margin-bottom: 3px;
    }
    .ct-info-value {
      font-size: .95rem; font-weight: 500; color: #222;
    }

    /* Map placeholder */
    .ct-map {
      margin-top: 36px;
      width: 100%; height: 200px;
      overflow: hidden;
      border: 1px solid #f0ece4;
      position: relative;
    }
    .ct-map img {
      width: 100%; height: 100%; object-fit: cover;
      filter: grayscale(30%);
      transition: filter .3s;
    }
    .ct-map:hover img { filter: grayscale(0%); }
    .ct-map-pin {
      position: absolute; top: 50%; left: 50%;
      transform: translate(-50%, -60%);
      color: #F59E0B; font-size: 2.2rem;
      filter: drop-shadow(0 2px 8px rgba(0,0,0,.4));
    }

    /* ── RIGHT PANEL ── */
    .ct-right {}
    .ct-form-card {
      border: 1px solid #f0ece4;
      padding: 44px 40px;
      background: #fff;
      box-shadow: 0 8px 40px rgba(0,0,0,.05);
    }
    @media (max-width: 480px) { .ct-form-card { padding: 28px 20px; } }

    .ct-form-title {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.9rem; font-weight: 400; color: #111;
      margin-bottom: 6px; line-height: 1.2;
    }
    .ct-form-sub {
      font-size: .88rem; color: #888; font-weight: 300;
      margin-bottom: 32px; line-height: 1.6;
    }

    .ct-textarea {
      width: 100%;
      padding: 16px 18px;
      border: 1.5px solid #e8e4da;
      background: #FAFAF8;
      font-family: 'Outfit', sans-serif;
      font-size: .9rem;
      font-weight: 300;
      color: #333;
      resize: vertical;
      outline: none;
      transition: border-color .25s, box-shadow .25s;
      line-height: 1.65;
    }
    .ct-textarea::placeholder { color: #bbb; }
    .ct-textarea:focus {
      border-color: #F59E0B;
      box-shadow: 0 0 0 3px rgba(245,158,11,.1);
      background: #fff;
    }

    .ct-submit {
      width: 100%; margin-top: 16px;
      display: flex; align-items: center; justify-content: center; gap: 10px;
      padding: 16px;
      background: #F59E0B; color: #111;
      font-family: 'Outfit', sans-serif;
      font-weight: 600; font-size: .85rem;
      letter-spacing: .1em; text-transform: uppercase;
      border: none; cursor: pointer;
      transition: background .25s, color .25s, transform .2s;
    }
    .ct-submit:hover:not(:disabled) {
      background: #111; color: #F59E0B; transform: translateY(-2px);
    }
    .ct-submit:disabled { opacity: .55; cursor: not-allowed; }

    /* ── INQUIRY LIST ── */
    .ct-inq-section { margin-top: 44px; border-top: 1px solid #f0ece4; padding-top: 36px; }
    .ct-inq-heading {
      font-family: 'Cormorant Garamond', serif;
      font-size: 1.5rem; font-weight: 400; color: #111; margin-bottom: 20px;
    }
    .ct-inq-scroll {
      max-height: 420px; overflow-y: auto;
      display: flex; flex-direction: column; gap: 16px;
      padding-right: 4px;
      scrollbar-width: thin; scrollbar-color: #F59E0B #f5f0e8;
    }
    .ct-inq-card {
      border: 1px solid #f0ece4;
      padding: 22px 24px;
      background: #FAFAF8;
      transition: border-color .25s, box-shadow .25s;
    }
    .ct-inq-card:hover {
      border-color: #e0dbd0;
      box-shadow: 0 6px 24px rgba(0,0,0,.05);
    }
    .ct-inq-meta {
      display: flex; align-items: center; gap: 8px;
      margin-bottom: 12px;
    }
    .ct-inq-dot {
      width: 6px; height: 6px; border-radius: 50%; background: #F59E0B; flex-shrink: 0;
    }
    .ct-inq-label {
      font-size: .68rem; letter-spacing: .22em; text-transform: uppercase;
      color: #aaa; font-weight: 400;
    }
    .ct-inq-textarea {
      width: 100%; padding: 12px 14px;
      border: 1.5px solid #e8e4da;
      background: #fff;
      font-family: 'Outfit', sans-serif;
      font-size: .88rem; font-weight: 300; color: #333;
      resize: vertical; outline: none;
      transition: border-color .25s;
      margin-bottom: 12px;
    }
    .ct-inq-textarea:focus { border-color: #F59E0B; }

    .ct-inq-response-label {
      font-size: .68rem; letter-spacing: .22em; text-transform: uppercase;
      color: #aaa; font-weight: 400; margin-bottom: 6px;
    }
    .ct-inq-response {
      font-size: .88rem; color: #666; font-style: italic;
      font-weight: 300; margin-bottom: 18px; line-height: 1.6;
    }

    .ct-inq-btns { display: flex; gap: 10px; }
    .ct-btn-update {
      flex: 1; padding: 10px;
      background: transparent; border: 1.5px solid #F59E0B; color: #F59E0B;
      font-family: 'Outfit', sans-serif;
      font-size: .78rem; font-weight: 600;
      letter-spacing: .1em; text-transform: uppercase;
      cursor: pointer;
      transition: background .2s, color .2s;
    }
    .ct-btn-update:hover { background: #F59E0B; color: #111; }
    .ct-btn-delete {
      flex: 1; padding: 10px;
      background: transparent; border: 1.5px solid #e5595a; color: #e5595a;
      font-family: 'Outfit', sans-serif;
      font-size: .78rem; font-weight: 600;
      letter-spacing: .1em; text-transform: uppercase;
      cursor: pointer;
      transition: background .2s, color .2s;
    }
    .ct-btn-delete:hover { background: #e5595a; color: #fff; }
  `}</style>
);

export default function Contact() {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [inquiries, setInquiries] = useState([]);

  const fetchInquiries = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await axios.get(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/inquiry`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setInquiries(res.data || []);
    } catch (err) {
      console.error("Failed to fetch inquiries", err);
    }
  };

  useEffect(() => { fetchInquiries(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message.trim()) {
      Swal.fire("Error", "Please enter your message.", "warning");
      return;
    }
    try {
      setLoading(true);
      const token = localStorage.getItem("token");
      await axios.post(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/inquiry`,
        { message },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      Swal.fire("Success", "Your inquiry has been submitted.", "success");
      setMessage("");
      fetchInquiries();
    } catch (error) {
      console.error("Inquiry submission failed", error);
      Swal.fire("Error", "Please login first.", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ct-root">
      <ContactStyles />

      {/* ── HERO BANNER ── */}
      <section className="ct-hero">
        <img
          className="ct-hero-img"
          src="https://images.unsplash.com/photo-1600891964599-f61ba0e24092?w=1800&auto=format&fit=crop"
          alt="Contact FoodRush"
        />
        <div className="ct-hero-body">
          <p className="ct-label">We'd love to hear from you</p>
          <h1 className="ct-hero-title">
            Get in <em>Touch</em>
          </h1>
          <p className="ct-hero-sub">
            Have a question, feedback, or a bulk order? Our team is ready
            to help — reach out any time.
          </p>
        </div>
      </section>

      {/* ── MAIN GRID ── */}
      <div className="ct-body">

        {/* ── LEFT: Contact Info ── */}
        <div className="ct-left">
          <span className="ct-section-label">Reach us directly</span>
          <h2 className="ct-title">Contact<br />Information</h2>
          <p className="ct-desc">
            Feel free to use the form or drop us an email. Old-fashioned
            phone calls work too — we're always happy to chat.
          </p>

          <div className="ct-info-list">
            <div className="ct-info-card">
              <div className="ct-info-icon-wrap">
                <BiPhoneCall />
              </div>
              <div className="ct-info-text">
                <p className="ct-info-label">Phone</p>
                <p className="ct-info-value">0789 840 996</p>
              </div>
            </div>

            <div className="ct-info-card">
              <div className="ct-info-icon-wrap">
                <AiOutlineMail />
              </div>
              <div className="ct-info-text">
                <p className="ct-info-label">Email</p>
                <p className="ct-info-value">Ravindu2232@gmail.com</p>
              </div>
            </div>

            <div className="ct-info-card">
              <div className="ct-info-icon-wrap">
                <HiLocationMarker />
              </div>
              <div className="ct-info-text">
                <p className="ct-info-label">Address</p>
                <p className="ct-info-value">Kahatagasdigiliya, Anuradhapura</p>
              </div>
            </div>
          </div>

          {/* Map image */}
          <div className="ct-map">
            <img
              src="https://images.unsplash.com/photo-1524661135-423995f22d0b?w=900&auto=format&fit=crop"
              alt="Location map"
            />
            <div className="ct-map-pin">
              <HiLocationMarker />
            </div>
          </div>
        </div>

        {/* ── RIGHT: Form + Inquiries ── */}
        <div className="ct-right">
          <div className="ct-form-card">
            <span className="ct-section-label">Send a message</span>
            <h2 className="ct-form-title">Drop us a line</h2>
            <p className="ct-form-sub">
              Tell us how we can help and we'll get back to you as soon
              as possible.
            </p>

            <form onSubmit={handleSubmit}>
              <textarea
                className="ct-textarea"
                name="message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Write your message here…"
                rows={5}
              />
              <button type="submit" disabled={loading} className="ct-submit">
                {loading ? "Sending…" : "Send Message →"}
              </button>
            </form>

            {/* ── Inquiry list ── */}
            {inquiries.length > 0 && (
              <div className="ct-inq-section">
                <h3 className="ct-inq-heading">Your Inquiries</h3>
                <div className="ct-inq-scroll">
                  {inquiries.map((inq, idx) => (
                    <div key={inq._id} className="ct-inq-card">
                      <div className="ct-inq-meta">
                        <span className="ct-inq-dot" />
                        <span className="ct-inq-label">Inquiry #{idx + 1}</span>
                      </div>

                      <textarea
                        rows={3}
                        className="ct-inq-textarea"
                        value={inq.message}
                        onChange={(e) => {
                          const updated = [...inquiries];
                          updated[idx].message = e.target.value;
                          setInquiries(updated);
                        }}
                      />

                      <p className="ct-inq-response-label">Response</p>
                      <p className="ct-inq-response">
                        {inq.response || "No response yet."}
                      </p>

                      <div className="ct-inq-btns">
                        <button
                          className="ct-btn-update"
                          onClick={async () => {
                            try {
                              const token = localStorage.getItem("token");
                              const { message } = inquiries[idx];
                              if (!message.trim()) {
                                Swal.fire("Warning", "Message cannot be empty.", "warning");
                                return;
                              }
                              await axios.put(
                                `${import.meta.env.VITE_USER_SERVICE_URL}/api/inquiry/${inq._id}`,
                                { message },
                                { headers: { Authorization: `Bearer ${token}` } }
                              );
                              Swal.fire("Success", "Inquiry updated successfully.", "success");
                              fetchInquiries();
                            } catch (err) {
                              console.error("Failed to update inquiry", err);
                              Swal.fire("Error", "Failed to update inquiry.", "error");
                            }
                          }}
                        >
                          Update
                        </button>

                        <button
                          className="ct-btn-delete"
                          onClick={async () => {
                            const confirmed = await Swal.fire({
                              title: "Are you sure?",
                              text: "This action cannot be undone.",
                              icon: "warning",
                              showCancelButton: true,
                              confirmButtonText: "Yes, delete it!",
                            });
                            if (confirmed.isConfirmed) {
                              try {
                                const token = localStorage.getItem("token");
                                await axios.delete(
                                  `${import.meta.env.VITE_USER_SERVICE_URL}/api/inquiry/${inq._id}`,
                                  { headers: { Authorization: `Bearer ${token}` } }
                                );
                                Swal.fire("Deleted!", "Your inquiry has been removed.", "success");
                                fetchInquiries();
                              } catch (err) {
                                console.error("Failed to delete inquiry", err);
                                Swal.fire("Error", "Failed to delete inquiry.", "error");
                              }
                            }
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

      </div>

      <Footer />
    </div>
  );
}