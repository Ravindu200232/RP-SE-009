# Implementation Plan - MegaMart Pro

## Project Overview & Design Philosophy
This enterprise-level retail platform requires a robust architecture supporting multiple roles (Super Admin, Admin, Branch Manager, Cashier, Inventory Staff, Customer) with distinct access patterns. The system will feature:
- A modular folder structure separating server and UI concerns
- Role-based navigation driven by user authentication state
- Consistent shadcn/ui component library for interactive elements
- MongoDB-backed data models ensuring scalability and performance
- Server-side rendering (SSR) and API routes handling business logic securely

## Requirement Summary
The MegaMart Pro system will support public-facing e-commerce, cashier POS operations, inventory management, supplier purchasing, and comprehensive admin dashboards. Key workflows include:
- Customer browsing, carting, and checkout
- Product search with filters/sort on listing pages
- Inventory tracking across branches with alerts
- Role-based data access for all user types

**Feature Inventory**
| ID | Feature / requirement                                       | User role        | Priority | Notes                                                                 |
|---|--------------------------------------------------------------|------------------|----------|----------------------------------------------------------------------|
| 1 | Public product browsing and search                           | All              | High     | Includes category/price filters                                    |
| 2 | Customer checkout                                             | Customer, Cashier| Medium   | Supports multiple payment methods                                   |
| 3 | Role-based dashboard navigation                              | Admin roles      | Critical | Navigation must change based on user role                             |
| 4 | Inventory stock management (low-stock alerts)                | Inventory Staff | High     | Must track branch-specific inventory                                |

## Architecture & Folder Strategy
The application will be structured as follows:
- **app/**: Contains Next.js Server Components, layout routes, and UI pages organized by module.
- **components/**: Reusable shadcn/ui primitives (Button, Input, Table) plus app-specific components like RoleNav.
- **lib/**
  - **models/**: Mongoose schemas for all MongoDB models. Each model is in a separate file named PascalCase (e.g., `Product.ts`).
  - **utils**: Shared data fetching helpers and validation functions.

### Folder Structure

app/
├── dashboard/             # Admin dashboards
│   ├── products/          # Product management page
│   └── ...                 # Other admin pages
├── public/                # Public-facing routes (non-API)
│   ├── home/              # Home route (/)
│   ├── product/[id]/      # Dynamic product detail page (/product/:slug)
│   └── ...                 # Cart, Checkout, etc.
└── api/                    # API Routes
  ├── auth/
  │   ├── login.ts
  │   └── register.ts
  └── products/             # Product CRUD endpoints
      ├── [id].ts           # Item-level operations
      └── index.ts          # List endpoint

lib/
├── models/
│   ├── User.ts            # Schema for users collection
│   ├── ...                # Other collections (Product, Stock, etc.)
└── utils/                 # Helper functions and validators


## Database Schema Summary
All MongoDB collections will be defined in `lib/models/` with explicit field definitions.

### ### User (lib/models/User.ts)
| Field              | Type          | Required | Notes                                                                 |
|--------------------|---------------|----------|----------------------------------------------------------------------|
| name               | String        | Optional  | Display name                                                        |
| email              | String        | Unique   | Login identifier                                                    |
| passwordHash       | String        | True     | Hashed password using bcrypt                                         |
| role               | Enum          | Required | One of 'superAdmin', 'admin', 'branchManager', 'cashier', 'inventoryStaff', 'customer' |
| branchId           | mongoose.Schema.Types.ObjectId | Optional | Reference to Branch model if applicable (for non-customer roles) |
| status             | String        | True     | 'active' or 'inactive'                                               |
| createdAt          | Date          | Auto     | Default: new Date()                                                  |
| updatedAt          | Date          | Auto     | Default: new Date(), updates on save                                 |

### ### Product (lib/models/Product.ts)
| Field              | Type          | Required | Notes                                                                 |
|--------------------|---------------|----------|----------------------------------------------------------------------|
| name               | String        | True     | Product title                                                        |
| sku                | String        | Unique   | Stock keeping unit                                                   |
| barcode            | String        | Optional  | Barcode string for scanning                                          |
| slug               | String        | Unique   | URL-friendly version of product name                                |
| description       | String        | Optional  | Detailed product description                                        |
| categoryId         | mongoose.Schema.Types.ObjectId | True     | Reference to Category model                                     |
| brandId            | mongoose.Schema.Types.ObjectId | True     | Reference to Brand model                                      |
| sellingPrice       | Number        | True     | Price for customer-facing                                            |
| costPrice          | Number        | Optional  | Internal purchase price                                              |
| discountPrice      | Number        | Optional  | Discounted price (if applicable)                                    |
| images             | Array         | Optional  | Array of image URLs                                                  |
| unit               | String        | True     | Unit type ('kg', 'pcs', etc.)                                         |
| reorderLevel       | Number        | True     | Minimum stock level before alert                                     |
| status             | String        | True     | 'active' or 'inactive'                                               |
| timestamps         | Date          | Auto     | Creation and update dates                                             |

### ### Stock (lib/models/Stock.ts)
| Field              | Type          | Required | Notes                                                                 |
|--------------------|---------------|----------|----------------------------------------------------------------------|
| productId          | mongoose.Schema.Types.ObjectId | True     | Reference to Product model                                  |
| branchId           | mongoose.Schema.Types.ObjectId | True     | Reference to Branch model                                    |
| quantity           | Number        | True     | Current stock level                                                  |
| reservedQuantity   | Number        | Optional  | Quantity currently on hold                                           |
| reorderLevel       | Number        | Inherited from Product schema (reference) | Minimum restock threshold                                          |

### User (lib/models/User.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| email | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| passwordHash | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| role | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| branchId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| createdAt | Date | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| updatedAt | Date | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Branch (lib/models/Branch.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| code | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| address | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| phone | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Category (lib/models/Category.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| slug | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| parentId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| description | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Brand (lib/models/Brand.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| slug | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| description | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Product (lib/models/Product.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| sku | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| barcode | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| slug | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| description | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| categoryId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| brandId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| sellingPrice | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| costPrice | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| discountPrice | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| images | Array | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| unit | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| reorderLevel | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Stock (lib/models/Stock.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| productId | ObjectId | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| branchId | ObjectId | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| quantity | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| reservedQuantity | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| reorderLevel | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Customer (lib/models/Customer.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| browse | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| products | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| cart | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| checkout | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| order | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| history | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Supplier (lib/models/Supplier.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| name | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| contactPerson | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| phone | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| email | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| address | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |

### PurchaseOrder (lib/models/PurchaseOrder.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| supplierId | ObjectId | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| branchId | ObjectId | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| items | Array | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| productId | ObjectId | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| quantity | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| costPrice | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| totalAmount | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |

### GRN (lib/models/GRN.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| purchaseOrderId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| supplierId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| branchId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| items | Array | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| productId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| quantity | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| costPrice | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| receivedBy | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| receivedAt | Date | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| totalAmount | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Sale (lib/models/Sale.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| invoiceNo | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| branchId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| customerId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| cashierId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| items | Array | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| productId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| quantity | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| price | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| discount | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| total | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| subtotal | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| discountTotal | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| taxTotal | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| grandTotal | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| paymentMethod | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| upi | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |

### OnlineOrder (lib/models/OnlineOrder.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| orderNo | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| customerId | ObjectId | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| items | Array | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| productId | ObjectId | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| quantity | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| price | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| total | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| shippingAddress | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| pending | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| confirmed | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| packed | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| shipped | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| delivered | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| paymentStatus | String | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |
| totalAmount | Number | Yes | From user input; preserve validation, unique, enum, and ref notes where specified. |

### Payment (lib/models/Payment.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| referenceNo | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| saleId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| orderId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| amount | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| method | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| status | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |

### StockMovement (lib/models/StockMovement.ts)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| productId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| branchId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| type | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| purchase | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| sale | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| adjustment | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| return | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| transfer | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| quantity | Number | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| negative | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| referenceId | ObjectId | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |
| note | String | Conditional | From user input; preserve validation, unique, enum, and ref notes where specified. |

## Page/Module List
This table lists all required UI routes and pages.

### Page/Module List
| Route                     | Page                                       | Type         | Access          | Purpose                                                                 |
|---------------------------|--------------------------------------------|--------------|-----------------|-------------------------------------------------------------------------|
| /                         | Home Page                                  | Server       | All             | Public landing page with hero, featured sections                        |
| /login                    | Login Page                                 | Server       | All             | Authentication entry point                                             |
| /register                 | Register Page                              | Server       | Customer        | Customer registration                                                   |
| /products                 | Product Listing                             | Server       | Customer        | Browse products by category and search                                  |
| /product/:slug            | Product Detail                             | Server       | Customer        | View product details, add to cart                                        |
| /cart                     | Cart Page                                   | Server       | Customer        | Manage shopping cart                                                    |
| /checkout                 | Checkout Page                              | Server       | Customer        | Process orders and payments                                              |
| /dashboard                | Admin Dashboard Overview                   | Server/Shell  | Admin roles     | KPI dashboard with summary metrics                                     |
| /dashboard/products      | Products Management                        | Server/Edit  | Admin, Branch Manager, Inventory Staff | CRUD for products                                                      |
| /products/[slug] | Product Details Page | Public | Public | Implement Product Details Page required by the user input. |
| /order-success | Order Success Page | Public | Public | Implement Order Success Page required by the user input. |
| /about | About Page | Public | Public | Implement About Page required by the user input. |
| /contact | Contact Page | Public | Public | Implement Contact Page required by the user input. |
| /dashboard/categories | Categories Page | Dashboard | Role-based | Implement Categories Page required by the user input. |
| /dashboard/brands | Brands Page | Dashboard | Role-based | Implement Brands Page required by the user input. |
| /dashboard/customers | Customers Page | Dashboard | Role-based | Implement Customers Page required by the user input. |
| /dashboard/suppliers | Suppliers Page | Dashboard | Role-based | Implement Suppliers Page required by the user input. |
| /dashboard/branches | Branches Page | Dashboard | Role-based | Implement Branches Page required by the user input. |
| /dashboard/users | Staff Users Page | Dashboard | Admin / Super Admin | Implement Staff Users Page required by the user input. |
| /dashboard/pos | POS Billing Page | Dashboard | Role-based | Implement POS Billing Page required by the user input. |
| /dashboard/inventory | Inventory Page | Dashboard | Role-based | Implement Inventory Page required by the user input. |
| /dashboard/grn | GRN Purchase Receiving Page | Dashboard | Role-based | Implement GRN Purchase Receiving Page required by the user input. |
| /dashboard/stock-adjustments | Stock Adjustment Page | Dashboard | Role-based | Implement Stock Adjustment Page required by the user input. |
| /dashboard/orders | Online Orders Page | Dashboard | Role-based | Implement Online Orders Page required by the user input. |
| /dashboard/sales | Invoice Sales History Page | Dashboard | Role-based | Implement Invoice Sales History Page required by the user input. |
| /dashboard/reports | Reports Page | Dashboard | Admin / Super Admin | Implement Reports Page required by the user input. |
| /dashboard/settings | Settings Page | Dashboard | Admin / Super Admin | Implement Settings Page required by the user input. |

## API Routes List
Concrete endpoints to be implemented:

- `GET /api/auth/login - Login endpoint (customer)`
- `POST /api/auth/register - Customer registration`
- `PUT /api/users/me - Update current user profile`

- GET /api/users - list/search User records - access(role-based)
- POST /api/users - create User record with validation - access(role-based)
- GET /api/users/:id - fetch one User record - access(role-based)
- PUT /api/users/:id - update User record - access(role-based)
- DELETE /api/users/:id - delete or deactivate User record - access(role-based)
- GET /api/branchs - list/search Branch records - access(role-based)
- POST /api/branchs - create Branch record with validation - access(role-based)
- GET /api/branchs/:id - fetch one Branch record - access(role-based)
- PUT /api/branchs/:id - update Branch record - access(role-based)
- DELETE /api/branchs/:id - delete or deactivate Branch record - access(role-based)
- GET /api/categories - list/search Category records - access(role-based)
- POST /api/categories - create Category record with validation - access(role-based)
- GET /api/categories/:id - fetch one Category record - access(role-based)
- PUT /api/categories/:id - update Category record - access(role-based)
- DELETE /api/categories/:id - delete or deactivate Category record - access(role-based)
- GET /api/brands - list/search Brand records - access(role-based)
- POST /api/brands - create Brand record with validation - access(role-based)
- GET /api/brands/:id - fetch one Brand record - access(role-based)
- PUT /api/brands/:id - update Brand record - access(role-based)
- DELETE /api/brands/:id - delete or deactivate Brand record - access(role-based)
- GET /api/products - list/search Product records - access(role-based)
- POST /api/products - create Product record with validation - access(role-based)
- GET /api/products/:id - fetch one Product record - access(role-based)
- PUT /api/products/:id - update Product record - access(role-based)
- DELETE /api/products/:id - delete or deactivate Product record - access(role-based)
- GET /api/stocks - list/search Stock records - access(role-based)
- POST /api/stocks - create Stock record with validation - access(role-based)
- GET /api/stocks/:id - fetch one Stock record - access(role-based)
- PUT /api/stocks/:id - update Stock record - access(role-based)
- DELETE /api/stocks/:id - delete or deactivate Stock record - access(role-based)
- GET /api/customers - list/search Customer records - access(role-based)
- POST /api/customers - create Customer record with validation - access(role-based)
- GET /api/customers/:id - fetch one Customer record - access(role-based)
- PUT /api/customers/:id - update Customer record - access(role-based)
- DELETE /api/customers/:id - delete or deactivate Customer record - access(role-based)
- GET /api/suppliers - list/search Supplier records - access(role-based)
- POST /api/suppliers - create Supplier record with validation - access(role-based)
- GET /api/suppliers/:id - fetch one Supplier record - access(role-based)
- PUT /api/suppliers/:id - update Supplier record - access(role-based)
- DELETE /api/suppliers/:id - delete or deactivate Supplier record - access(role-based)
- GET /api/purchase-orders - list/search PurchaseOrder records - access(role-based)
- POST /api/purchase-orders - create PurchaseOrder record with validation - access(role-based)
- GET /api/purchase-orders/:id - fetch one PurchaseOrder record - access(role-based)
- PUT /api/purchase-orders/:id - update PurchaseOrder record - access(role-based)
- DELETE /api/purchase-orders/:id - delete or deactivate PurchaseOrder record - access(role-based)
- GET /api/grns - list/search GRN records - access(role-based)
- POST /api/grns - create GRN record with validation - access(role-based)
- GET /api/grns/:id - fetch one GRN record - access(role-based)
- PUT /api/grns/:id - update GRN record - access(role-based)
- DELETE /api/grns/:id - delete or deactivate GRN record - access(role-based)
- GET /api/sales - list/search Sale records - access(role-based)
- POST /api/sales - create Sale record with validation - access(role-based)
- GET /api/sales/:id - fetch one Sale record - access(role-based)
- PUT /api/sales/:id - update Sale record - access(role-based)
- DELETE /api/sales/:id - delete or deactivate Sale record - access(role-based)
- GET /api/online-orders - list/search OnlineOrder records - access(role-based)
- POST /api/online-orders - create OnlineOrder record with validation - access(role-based)
- GET /api/online-orders/:id - fetch one OnlineOrder record - access(role-based)
- PUT /api/online-orders/:id - update OnlineOrder record - access(role-based)
- DELETE /api/online-orders/:id - delete or deactivate OnlineOrder record - access(role-based)
- GET /api/payments - list/search Payment records - access(role-based)
- POST /api/payments - create Payment record with validation - access(role-based)
- GET /api/payments/:id - fetch one Payment record - access(role-based)
- PUT /api/payments/:id - update Payment record - access(role-based)
- DELETE /api/payments/:id - delete or deactivate Payment record - access(role-based)
- GET /api/stock-movements - list/search StockMovement records - access(role-based)
- POST /api/stock-movements - create StockMovement record with validation - access(role-based)
- GET /api/stock-movements/:id - fetch one StockMovement record - access(role-based)
- PUT /api/stock-movements/:id - update StockMovement record - access(role-based)
- DELETE /api/stock-movements/:id - delete or deactivate StockMovement record - access(role-based)

## UI and Component Strategy
The app shell will use:
- Top navbar for public routes (/, login, register)
- Sidebar navigation for admin dashboards

Navigation components (`RoleNav`) will be server-side rendered based on the authenticated user's role. All interactive elements (buttons, inputs) must use shadcn/ui primitives.

## Page-by-Page Build Blueprint
### ### / - Home Page
**Sections**: Hero banner, Featured categories, Featured products carousel, Why Choose Us section.
**Functions**: Fetches featured data from API on server side.
**Data**: Public-facing models (Product, Category) via `/api/products/featured` and `/api/categories/public`.
**Design**: Clean layout with ample white space.

### ### /login - Login Page
**Sections**: LoginForm centered in a card, Auth demo footer.
**Functions**: Validates login credentials against API endpoints.
**Data**: User model from `/api/auth/login`.
**Design**: Simple authentication-focused page.

### ### /dashboard/products - Products Management
**Sections**: Product table with search bar, Add/Edit modal forms.
**Functions**: Fetches product list, handles CRUD operations via API routes.
**Data**: Product and Category models from `/api/products` endpoints.
**Design**: Admin dashboard styling with card-based UI elements.

### / - Home Page

**Sections**:
- Header, primary content area, and contextual actions for Home Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Home Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /login - Login Page

**Sections**:
- Header, primary content area, and contextual actions for Login Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Login Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /register - Register Page

**Sections**:
- Header, primary content area, and contextual actions for Register Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Register Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /products - Product Listing

**Sections**:
- Header, primary content area, and contextual actions for Product Listing.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Product Listing.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /product/:slug - Product Detail

**Sections**:
- Header, primary content area, and contextual actions for Product Detail.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Product Detail.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /cart - Cart Page

**Sections**:
- Header, primary content area, and contextual actions for Cart Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Cart Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /checkout - Checkout Page

**Sections**:
- Header, primary content area, and contextual actions for Checkout Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Checkout Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard - Admin Dashboard Overview

**Sections**:
- Header, primary content area, and contextual actions for Admin Dashboard Overview.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Admin Dashboard Overview.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/products - Products Management

**Sections**:
- Header, primary content area, and contextual actions for Products Management.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for ## API Routes List
Concrete endpoints to be implemented:

- GET /api/auth/login - Login endpoint (customer)
- POST /api/auth/register - Customer registration
- PUT /api/users/me - Update current user profile

- GET /api/users - list/search User records - access(role-based)
- POST /api/users - create User record with validation - access(role-based)
- GET /api/users/:id - fetch one User record - access(role-based)
- PUT /api/users/:id - update User record - access(role-based)
- DELETE /api/users/:id - delete or deactivate User record - access(role-based)
- GET /api/branchs - list/search Branch records - access(role-based)
- POST /api/branchs - create Branch record with validation - access(role-based)
- GET /api/branchs/:id - fetch one Branch record - access(role-based)
- PUT /api/branchs/:id - update Branch record - access(role-based)
- DELETE /api/branchs/:id - delete or deactivate Branch record - access(role-based)
- GET /api/categories - list/search Category records - access(role-based)
- POST /api/categories - create Category record with validation - access(role-based)
- GET /api/categories/:id - fetch one Category record - access(role-based)
- PUT /api/categories/:id - update Category record - access(role-based)
- DELETE /api/categories/:id - delete or deactivate Category record - access(role-based)
- GET /api/brands - list/search Brand records - access(role-based)
- POST /api/brands - create Brand record with validation - access(role-based)
- GET /api/brands/:id - fetch one Brand record - access(role-based)
- PUT /api/brands/:id - update Brand record - access(role-based)
- DELETE /api/brands/:id - delete or deactivate Brand record - access(role-based)
- GET /api/products - list/search Product records - access(role-based)
- POST /api/products - create Product record with validation - access(role-based)
- GET /api/products/:id - fetch one Product record - access(role-based)
- PUT /api/products/:id - update Product record - access(role-based)
- DELETE /api/products/:id - delete or deactivate Product record - access(role-based)
- GET /api/stocks - list/search Stock records - access(role-based)
- POST /api/stocks - create Stock record with validation - access(role-based)
- GET /api/stocks/:id - fetch one Stock record - access(role-based)
- PUT /api/stocks/:id - update Stock record - access(role-based)
- DELETE /api/stocks/:id - delete or deactivate Stock record - access(role-based)
- GET /api/customers - list/search Customer records - access(role-based)
- POST /api/customers - create Customer record with validation - access(role-based)
- GET /api/customers/:id - fetch one Customer record - access(role-based)
- PUT /api/customers/:id - update Customer record - access(role-based)
- DELETE /api/customers/:id - delete or deactivate Customer record - access(role-based)
- GET /api/suppliers - list/search Supplier records - access(role-based)
- POST /api/suppliers - create Supplier record with validation - access(role-based)
- GET /api/suppliers/:id - fetch one Supplier record - access(role-based)
- PUT /api/suppliers/:id - update Supplier record - access(role-based)
- DELETE /api/suppliers/:id - delete or deactivate Supplier record - access(role-based)
- GET /api/purchase-orders - list/search PurchaseOrder records - access(role-based)
- POST /api/purchase-orders - create PurchaseOrder record with validation - access(role-based)
- GET /api/purchase-orders/:id - fetch one PurchaseOrder record - access(role-based)
- PUT /api/purchase-orders/:id - update PurchaseOrder record - access(role-based)
- DELETE /api/purchase-orders/:id - delete or deactivate PurchaseOrder record - access(role-based)
- GET /api/grns - list/search GRN records - access(role-based)
- POST /api/grns - create GRN record with validation - access(role-based)
- GET /api/grns/:id - fetch one GRN record - access(role-based)
- PUT /api/grns/:id - update GRN record - access(role-based)
- DELETE /api/grns/:id - delete or deactivate GRN record - access(role-based)
- GET /api/sales - list/search Sale records - access(role-based)
- POST /api/sales - create Sale record with validation - access(role-based)
- GET /api/sales/:id - fetch one Sale record - access(role-based)
- PUT /api/sales/:id - update Sale record - access(role-based)
- DELETE /api/sales/:id - delete or deactivate Sale record - access(role-based)
- GET /api/online-orders - list/search OnlineOrder records - access(role-based)
- POST /api/online-orders - create OnlineOrder record with validation - access(role-based)
- GET /api/online-orders/:id - fetch one OnlineOrder record - access(role-based)
- PUT /api/online-orders/:id - update OnlineOrder record - access(role-based)
- DELETE /api/online-orders/:id - delete or deactivate OnlineOrder record - access(role-based)
- GET /api/payments - list/search Payment records - access(role-based)
- POST /api/payments - create Payment record with validation - access(role-based)
- GET /api/payments/:id - fetch one Payment record - access(role-based)
- PUT /api/payments/:id - update Payment record - access(role-based)
- DELETE /api/payments/:id - delete or deactivate Payment record - access(role-based)
- GET /api/stock-movements - list/search StockMovement records - access(role-based)
- POST /api/stock-movements - create StockMovement record with validation - access(role-based)
- GET /api/stock-movements/:id - fetch one StockMovement record - access(role-based)
- PUT /api/stock-movements/:id - update StockMovement record - access(role-based)
- DELETE /api/stock-movements/:id - delete or deactivate StockMovement record - access(role-based)

## UI and Component Strategy
The app shell will use:
- Top navbar for public routes (/, login, register)
- Sidebar navigation for admin dashboards

Navigation components (RoleNav) will be server-side rendered based on the authenticated user's role. All interactive elements (buttons, inputs) must use shadcn/ui primitives.

## Page-by-Page Build Blueprint
### ### / - Home Page
**Sections**: Hero banner, Featured categories, Featured products carousel, Why Choose Us section.
**Functions**: Fetches featured data from API on server side.
**Data**: Public-facing models (Product, Category) via /api/products/featured and /api/categories/public.
**Design**: Clean layout with ample white space.

### ### /login - Login Page
**Sections**: LoginForm centered in a card, Auth demo footer.
**Functions**: Validates login credentials against API endpoints.
**Data**: User model from /api/auth/login.
**Design**: Simple authentication-focused page.

### ### /dashboard/products - Products Management
**Sections**: Product table with search bar, Add/Edit modal forms.
**Functions**: Fetches product list, handles CRUD operations via API routes.
**Data**: Product and Category models from /api/products endpoints.
**Design**: Admin dashboard styling with card-based UI elements.

### /products/[slug] - Product Details Page

**Sections**:
- Header, primary content area, and contextual actions for Product Details Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Product Details Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /order-success - Order Success Page

**Sections**:
- Header, primary content area, and contextual actions for Order Success Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Order Success Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /about - About Page

**Sections**:
- Header, primary content area, and contextual actions for About Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for About Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /contact - Contact Page

**Sections**:
- Header, primary content area, and contextual actions for Contact Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Contact Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/categories - Categories Page

**Sections**:
- Header, primary content area, and contextual actions for Categories Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Categories Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/brands - Brands Page

**Sections**:
- Header, primary content area, and contextual actions for Brands Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Brands Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/customers - Customers Page

**Sections**:
- Header, primary content area, and contextual actions for Customers Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Customers Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/suppliers - Suppliers Page

**Sections**:
- Header, primary content area, and contextual actions for Suppliers Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Suppliers Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/branches - Branches Page

**Sections**:
- Header, primary content area, and contextual actions for Branches Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Branches Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/users - Staff Users Page

**Sections**:
- Header, primary content area, and contextual actions for Staff Users Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Staff Users Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/pos - POS Billing Page

**Sections**:
- Header, primary content area, and contextual actions for POS Billing Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for POS Billing Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/inventory - Inventory Page

**Sections**:
- Header, primary content area, and contextual actions for Inventory Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Inventory Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/grn - GRN Purchase Receiving Page

**Sections**:
- Header, primary content area, and contextual actions for GRN Purchase Receiving Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for GRN Purchase Receiving Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/stock-adjustments - Stock Adjustment Page

**Sections**:
- Header, primary content area, and contextual actions for Stock Adjustment Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Stock Adjustment Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/orders - Online Orders Page

**Sections**:
- Header, primary content area, and contextual actions for Online Orders Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Online Orders Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/sales - Invoice Sales History Page

**Sections**:
- Header, primary content area, and contextual actions for Invoice Sales History Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Invoice Sales History Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/reports - Reports Page

**Sections**:
- Header, primary content area, and contextual actions for Reports Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Reports Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/settings - Settings Page

**Sections**:
- Header, primary content area, and contextual actions for Settings Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for ## API Routes List
Concrete endpoints to be implemented:

- GET /api/auth/login - Login endpoint (customer)
- POST /api/auth/register - Customer registration
- PUT /api/users/me - Update current user profile

- GET /api/users - list/search User records - access(role-based)
- POST /api/users - create User record with validation - access(role-based)
- GET /api/users/:id - fetch one User record - access(role-based)
- PUT /api/users/:id - update User record - access(role-based)
- DELETE /api/users/:id - delete or deactivate User record - access(role-based)
- GET /api/branchs - list/search Branch records - access(role-based)
- POST /api/branchs - create Branch record with validation - access(role-based)
- GET /api/branchs/:id - fetch one Branch record - access(role-based)
- PUT /api/branchs/:id - update Branch record - access(role-based)
- DELETE /api/branchs/:id - delete or deactivate Branch record - access(role-based)
- GET /api/categories - list/search Category records - access(role-based)
- POST /api/categories - create Category record with validation - access(role-based)
- GET /api/categories/:id - fetch one Category record - access(role-based)
- PUT /api/categories/:id - update Category record - access(role-based)
- DELETE /api/categories/:id - delete or deactivate Category record - access(role-based)
- GET /api/brands - list/search Brand records - access(role-based)
- POST /api/brands - create Brand record with validation - access(role-based)
- GET /api/brands/:id - fetch one Brand record - access(role-based)
- PUT /api/brands/:id - update Brand record - access(role-based)
- DELETE /api/brands/:id - delete or deactivate Brand record - access(role-based)
- GET /api/products - list/search Product records - access(role-based)
- POST /api/products - create Product record with validation - access(role-based)
- GET /api/products/:id - fetch one Product record - access(role-based)
- PUT /api/products/:id - update Product record - access(role-based)
- DELETE /api/products/:id - delete or deactivate Product record - access(role-based)
- GET /api/stocks - list/search Stock records - access(role-based)
- POST /api/stocks - create Stock record with validation - access(role-based)
- GET /api/stocks/:id - fetch one Stock record - access(role-based)
- PUT /api/stocks/:id - update Stock record - access(role-based)
- DELETE /api/stocks/:id - delete or deactivate Stock record - access(role-based)
- GET /api/customers - list/search Customer records - access(role-based)
- POST /api/customers - create Customer record with validation - access(role-based)
- GET /api/customers/:id - fetch one Customer record - access(role-based)
- PUT /api/customers/:id - update Customer record - access(role-based)
- DELETE /api/customers/:id - delete or deactivate Customer record - access(role-based)
- GET /api/suppliers - list/search Supplier records - access(role-based)
- POST /api/suppliers - create Supplier record with validation - access(role-based)
- GET /api/suppliers/:id - fetch one Supplier record - access(role-based)
- PUT /api/suppliers/:id - update Supplier record - access(role-based)
- DELETE /api/suppliers/:id - delete or deactivate Supplier record - access(role-based)
- GET /api/purchase-orders - list/search PurchaseOrder records - access(role-based)
- POST /api/purchase-orders - create PurchaseOrder record with validation - access(role-based)
- GET /api/purchase-orders/:id - fetch one PurchaseOrder record - access(role-based)
- PUT /api/purchase-orders/:id - update PurchaseOrder record - access(role-based)
- DELETE /api/purchase-orders/:id - delete or deactivate PurchaseOrder record - access(role-based)
- GET /api/grns - list/search GRN records - access(role-based)
- POST /api/grns - create GRN record with validation - access(role-based)
- GET /api/grns/:id - fetch one GRN record - access(role-based)
- PUT /api/grns/:id - update GRN record - access(role-based)
- DELETE /api/grns/:id - delete or deactivate GRN record - access(role-based)
- GET /api/sales - list/search Sale records - access(role-based)
- POST /api/sales - create Sale record with validation - access(role-based)
- GET /api/sales/:id - fetch one Sale record - access(role-based)
- PUT /api/sales/:id - update Sale record - access(role-based)
- DELETE /api/sales/:id - delete or deactivate Sale record - access(role-based)
- GET /api/online-orders - list/search OnlineOrder records - access(role-based)
- POST /api/online-orders - create OnlineOrder record with validation - access(role-based)
- GET /api/online-orders/:id - fetch one OnlineOrder record - access(role-based)
- PUT /api/online-orders/:id - update OnlineOrder record - access(role-based)
- DELETE /api/online-orders/:id - delete or deactivate OnlineOrder record - access(role-based)
- GET /api/payments - list/search Payment records - access(role-based)
- POST /api/payments - create Payment record with validation - access(role-based)
- GET /api/payments/:id - fetch one Payment record - access(role-based)
- PUT /api/payments/:id - update Payment record - access(role-based)
- DELETE /api/payments/:id - delete or deactivate Payment record - access(role-based)
- GET /api/stock-movements - list/search StockMovement records - access(role-based)
- POST /api/stock-movements - create StockMovement record with validation - access(role-based)
- GET /api/stock-movements/:id - fetch one StockMovement record - access(role-based)
- PUT /api/stock-movements/:id - update StockMovement record - access(role-based)
- DELETE /api/stock-movements/:id - delete or deactivate StockMovement record - access(role-based)

## UI and Component Strategy
The app shell will use:
- Top navbar for public routes (/, login, register)
- Sidebar navigation for admin dashboards

Navigation components (RoleNav) will be server-side rendered based on the authenticated user's role. All interactive elements (buttons, inputs) must use shadcn/ui primitives.

## Page-by-Page Build Blueprint
### ### / - Home Page
**Sections**: Hero banner, Featured categories, Featured products carousel, Why Choose Us section.
**Functions**: Fetches featured data from API on server side.
**Data**: Public-facing models (Product, Category) via /api/products/featured and /api/categories/public.
**Design**: Clean layout with ample white space.

### ### /login - Login Page
**Sections**: LoginForm centered in a card, Auth demo footer.
**Functions**: Validates login credentials against API endpoints.
**Data**: User model from /api/auth/login.
**Design**: Simple authentication-focused page.

### ### /dashboard/products - Products Management
**Sections**: Product table with search bar, Add/Edit modal forms.
**Functions**: Fetches product list, handles CRUD operations via API routes.
**Data**: Product and Category models from /api/products endpoints.
**Design**: Admin dashboard styling with card-based UI elements.

### / - Home Page

**Sections**:
- Header, primary content area, and contextual actions for Home Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Home Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /login - Login Page

**Sections**:
- Header, primary content area, and contextual actions for Login Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Login Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /register - Register Page

**Sections**:
- Header, primary content area, and contextual actions for Register Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Register Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /products - Product Listing

**Sections**:
- Header, primary content area, and contextual actions for Product Listing.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Product Listing.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /product/:slug - Product Detail

**Sections**:
- Header, primary content area, and contextual actions for Product Detail.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Product Detail.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /cart - Cart Page

**Sections**:
- Header, primary content area, and contextual actions for Cart Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Cart Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /checkout - Checkout Page

**Sections**:
- Header, primary content area, and contextual actions for Checkout Page.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Checkout Page.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard - Admin Dashboard Overview

**Sections**:
- Header, primary content area, and contextual actions for Admin Dashboard Overview.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for Admin Dashboard Overview.

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

### /dashboard/products - Products Management

**Sections**:
- Header, primary content area, and contextual actions for Products Management.

**Functions**:
- Load required data, validate user actions, and support the interactions implied by this route.

**Data**:
- Use the models, API routes, or local state needed for ## API Routes List
Concrete endpoints to be implemented:

- GET /api/auth/login - Login endpoint (customer)
- POST /api/auth/register - Customer registration
- PUT /api/users/me - Update current user profile

- GET /api/users - list/search User records - access(role-based)
- POST /api/users - create User record with validation - access(role-based)
- GET /api/users/:id - fetch one User record - access(role-based)
- PUT /api/users/:id - update User record - access(role-based)
- DELETE /api/users/:id - delete or deactivate User record - access(role-based)
- GET /api/branchs - list/search Branch records - access(role-based)
- POST /api/branchs - create Branch record with validation - access(role-based)
- GET /api/branchs/:id - fetch one Branch record - access(role-based)
- PUT /api/branchs/:id - update Branch record - access(role-based)
- DELETE /api/branchs/:id - delete or deactivate Branch record - access(role-based)
- GET /api/categories - list/search Category records - access(role-based)
- POST /api/categories - create Category record with validation - access(role-based)
- GET /api/categories/:id - fetch one Category record - access(role-based)
- PUT /api/categories/:id - update Category record - access(role-based)
- DELETE /api/categories/:id - delete or deactivate Category record - access(role-based)
- GET /api/brands - list/search Brand records - access(role-based)
- POST /api/brands - create Brand record with validation - access(role-based)
- GET /api/brands/:id - fetch one Brand record - access(role-based)
- PUT /api/brands/:id - update Brand record - access(role-based)
- DELETE /api/brands/:id - delete or deactivate Brand record - access(role-based)
- GET /api/products - list/search Product records - access(role-based)
- POST /api/products - create Product record with validation - access(role-based)
- GET /api/products/:id - fetch one Product record - access(role-based)
- PUT /api/products/:id - update Product record - access(role-based)
- DELETE /api/products/:id - delete or deactivate Product record - access(role-based)
- GET /api/stocks - list/search Stock records - access(role-based)
- POST /api/stocks - create Stock record with validation - access(role-based)
- GET /api/stocks/:id - fetch one Stock record - access(role-based)
- PUT /api/stocks/:id - update Stock record - access(role-based)
- DELETE /api/stocks/:id - delete or deactivate Stock record - access(role-based)
- GET /api/customers - list/search Customer records - access(role-based)
- POST /api/customers - create Customer record with validation - access(role-based)
- GET /api/customers/:id - fetch one Customer record - access(role-based)
- PUT /api/customers/:id - update Customer record - access(role-based)
- DELETE /api/customers/:id - delete or deactivate Customer record - access(role-based)
- GET /api/suppliers - list/search Supplier records - access(role-based)
- POST /api/suppliers - create Supplier record with validation - access(role-based)
- GET /api/suppliers/:id - fetch one Supplier record - access(role-based)
- PUT /api/suppliers/:id - update Supplier record - access(role-based)
- DELETE /api/suppliers/:id - delete or deactivate Supplier record - access(role-based)
- GET /api/purchase-orders - list/search PurchaseOrder records - access(role-based)
- POST /api/purchase-orders - create PurchaseOrder record with validation - access(role-based)
- GET /api/purchase-orders/:id - fetch one PurchaseOrder record - access(role-based)
- PUT /api/purchase-orders/:id - update PurchaseOrder record - access(role-based)
- DELETE /api/purchase-orders/:id - delete or deactivate PurchaseOrder record - access(role-based)
- GET /api/grns - list/search GRN records - access(role-based)
- POST /api/grns - create GRN record with validation - access(role-based)
- GET /api/grns/:id - fetch one GRN record - access(role-based)
- PUT /api/grns/:id - update GRN record - access(role-based)
- DELETE /api/grns/:id - delete or deactivate GRN record - access(role-based)
- GET /api/sales - list/search Sale records - access(role-based)
- POST /api/sales - create Sale record with validation - access(role-based)
- GET /api/sales/:id - fetch one Sale record - access(role-based)
- PUT /api/sales/:id - update Sale record - access(role-based)
- DELETE /api/sales/:id - delete or deactivate Sale record - access(role-based)
- GET /api/online-orders - list/search OnlineOrder records - access(role-based)
- POST /api/online-orders - create OnlineOrder record with validation - access(role-based)
- GET /api/online-orders/:id - fetch one OnlineOrder record - access(role-based)
- PUT /api/online-orders/:id - update OnlineOrder record - access(role-based)
- DELETE /api/online-orders/:id - delete or deactivate OnlineOrder record - access(role-based)
- GET /api/payments - list/search Payment records - access(role-based)
- POST /api/payments - create Payment record with validation - access(role-based)
- GET /api/payments/:id - fetch one Payment record - access(role-based)
- PUT /api/payments/:id - update Payment record - access(role-based)
- DELETE /api/payments/:id - delete or deactivate Payment record - access(role-based)
- GET /api/stock-movements - list/search StockMovement records - access(role-based)
- POST /api/stock-movements - create StockMovement record with validation - access(role-based)
- GET /api/stock-movements/:id - fetch one StockMovement record - access(role-based)
- PUT /api/stock-movements/:id - update StockMovement record - access(role-based)
- DELETE /api/stock-movements/:id - delete or deactivate StockMovement record - access(role-based)

## UI and Component Strategy
The app shell will use:
- Top navbar for public routes (/, login, register)
- Sidebar navigation for admin dashboards

Navigation components (RoleNav) will be server-side rendered based on the authenticated user's role. All interactive elements (buttons, inputs) must use shadcn/ui primitives.

## Page-by-Page Build Blueprint
### ### / - Home Page
**Sections**: Hero banner, Featured categories, Featured products carousel, Why Choose Us section.
**Functions**: Fetches featured data from API on server side.
**Data**: Public-facing models (Product, Category) via /api/products/featured and /api/categories/public.
**Design**: Clean layout with ample white space.

### ### /login - Login Page
**Sections**: LoginForm centered in a card, Auth demo footer.
**Functions**: Validates login credentials against API endpoints.
**Data**: User model from /api/auth/login.
**Design**: Simple authentication-focused page.

### ### /dashboard/products - Products Management
**Sections**: Product table with search bar, Add/Edit modal forms.
**Functions**: Fetches product list, handles CRUD operations via API routes.
**Data**: Product and Category models from /api/products endpoints.
**Design**: Admin dashboard styling with card-based UI elements.

## Development Phases
1. **Core Models & Auth (Week 1-2)**
   - Implement User, Role, Branch schemas
   - Set up authentication system (/login, /register)
   - Create seed scripts for initial demo data

2. **Product Management Module (Week 3-4)**
   - Build Product schema and API endpoints
   - Develop public product listing page (/products)
   - Implement product detail view (/product/:slug)

3. **Inventory & Stock Tracking (Week 5)** 
   - Create inventory-related schemas (Stock, ReorderLevel)
   - Develop stock management dashboard for Inventory Staff

4. **Admin Dashboard Development (Week 6-7)**
   - Build KPI overview page (/dashboard)
   - Implement role-based navigation system
   - Add reports section with data visualization

5. **POS & Checkout System (Week 8)** 
   - Create cashier POS interface and API endpoints
   - Develop online checkout functionality

## Quality & Acceptance Checklist
- All pages load correctly on desktop, tablet, and mobile devices.
- Loading states appear during initial page loads or data fetches.
- Empty states are visible where appropriate (e.g., empty cart).
- Error handling displays user-friendly messages for API failures.
- Role-based access controls work as expected across all routes.
- RBAC enforces correct permissions on dashboard navigation..

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

## Development Phases
1. **Core Models & Auth (Week 1-2)**
   - Implement User, Role, Branch schemas
   - Set up authentication system (/login, /register)
   - Create seed scripts for initial demo data

2. **Product Management Module (Week 3-4)**
   - Build Product schema and API endpoints
   - Develop public product listing page (/products)
   - Implement product detail view (/product/:slug)

3. **Inventory & Stock Tracking (Week 5)** 
   - Create inventory-related schemas (Stock, ReorderLevel)
   - Develop stock management dashboard for Inventory Staff

4. **Admin Dashboard Development (Week 6-7)**
   - Build KPI overview page (/dashboard)
   - Implement role-based navigation system
   - Add reports section with data visualization

5. **POS & Checkout System (Week 8)** 
   - Create cashier POS interface and API endpoints
   - Develop online checkout functionality

## Quality & Acceptance Checklist
- All pages load correctly on desktop, tablet, and mobile devices.
- Loading states appear during initial page loads or data fetches.
- Empty states are visible where appropriate (e.g., empty cart).
- Error handling displays user-friendly messages for API failures.
- Role-based access controls work as expected across all routes.
- RBAC enforces correct permissions on dashboard navigation..

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

## Development Phases
1. **Core Models & Auth (Week 1-2)**
   - Implement User, Role, Branch schemas
   - Set up authentication system (/login, /register)
   - Create seed scripts for initial demo data

2. **Product Management Module (Week 3-4)**
   - Build Product schema and API endpoints
   - Develop public product listing page (/products)
   - Implement product detail view (/product/:slug)

3. **Inventory & Stock Tracking (Week 5)** 
   - Create inventory-related schemas (Stock, ReorderLevel)
   - Develop stock management dashboard for Inventory Staff

4. **Admin Dashboard Development (Week 6-7)**
   - Build KPI overview page (/dashboard)
   - Implement role-based navigation system
   - Add reports section with data visualization

5. **POS & Checkout System (Week 8)** 
   - Create cashier POS interface and API endpoints
   - Develop online checkout functionality

## Quality & Acceptance Checklist
- All pages load correctly on desktop, tablet, and mobile devices.
- Loading states appear during initial page loads or data fetches.
- Empty states are visible where appropriate (e.g., empty cart).
- Error handling displays user-friendly messages for API failures.
- Role-based access controls work as expected across all routes.
- RBAC enforces correct permissions on dashboard navigation..

**Design**:
- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.

## Development Phases
1. **Core Models & Auth (Week 1-2)**
   - Implement User, Role, Branch schemas
   - Set up authentication system (/login, /register)
   - Create seed scripts for initial demo data

2. **Product Management Module (Week 3-4)**
   - Build Product schema and API endpoints
   - Develop public product listing page (/products)
   - Implement product detail view (/product/:slug)

3. **Inventory & Stock Tracking (Week 5)** 
   - Create inventory-related schemas (Stock, ReorderLevel)
   - Develop stock management dashboard for Inventory Staff

4. **Admin Dashboard Development (Week 6-7)**
   - Build KPI overview page (/dashboard)
   - Implement role-based navigation system
   - Add reports section with data visualization

5. **POS & Checkout System (Week 8)** 
   - Create cashier POS interface and API endpoints
   - Develop online checkout functionality

## Quality & Acceptance Checklist
- All pages load correctly on desktop, tablet, and mobile devices.
- Loading states appear during initial page loads or data fetches.
- Empty states are visible where appropriate (e.g., empty cart).
- Error handling displays user-friendly messages for API failures.
- Role-based access controls work as expected across all routes.
- RBAC enforces correct permissions on dashboard navigation.
