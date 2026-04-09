# Frontend Pattern Guide

This file explains how the frontend in this project is structured, how `App.jsx` is handled, how `BrowserRouter` is used, how nested routes are organized, and how to extend the frontend cleanly.

## 1. Frontend Stack

The frontend uses:

- React
- Vite
- React Router
- Tailwind CSS
- `axios` for API calls
- `react-hot-toast` for notifications
- `@react-oauth/google` for Google login
- Supabase for image uploads

Main frontend folders:

```text
client/
|-- src/
|   |-- components/
|   |-- pages/
|   |   |-- admin/
|   |   |-- driver/
|   |   |-- home/
|   |   |-- login/
|   |   |-- register/
|   |   |-- restaurantant/
|   |   |-- verifyEmail/
|   |-- utils/
|   |-- App.jsx
|   |-- main.jsx
|   |-- index.css
```

## 2. `main.jsx` Pattern

`main.jsx` is the frontend entry file. It mounts the React app.

Current pattern:

```jsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

Use `main.jsx` only for:

- importing global CSS
- rendering the root app
- optionally wrapping in `StrictMode`

Do not place app routes or page layout logic here.

## 3. `App.jsx` Pattern

`App.jsx` is the root application router layer.

This project uses `App.jsx` to:

- wrap the app with `GoogleOAuthProvider`
- wrap the app with `BrowserRouter`
- mount the global `Toaster`
- define top-level route groups

Current structure:

```jsx
function App() {
  return (
    <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID || ""}>
      <BrowserRouter>
        <Toaster position="top-right" />
        <Routes path="/">
          <Route path="/*" element={<HomePage />} />
          <Route path="/login" element={<Login />} />
          <Route path="admin/*" element={<AdminPage />} />
          <Route path="restaurantC/*" element={<RestaurantPage />} />
          <Route path="driver/*" element={<DriverPage />} />
        </Routes>
      </BrowserRouter>
    </GoogleOAuthProvider>
  );
}
```

### What belongs in `App.jsx`

- providers
- root routes
- global route-level pages
- route groups like admin, restaurant, driver, public

### What should not go in `App.jsx`

- page-specific business logic
- data fetching for one page
- component styling blocks for a single feature
- repeated route definitions for dashboard children

## 4. `BrowserRouter` Pattern

This app uses `BrowserRouter` from `react-router-dom`.

Use it once at the root:

```jsx
<BrowserRouter>
  <App />
</BrowserRouter>
```

In this project it is already placed inside `App.jsx`, which is valid because `main.jsx` renders only `App`.

Use `BrowserRouter` when:

- you want normal browser URLs
- you want nested routes
- you want `Link`, `Routes`, `Route`, `useNavigate`, `useLocation`

## 5. Route Group Pattern

This frontend is organized into route groups:

- public routes handled by `HomePage`
- admin dashboard routes handled by `AdminPage`
- restaurant owner dashboard routes handled by `RestaurantPage`
- driver dashboard routes handled by `DriverPage`

Top-level route groups:

```jsx
<Route path="/*" element={<HomePage />} />
<Route path="admin/*" element={<AdminPage />} />
<Route path="restaurantC/*" element={<RestaurantPage />} />
<Route path="driver/*" element={<DriverPage />} />
```

This is the main frontend routing pattern of the repo.

## 6. Nested Routes Pattern

Each route group has its own local `<Routes>` block.

### Public pages: `HomePage`

`HomePage` mounts the shared public header, then defines its own routes:

```jsx
<>
  <Header />
  <main style={{ minHeight: "100vh" }}>
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/restaurant" element={<Restaurant />} />
      <Route path="/restaurant/*" element={<RestaurantDetails />} />
      <Route path="/item" element={<Item />} />
      <Route path="/product/:key" element={<ProductOverview />} />
      <Route path="/cart" element={<BookingPage />} />
      <Route path="/profile" element={<Profile />} />
      <Route path="/*" element={<ErrorNotFound />} />
    </Routes>
  </main>
</>
```

### Admin dashboard: `AdminPage`

`AdminPage` uses a sidebar + content layout, then defines child routes:

```jsx
<main className="flex-1 p-4 bg-gray-100 overflow-y-auto">
  <Routes>
    <Route path="/booking" element={<AdminBookingPage />} />
    <Route path="/item" element={<AdminItemPage />} />
    <Route path="/user/*" element={<User />} />
    <Route path="/review" element={<AdminReviewPage />} />
    <Route path="/inquiry" element={<AdminInquiryPage />} />
    <Route path="/package" element={<AdminPackagePage />} />
    <Route path="/profile" element={<Profile />} />
    <Route path="/payment" element={<AdminPayment />} />
  </Routes>
</main>
```

### Restaurant dashboard: `RestaurantPage`

```jsx
<Routes>
  <Route path="/booking" element={<RestaurantOrder />} />
  <Route path="/restaurant/" element={<RestaurantCreate />} />
  <Route path="/restaurant/add" element={<AddRestaurant />} />
  <Route path="/restaurant/edit" element={<UpdateRestaurant />} />
  <Route path="/restaurant/collection" element={<CollectionPage />} />
  <Route path="/restaurant/collection/add" element={<AddCollection />} />
  <Route path="/restaurant/collection/update" element={<UpdateCollection />} />
  <Route path="/review" element={<RestaurantReview />} />
  <Route path="/profile" element={<Profile />} />
</Routes>
```

### Driver dashboard: `DriverPage`

```jsx
<Routes>
  <Route path="/available" element={<Available />} />
  <Route path="/track" element={<DeliveryTrack />} />
</Routes>
```

## 7. How To Add New Routes

Use this rule:

1. Decide whether the page is public, admin, restaurant, or driver.
2. Add the top-level route only if it is a brand-new route group.
3. Otherwise add the child route inside that group component.
4. Add a navigation `Link` if the page should appear in menus.

### Example: add a new public page

Create file:

```text
client/src/pages/home/about.jsx
```

Then add route in `HomePage.jsx`:

```jsx
import About from "./about";

<Route path="/about" element={<About />} />
```

Then add navigation item in `Header.jsx`:

```jsx
const NAV = [
  { to: "/", label: "Home" },
  { to: "/contact", label: "Contact" },
  { to: "/restaurant", label: "Restaurants" },
  { to: "/item", label: "Items" },
  { to: "/about", label: "About" },
];
```

### Example: add a new admin page

Create file:

```text
client/src/pages/admin/adminReports.jsx
```

Then add route in `AdminPage.jsx`:

```jsx
import AdminReports from "./adminReports";

<Route path="/reports" element={<AdminReports />} />
```

Then add sidebar link:

```jsx
{
  to: "/admin/reports",
  icon: <BsGraphDown />,
  label: "Reports",
}
```

## 8. Navigation Pattern

This project uses:

- `Link` for navigation UI
- `useNavigate` for programmatic redirects
- `useLocation` for active route styling and location state

Examples already used in the project:

- `useNavigate()` after login
- `useLocation()` for `restaurantId` state in forms
- `Link` inside sidebars and the main header

Example:

```jsx
const navigate = useNavigate();

function handleSuccess() {
  navigate("/login");
}
```

## 9. Protected Layout Pattern

The admin, restaurant, and driver dashboards all use the same access pattern:

```jsx
const [token] = useState(localStorage.getItem("token"));

if (!token) {
  window.location.href = "/login";
}
```

Then the page renders:

- mobile menu toggle
- sidebar
- logout button
- content area with nested routes

This project does not currently use a reusable `ProtectedRoute` component, but you can introduce one later if you want to reduce duplication.

## 10. API Call Pattern

Use env-based service URLs and attach the JWT from local storage.

Example:

```jsx
const token = localStorage.getItem("token");

await axios.get(`${import.meta.env.VITE_PAYMENT_SERVICE_URL}/api/payment`, {
  headers: {
    Authorization: `Bearer ${token}`,
  },
});
```

Recommended rule:

- keep URLs in `import.meta.env`
- keep token retrieval near the request
- keep API logic inside the page or move repeated logic into `utils/` or `services/`

## 11. Form Page Pattern

Form pages in this repo usually follow this pattern:

- local `useState` for fields
- `handleOnSubmit` or `handleAddItem`
- upload images first if needed
- build payload
- call backend with `axios`
- show success/error with `toast`
- redirect with `navigate`

Example structure:

```jsx
const [name, setName] = useState("");
const [images, setImages] = useState([]);

async function handleSubmit() {
  const token = localStorage.getItem("token");
  const imageUrls = await Promise.all(Array.from(images).map(mediaUpload));

  await axios.post(
    `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection`,
    { name, images: imageUrls },
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
}
```

## 12. State And Storage Pattern

The app stores frontend session data in `localStorage`:

- `token`
- `user`
- `cart`

Examples used in the repo:

```jsx
localStorage.setItem("token", res.data.token);
localStorage.setItem("user", JSON.stringify(user));
localStorage.clear();
```

Use this when:

- login completes
- profile changes need to be reflected
- logout happens

## 13. Recommended Frontend File Pattern

For each new feature page:

```text
pages/feature/
|-- featurePage.jsx
|-- featureForm.jsx
|-- featureTable.jsx
```

For reusable UI:

```text
components/
|-- header.jsx
|-- footer.jsx
|-- productCard.jsx
|-- skeleton.jsx
```

For helpers:

```text
utils/
|-- mediaUpload.js
|-- card.jsx
```

## 14. Frontend Env Pattern

Use:

```env
VITE_USER_SERVICE_URL=http://localhost:3001
VITE_RESTAURANT_SERVICE_URL=http://localhost:3002
VITE_ORDER_SERVICE_URL=http://localhost:3003
VITE_PAYMENT_SERVICE_URL=http://localhost:3004
VITE_DELIVER_SERVICE_URL=http://localhost:3005
VITE_NOTIFICATION_SERVICE_URL=http://localhost:3006
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
VITE_SUPABASE_BUCKET=images
VITE_GOOGLE_CLIENT_ID=your_google_oauth_client_id
```

## 15. Reusable Build Prompt For Another AI

```text
Build the frontend using this pattern:

- Use React + Vite
- Use App.jsx as the root route file
- Wrap the app with GoogleOAuthProvider and BrowserRouter
- Put all public routes in HomePage.jsx
- Put admin routes in AdminPage.jsx
- Put restaurant routes in RestaurantPage.jsx
- Put driver routes in DriverPage.jsx
- Use nested Routes inside each route group
- Use Link for menus and useNavigate for redirects
- Store token and user in localStorage
- Send Authorization: Bearer <token> in protected requests
- Use Tailwind CSS for layouts and utility styling
- Use env-based service URLs with import.meta.env
- Use mediaUpload helper for Supabase image uploads
```

## 16. Summary

This frontend is built with a clear route-group structure:

- `main.jsx` mounts the app
- `App.jsx` defines global wrappers and root routes
- each major dashboard owns its own child routes
- shared UI lives in `components/`
- helpers live in `utils/`
- API calls use `axios` + env URLs + JWT

If you follow this pattern, new frontend pages will fit naturally into the current codebase.
