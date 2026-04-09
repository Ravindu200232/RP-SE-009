# UI Design Pattern Guide

This file documents the UI patterns already used in the frontend so another developer or AI model can build new screens in the same visual style.

The current UI mixes:

- Tailwind utility classes
- inline `<style>` blocks for custom branded sections
- responsive dashboard layouts
- soft shadows and rounded cards
- gold accent color for premium CTAs
- white, gray, and dark neutral surfaces

## 1. Core Visual Direction

The frontend uses two main UI modes:

### Public marketing / storefront mode

Seen in:

- `Header`
- `Home`
- `ProductCard`

Style traits:

- editorial fonts such as `Cormorant Garamond`
- accent gold `#F59E0B`
- strong hero imagery
- elegant black/white/gold contrast
- animated hover transitions

### Dashboard / app mode

Seen in:

- `AdminPage`
- `RestaurantPage`
- `DriverPage`
- admin tables and forms

Style traits:

- Tailwind utility classes
- white cards on gray backgrounds
- simple tables and forms
- bold headings
- mobile sidebar pattern

## 2. Color Pattern

Colors already used in the project:

- `primary`: `#050818`
- `secondary`: `#ffffff`
- `accent`: `#7DC4FF`
- premium highlight gold: `#F59E0B`
- dashboard gray background: `bg-gray-100`
- dark footer/header background: `bg-gray-900` or `#111`

Recommended usage:

- gold for CTA buttons, active links, badges, decorative lines
- white for cards, tables, forms, and content surfaces
- dark backgrounds for hero sections, footer, premium areas
- gray background for admin content areas

## 3. Typography Pattern

Two font personalities are used:

### Content / UI font

- `Outfit`
- good for navigation, buttons, forms, labels, sidebars

### Display font

- `Cormorant Garamond`
- good for hero headings, elegant titles, product and section headers

Pattern:

```css
font-family: 'Outfit', sans-serif;
font-family: 'Cormorant Garamond', serif;
```

Use display typography for:

- hero titles
- major section headings
- product names

Use sans-serif for:

- buttons
- tables
- forms
- menu labels
- utility text

## 4. Header Pattern

Current header behavior:

- fixed at top
- transparent at top of page
- becomes solid on scroll
- desktop nav + mobile drawer
- cart action
- login or profile chip on right

Structure:

```jsx
<header className={`fh ${scrolled ? "fh-solid" : "fh-clear"}`}>
  <div className="fh-inner">
    <Link to="/" className="fh-logo">...</Link>
    <nav className="fh-nav">...</nav>
    <div className="fh-actions">...</div>
  </div>
</header>
```

Key design rules:

- keep header fixed
- use active nav underline
- use a profile avatar when logged in
- support drawer navigation on mobile

## 5. Footer Pattern

Current footer style:

- dark background
- 4-column responsive layout
- company links
- support links
- contact details
- social icons

Tailwind pattern:

```jsx
<footer className="w-screen bg-gray-900 text-white py-10">
  <div className="max-w-6xl mx-auto flex flex-wrap justify-center md:justify-between px-6 md:px-12 gap-8">
    ...
  </div>
</footer>
```

Use footer when:

- public pages need closing information
- marketing pages need brand reinforcement

## 6. Button Pattern

There are multiple button styles in the repo.

### Premium CTA button

Used in public hero sections:

```css
.btn-gold {
  background: #F59E0B;
  color: #111;
  padding: 16px 40px;
  text-transform: uppercase;
}
.btn-gold:hover {
  background: #111;
  color: #F59E0B;
}
```

Use for:

- primary actions
- hero CTA
- order now buttons

### Outline / ghost button

```css
.btn-ghost {
  border: 1.5px solid #F59E0B;
  color: #F59E0B;
}
.btn-ghost:hover {
  background: #F59E0B;
  color: #111;
}
```

Use for:

- secondary CTA
- alternate actions

### Dashboard action button

Used in forms and panels:

```jsx
<button className="bg-blue-500 text-white font-semibold py-2 rounded-lg hover:bg-blue-600 transition">
  Add
</button>
```

Use for:

- CRUD submit actions
- quick dashboard interactions

### Destructive button

```jsx
<button className="bg-red-500 text-white font-semibold py-2 rounded-lg hover:bg-red-600 transition">
  Cancel
</button>
```

Use for:

- cancel
- delete
- remove actions

## 7. Card / Box Pattern

The project has multiple card styles.

### Product card

Current traits:

- white background
- subtle border
- hover elevation
- image zoom on hover
- availability badge
- category tag
- CTA button

Structure:

```jsx
<div className="pc-card">
  <div className="pc-bar" />
  <div className="pc-img-wrap">
    <img className="pc-img" ... />
    <span className="pc-avail yes">Available</span>
  </div>
  <div className="pc-body">
    <h2 className="pc-name">Item Name</h2>
    <p className="pc-price">Rs.1000.00</p>
  </div>
</div>
```

### Form box

Used in add/edit screens:

```jsx
<div className="w-full max-w-md bg-white shadow-xl rounded-lg p-6 flex flex-col space-y-4">
  ...
</div>
```

Use for:

- item creation
- profile forms
- update forms

### Dashboard stat/info box

Recommended based on project style:

```jsx
<div className="bg-white rounded-xl shadow-md p-5 border border-gray-200">
  <h3 className="text-lg font-semibold text-gray-800">Title</h3>
  <p className="text-sm text-gray-500 mt-1">Support text</p>
</div>
```

## 8. Table Pattern

Used in admin payment and order screens.

Typical pattern:

```jsx
<div className="overflow-x-auto">
  <table className="min-w-full bg-white rounded-lg shadow-md">
    <thead className="bg-primary text-white">
      <tr>
        <th className="p-3 text-left">Booking ID</th>
        <th className="p-3 text-left">Amount</th>
      </tr>
    </thead>
    <tbody>
      <tr className="border-t hover:bg-gray-100">
        <td className="p-3">ORD0001</td>
        <td className="p-3">Rs.2500.00</td>
      </tr>
    </tbody>
  </table>
</div>
```

Rules:

- wrap in `overflow-x-auto`
- use white card table surface
- use dark or primary-colored header
- use `hover:bg-gray-100` for row feedback
- keep padding consistent with `p-3` or `px-4 py-3`

## 9. Sidebar Pattern

Used in admin, restaurant, and driver dashboards.

Traits:

- fixed mobile sidebar
- static desktop sidebar
- slide-in transform
- top logo/title area
- nav link list
- logout button at bottom

Layout:

```jsx
<div className="flex h-screen overflow-hidden">
  <aside className="fixed md:static z-40 top-0 left-0 h-full w-64 bg-white shadow-md ...">
    ...
  </aside>

  <main className="flex-1 p-4 bg-gray-100 overflow-y-auto">
    ...
  </main>
</div>
```

Use this for any role-based dashboard.

## 10. Hero Section Pattern

Seen in `home.jsx`.

Traits:

- full viewport height
- large background image
- dark overlay or brightness reduction
- large serif heading
- uppercase eyebrow text
- one clear CTA

Structure:

```jsx
<section className="fr-hero">
  <img className="fr-hero-img" ... />
  <div className="fr-hero-body">
    <p className="fr-eyebrow">Welcome</p>
    <h1 className="fr-hero-title">Extraordinary food</h1>
    <p className="fr-hero-sub">Description</p>
    <Link className="btn-gold">Explore</Link>
  </div>
</section>
```

Use hero sections for:

- homepage
- landing pages
- campaign pages

## 11. Form Pattern

There are two form styles in the repo.

### Glassmorphism auth form

Used in login/register pages:

```jsx
<div className="w-[400px] backdrop-blur-xl rounded-2xl flex flex-col justify-center items-center">
  <input className="bg-transparent border-b-2 border-white text-white ..." />
</div>
```

Traits:

- blurred panel
- transparent inputs
- white text
- large visual login/register screen

### Standard dashboard form

Used in add/edit management pages:

```jsx
<input className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400" />
```

Traits:

- white card
- gray border
- rounded corners
- blue focus ring

Use dashboard form style for CRUD screens.

## 12. Image Upload Pattern

Used in register and collection creation pages.

Pattern:

- file input hidden or inline
- preview uploaded/selected image
- upload through `mediaUpload`
- store final public URL in state

Example:

```jsx
const uploadedUrl = await mediaUpload(file);
setImage(uploadedUrl);
```

Preview block:

```jsx
<img
  src={image}
  alt="Profile"
  className="w-24 h-24 object-cover rounded-full border-2 border-white"
/>
```

## 13. Loading / Skeleton Pattern

The repo has a skeleton placeholder component:

```jsx
<div className="flex items-center p-4 bg-secondary rounded-lg shadow-md w-full animate-pulse">
  <div className="w-16 h-16 bg-gray-300 rounded-lg"></div>
</div>
```

Use skeletons for:

- lists
- cards
- bookings
- image-heavy content

## 14. Badge Pattern

Used in product cards and status UIs.

Examples:

- availability badge
- category tag
- order status labels

Recommended style:

```jsx
<span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-700">
  Available
</span>
```

Use color by meaning:

- green: success, available, verified
- red: unavailable, error, blocked
- yellow/gold: warning, premium, active attention
- blue: informational status

## 15. Spacing And Layout Pattern

Common spacing used in this project:

- `p-4`, `p-6`
- `gap-4`, `gap-8`
- `rounded-lg`, `rounded-xl`, `rounded-2xl`
- `shadow-md`, `shadow-xl`
- `max-w-md`, `max-w-6xl`

Recommended layout pattern:

```jsx
<section className="w-full min-h-screen bg-gray-100 px-4 py-6">
  <div className="max-w-6xl mx-auto">
    ...
  </div>
</section>
```

## 16. Reusable UI Building Blocks To Keep

When adding more screens, keep reusing these patterns:

- fixed responsive header
- dark multi-column footer
- white cards with soft shadows
- hoverable product cards
- gray dashboard background
- sidebar dashboard layout
- white data tables
- gold premium CTA buttons
- blue CRUD buttons
- red destructive buttons
- rounded forms with focus ring
- loading skeletons

## 17. UI Prompt For Another AI

```text
Build the UI in this style:

- Public pages should feel premium, elegant, and editorial
- Use Cormorant Garamond for major display headings
- Use Outfit for interface text
- Use gold (#F59E0B), black, white, and neutral grays
- Make the header fixed, transparent on top, solid on scroll
- Use a responsive mobile drawer menu
- Use a dark footer with columns and social links
- Use white cards with soft shadows for dashboard content
- Use white tables with dark headers and hover rows
- Use gold CTA buttons for major storefront actions
- Use blue buttons for add/save actions
- Use red buttons for cancel/delete actions
- Use rounded form inputs with clear focus states
- Add image previews for uploads
- Use skeleton placeholders while loading
```

## 18. Summary

This project already contains a strong UI pattern library:

- premium storefront sections
- utility-based dashboard screens
- responsive sidebars
- elegant header/footer
- reusable cards, forms, buttons, and tables

If new screens follow these patterns, they will fit the current frontend naturally.
