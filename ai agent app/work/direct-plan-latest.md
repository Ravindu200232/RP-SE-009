
# Implementation Plan - MegaMart Pro

## Project Overview & Design Philosophy
MegaMart Pro is a comprehensive retail enterprise platform built on Next.js 15 App Router, TypeScript, Tailwind CSS, shadcn/ui primitives, and MongoDB with Mongoose. It integrates public-facing e-commerce features (product browsing, cart, checkout) with internal modules for POS billing, inventory management, supplier purchasing, and admin controls. The design prioritizes a modular architecture, role-based access control (RBAC), responsive user interfaces across mobile, tablet, and desktop, robust backend APIs using Route Handlers in `app/api`, and data integrity through MongoDB/Mongoose schemas. Key principles include separation of concerns for server-side logic from client components, leveraging shadcn/ui primitives for consistent UI elements, ensuring all CRUD operations are backed by real MongoDB queries (not local arrays), implementing seed data for initial state when the database is empty, and maintaining strict TypeScript typing throughout.

## Requirement Summary
This platform provides a unified solution for retail businesses, encompassing customer shopping experiences alongside internal management systems. It supports multiple user roles with distinct permissions and access levels, enabling tailored functionality. The system includes full CRUD capabilities across products, customers, suppliers, inventory, orders, etc., along with reporting features to monitor sales, stock levels, and business performance. Role-based navigation ensures users only see relevant sections based on their assigned role.

| ID | Feature / Requirement                                  | User Role(s)                      | Priority | Notes                                                                 |
| -- | ------------------------------------------------------- | --------------------------------- | -------- | -------------------------------------------------------------------- |
| 1  | Public Home Page with Hero                              | Customer, General Browse          | High     | Welcome screen for customers and general site visitors.              |
| 2  | Product Listing (Filtered & Sorted)                     | All Users                        | Critical | Display products based on category, search term, price range, etc.    |
| 3  | Product Detail Page                                     | Customer                           | Critical | Detailed view of a product including images, stock status, related items. |
| 4  | Cart Functionality                                      | Customer                           | High     | Add/remove/update quantities and proceed to checkout.                 |
| 5  | Checkout Process                                        | Customer                           | Critical | Collect shipping details for online orders; redirect to POS/Invoice otherwise. |
| 6  | Order Success Confirmation                              | Customer, Branch Manager           | High     | Post-checkout confirmation page with order summary (for online).    |
| 7  | About Page                                               | All Users                        | Medium   | Information about the company and its offerings.                     |
| 8  | Contact Page                                             | All Users                        | Medium   | Form or information for users to contact support/management.        |
| 9  | Dashboard Overview (KPIs, Recent Orders)               | Super Admin, Admin, Branch Manager | High     | Summary page showing key metrics and recent transactions.            |
| 10 | Products Management Page                                | Admin                             | Critical | CRUD interface for products with image handling and category/brand links. |
| 11 | Categories Management (with parent support)             | Admin                             | Critical | CRUD interface for product categories, including hierarchical structure if needed. |
| 12 | Branch Stock & Inventory Tracking                        | Branch Manager, Inventory Staff    | High     | View stock levels across branches and manage inventory adjustments/GRNs. |
| 13 | Cashier POS Billing Page                                 | Cashier                           | Critical | Create sales invoices with product search (by SKU/barcode), quantity input, discounts/taxes, payment methods, and invoice generation. |
| 14 | Inventory Staff Management (Stock, GRN, Adjustments)    | Inventory Staff                  | Critical | Track inventory levels, process Goods Receipt Notes (GRNs), handle stock adjustments, manage low-stock alerts. Includes expiry/batch tracking. |
| 15 | Supplier Purchasing Module                              | Admin                             | High     | Manage purchase orders from suppliers and track order statuses.        |
| 16 | Customer Management Page                                | Admin                             | Critical | CRUD interface for customer details, including loyalty points management. |
| 17 | Reports Generation (Sales, Product, Inventory)          | Super Admin                        | Medium   | Generate detailed reports based on various criteria; accessible only by certain roles. |

## Architecture & Folder Strategy
The application follows a server-components-first architecture with Next.js App Router Route Handlers for backend logic residing in `app/api`. Server components handle data fetching and business logic, while Client Components are used sparingly for UI interactivity (e.g., form validation feedback). The folder structure is designed as follows:

- **`/app`**: Contains all route files (`route.ts`) defining the frontend pages. Each page corresponds to a route in `Page/Module List`. Example: `/dashboard`, `/products`.
  - Subfolders organized by feature or role for clarity (e.g., `dashboard`, `public`, `inventory`). Pages are default server components unless marked with `'use client'` at the top.
- **`components/ui`**: Houses all shadcn/ui primitives and custom UI components built using these. This ensures reusability of elements like buttons, inputs, tables, modals across the app.
- **`lib`**: Core reusable logic and utilities.
  - `lib/server-actions`: Functions for server-side actions (CRUD operations) that can be called from client components via forms or API routes.
  - `lib/models`: Mongoose schemas and models defined in TypeScript files. Each model file name is Pascal Case (e.g., `Product.ts`, `StockMovement.ts`).
    - Includes interfaces for each collection, schema definitions with required/unique/ref notes, index specifications, and seed data functions.
- **`public`**: Static assets like images, fonts, or initial demo data files are stored here. Demo user seeds can be placed in `/public/demo-users.json`.
- **Shared Components**: Placed within `components/ui`, including:
  - Layout components (`Layout.tsx`) defining the base structure (header, footer).
  - Navigation component (`Navigation.tsx`) handling role-based menu items.
  - Data table components (`DataTable.tsx` with shadcn/ui integration) for displaying filtered/sorted/paginated data across modules.
  - Auth modals/redirects using shadcn/ui primitives.

## Database Schema Summary
All backend data is stored in MongoDB, managed via Mongoose schemas. Models are defined in `lib/models`. Below are the summaries for each required collection:

### User (lib/models/User.ts)
| Field           | Type            | Required | Notes                                                                 |
| ---------------- | --------------- | -------- | -------------------------------------------------------------------- |
| name             | String          | Yes      | Full user name.                                                       |
| email            | String          | Yes, Unique | Customer-facing email for login and contact; must be unique across all users (including staff). |
| passwordHash     | String          | Yes      | Hashed password using bcrypt or similar – never store plain text.       |
| role             | Enum<string>    | Yes      | One of 'Super Admin', 'Admin', 'Branch Manager', 'Cashier', 'Inventory Staff'. |
| branchId         | mongoose.Schema.Types.ObjectId | No  | Reference to a Branch document if the user is staff (not customer).     |
| status           | String          | Yes, Default: 'active' | Can be 'active', 'inactive', or for customers also 'verified'/'unverified'. |
| createdAt        | Date            | Yes      | Auto-populated timestamp.                                            |
| updatedAt         | Date            | Yes      | Auto-populated timestamp on update.

### Product (lib/models/Product.ts)
| Field           | Type            | Required | Notes                                                                 |
| ---------------- | --------------- | -------- | -------------------------------------------------------------------- |
| name             | String          | Yes      | Product title/description.                                            |
| sku              | String          | Yes, Unique | Stock Keeping Unit – unique identifier for inventory tracking.        |
| barcode          | String          | No       | Optional barcode string if provided by supplier or manufacturer.     |
| slug             | String          | Yes, Unique | URL-friendly version of the product name used in routes (e.g., `/products/[slug]`). |
| description      | String          | Yes      | Detailed product information including features and usage instructions. |
| categoryId       | mongoose.Schema.Types.ObjectId | No  | Reference to a Category document; products must belong to one category. |
| brandId          | mongoose.Schema.Types.ObjectId | No  | Reference to a Brand document if applicable.                           |
| sellingPrice     | Number          | Yes      | Current retail price for the product.                                |
| costPrice        | Number          | Yes      | Cost price per unit – used in inventory valuation and potentially profit calculations. |
| discountPrice    | Number          | No       | Optional discounted price if applicable (e.g., seasonal sale).       |
| images           | Array<string>   | No       | Array of image URLs or paths representing product visuals.            |
| unit             | String          | Yes      | Unit of measure for quantity (e.g., 'EA', 'KG', 'L').                |
| reorderLevel     | Number          | Yes, Default: 10 | Minimum stock level before triggering a low-stock alert; must be numeric and positive. |
| status           | String          | Yes, Default: 'active' | Can be 'active', 'inactive', or 'draft'.                  |
| timestamps       | Date            | Auto    | createdAt, updatedAt auto-populated.

### Stock (lib/models/Stock.ts)
| Field           | Type            | Required | Notes                                                                 |
| ---------------- | --------------- | -------- | -------------------------------------------------------------------- |
| productId        | mongoose.Schema.Types.ObjectId | No  | Reference to the Product document. This field is mandatory for a valid stock record. |
| branchId         | mongoose.Schema.Types.ObjectId | No       | Reference to the Branch document owning this stock level; required here as it's part of the compound index and core logic, but could be optional in some contexts if tracking only central inventory? Wait – spec says "branchId ref Branch", so make that required. |
| quantity         | Number          | Yes      | Current available stock count at this branch location.                |
| reservedQuantity | Number          | No       | Quantity currently on hold for pending orders or transfers; can be zero by default. |

### Other Models (Continue from spec)
- **Category**: If parent category support is needed, define a schema with `name`, `slug` (unique), `parentId` optional reference to itself for hierarchy.
- **Brand**: Simple model with `name`, `slug` unique, and potential image fields if required.

## Page/Module List
| Route          | Page                     | Type       | Access              | Purpose                                                                 |
| -------------- | ------------------------ | ---------- | ------------------- | ----------------------------------------------------------------------- |
| /               | Home Page                | Server     | Public              | Main landing page with hero section, featured content.                   |
| /products      | Product Listing          | Server     | All Users            | Browse all products; includes category filter, search, price filters, sort. |
| /products/[slug] | Product Details         | Server     | Customer            | View product details including stock status and related products (if any). |
| /cart           | Cart Page                | Server     | Customer            | Manage items in the shopping cart; proceed to checkout or modify quantities. |
| /checkout       | Checkout Process         | Server/Client | Customer          | Collect shipping/payment details for online orders; redirect to POS if applicable. |
| /success        | Order Success Confirmation | Server     | Customer            | Display confirmation message and order summary after successful purchase. |
| /about          | About Page               | Server     | Public              | Static information about the company.                                   |
| /contact        | Contact Page             | Server/Client | Public         | Form or contact details for user inquiries; includes form submission handling. |
| /dashboard      | Dashboard Overview       | Server     | Super Admin, Admin   | KPI dashboard showing revenue chart, recent orders, low stock products, etc. |
| /products/manage | Products Management Page | Server/Client | Admin        | CRUD interface for products (create, read, update, delete).             |
| /categories     | Categories List          | Server/Client | Admin        | Manage product categories; includes parent category support UI if implemented. |
| /branches        | Branches Overview         | Server/Client | Super Admin    | View and manage branch information including stock levels (if applicable to role). |

## API Routes List
- **GET /api/auth/login** - Handle login request, return JWT token or session ID upon successful authentication.
- **POST /api/auth/register** - Register a new customer user account; basic validation on client side before server call. *Note: Super Admin registration might be handled separately via an admin panel.*
- **GET /api/products** - Fetch all products with optional filters (category, search term) and pagination/sorting parameters.
- **POST /api/products** - Create a new product document in the database; requires staff authentication and validation of required fields.
- **PUT /api/products/:id** - Update an existing product by ID; restricts access based on role (Admin or Super Admin).
- **DELETE /api/products/:id** - Delete a product by ID; checks permissions and potentially cascades related data if necessary.

## UI and Component Strategy
The app shell uses a combination of Top Navbar for primary navigation and Sidebar for context-specific actions, adapting the layout based on user role and screen size (responsive design). The visual direction is clean, modern, and professional using Tailwind CSS for styling. All dropdowns use native `<select>` elements wrapped in shadcn/ui primitives for consistency.

- **Navigation**: Role-based sidebar toggles visibility of sections like 'Inventory', 'POS Billing'. Top navbar contains login/register links for unauthenticated users.
- **Responsive Behavior**: Mobile-first approach; dashboard collapses into a single column, product listing adjusts filter positions. Use Tailwind's responsive classes (e.g., `md:flex`) to control layout changes.
- **Accessibility**: Follow WCAG guidelines – ensure sufficient color contrast, proper ARIA labels where necessary, keyboard navigation support.

## Page-by-Page Build Blueprint
### / - Home Page
**Sections**: Hero banner, Featured categories section with horizontal scrolling cards, Featured products grid (limited view), Deals carousel if applicable.
**Functions**: Static content display; potentially pre-fetched featured data could be included here for dynamism.
**Data**: `lib/models/Category` and `Product` references via API routes or static props. No user interaction requires auth checks unless viewing product details which might have conditional stock info based on branch.
**Design**: Clean, welcoming layout with prominent CTAs; responsive grid and flex containers.

### /products - Product Listing
**Sections**: Category filter dropdown (native select), search bar, price range slider or input fields, Sort options (e.g., by name, price, popularity), Grid of product cards displaying image, name, price.
**Functions**: Fetch products from `/api/products` based on filters/sort; handle user interactions to change parameters without page reload.
**Data**: `lib/models/Product`; filter logic implemented in API route or server component action. Empty state for no results, loading skeleton while fetching data.
**Design**: Responsive grid layout (Tailwind CSS); interactive filter UI using shadcn/ui components.

### /products/[slug] - Product Details
**Sections**: Large product image gallery with navigation, Detailed description section, Price display including discount if applicable, Add to cart button with quantity selector or direct link to inventory page depending on user role.
**Functions**: Fetch single product via `/api/products/:id` (or slug mapping), handle adding items to cart by calling relevant API endpoint from client component.
**Data**: `lib/models/Product`; potentially related products based on category/brand. Cart state is managed locally or in a session store, synced with backend upon checkout initiation elsewhere.
**Design**: Detailed card layout; image gallery using responsive breakpoints.

### /cart - Cart Page
**Sections**: Summary of cart items (image, name, quantity, price each), Subtotal calculation including taxes/discounts applied during checkout flow. Add/remove item buttons per line item; edit quantities input field for individual items.
**Functions**: Fetch current user's cart state via API route or session storage on load; update quantities/add/remove items by calling `/api/cart/update` endpoint (or similar) from client component actions with validation.
**Data**: Cart data structure stored in `useState` initially, synced with backend upon save action. Empty cart redirects to product listing or home page.
**Design**: Simple list view of cart items; clear call-to-action buttons for checkout.

### /checkout - Checkout Process
**Sections**: Shipping address form (if new online order), Payment method selection section (credit card details, cash on delivery options etc.), Order summary with line items and calculated totals. Confirmation button that triggers API save.
**Functions**: Collect shipping info via client component state update; validate payment details before submission. Handle different payment methods securely.
**Data**: `lib/models/OnlineOrder` or potentially a unified order model depending on backend design. Form validation ensures all required fields are filled, quantities match stock etc.
**Design**: Step-by-step form layout with clear feedback during each step.

### /success - Order Success
**Sections**: Confirmation message and icon, Summary of the completed order (items, total amount), Optional link to track order status or continue shopping page. Simple thank you text.
**Functions**: Display success state after API call confirms order creation; no further user interaction needed here except maybe navigation.
**Data**: `lib/models/OnlineOrder` reference for confirmation message display if desired.
**Design**: Success-focused layout with positive reinforcement.

### /about - About Page
**Sections**: Static content sections: Company history, Mission statement, Contact information. Simple structure.
**Functions**: No data fetching required; purely static content.
**Data**: None fetched from backend APIs.
**Design**: Plain text and image layout using standard Tailwind components.

## Development Phases
1. **Authentication & RBAC Setup (Weeks 1-2)**: Implement login/register pages, user session management with secure cookies or JWT storage on client side; define API endpoints for auth (`/api/auth/login`, `/api/auth/me`) and seed initial demo users data in `public/demo-users.json`. Focus on core security patterns.
2. **Core Data Models & CRUD APIs (Weeks 3-5)**: Define all Mongoose schemas in `lib/models` based on spec; implement backend Route Handlers for each model's basic CRUD operations (`GET /api/model`, `POST /api/model`, etc.) using server components from `/app/api`. Ensure compound indexes are set up correctly.
3. **Public Facing Modules (Weeks 6-8)**: Build home page, product listing, cart, checkout, and customer dashboard pages with their respective UI logic and API integrations. Implement role-based navigation for public areas.
4. **Internal Admin Modules (Weeks 9-12)**: Develop staff management, inventory tracking, POS billing, supplier purchasing, branch stock, etc., focusing on complex data tables, forms, and RBAC restrictions at the API level or component rendering. Integrate shadcn/ui components for better presentation.
5. **Reporting & Settings (Weeks 13-14)**: Create dashboard page with KPI cards; implement report generation endpoints (`/api/reports/sales`) and display them via new pages. Add settings management functionality, potentially accessible only by Super Admin.

## Quality & Acceptance Checklist
The app must pass the following tests:
- **Loading States**: All data-heavy pages (dashboards, product lists) show appropriate loading skeletons or messages.
- **Empty States**: Pages like empty cart display a friendly message suggesting actions to return to browsing.
- **Error Handling**: Gracefully handle API errors during data fetching and form submissions with user-friendly error messages on the client side. Ensure server-side validation is communicated clearly (e.g., via toast notification).
- **Auth/Logout**: Login/register pages are functional; logout clears session properly, redirecting users appropriately based on their role.
- **RBAC Enforcement**: Role-based access controls work correctly – e.g., Branch Manager cannot see the 'Customers' module unless explicitly allowed. Navigation menus update based on user login state.
- **CRUD Functionality**: All create/update/delete operations are fully functional and backed by real database interactions (not local dev arrays). Delete actions have confirmation prompts where necessary.
- **Responsive Design**: Verify functionality across mobile, tablet, and desktop viewports using browser developer tools or actual devices. Navigation adapts correctly on all sizes.
- **No Dead Buttons/Links**: Every button click leads to a meaningful action; every link navigates appropriately (or is removed when backend auth is ready). Form submissions are handled properly without dead ends.