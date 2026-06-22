"""App taxonomy — 20 categories, 300+ specific app types, smart classifier.

`classify(prompt)` returns a full AppClassification dict that drives:
  - design_planes.get_plane()  → section sequence, visual style, template
  - design_genome._BIAS        → structural genome axis preferences
  - landing_copy               → domain-specific copy for each section

The classifier is FAST and deterministic — keyword matching with a scoring
layer, no LLM in the hot path. Each keyword entry has a weight so domain-
specific terms score higher than generic ones.
"""
from __future__ import annotations
import re
from typing import TypedDict

# ---------------------------------------------------------------------------
# Type
# ---------------------------------------------------------------------------
class AppClassification(TypedDict):
    category_id: str       # snake_case category id (e.g. "ecommerce")
    category_name: str     # human label (e.g. "E-commerce / Online Selling")
    app_type: str          # specific type (e.g. "Online Store")
    access: str            # public | private | hybrid
    complexity: str        # simple | medium | advanced | enterprise
    has_auth: bool         # requires login system
    has_dashboard: bool    # requires an internal dashboard
    has_public_site: bool  # requires public marketing pages
    design_family: str     # editorial | saas | dark-tech | corporate | minimal | marketplace | portal | ai-platform
    section_pool: str      # which section pool to use (maps to design_planes)


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------
# Each entry:
#   id, name, access, complexity, design_family, app_types, keywords (weight 1-3)
_CATEGORIES: list[dict] = [
    {
        "id": "public_website",
        "name": "Basic / Public Website",
        "access": "public",
        "complexity": "simple",
        "design_family": "editorial",
        "has_auth": False, "has_dashboard": False, "has_public_site": True,
        "app_types": [
            "Company Website", "Corporate Website", "Portfolio Website",
            "Personal Blog", "News Website", "Magazine Website",
            "Landing Page", "Product Showcase Website", "Event Website",
            "Non-profit Website", "NGO Website", "Religious Organization Website",
            "Educational Institute Website", "Restaurant Website",
            "Hotel Website", "Travel Agency Website", "Real Estate Website",
            "Construction Company Website", "Law Firm Website",
            "Medical Clinic Website", "Fitness Website", "Gym Website",
            "Wedding Website", "Photography Website", "Architect Website",
        ],
        "keywords": {
            # weight-3: domain-specific
            "portfolio website": 3, "personal blog": 3, "news website": 3, "magazine website": 3,
            "restaurant website": 3, "hotel website": 3, "travel agency website": 3,
            "law firm website": 3, "wedding website": 3, "event website": 3,
            "non-profit website": 3, "ngo website": 3, "church website": 3,
            "photography website": 3, "architecture website": 3, "fitness website": 3,
            # weight-2: clear intent
            "company website": 2, "corporate website": 2, "landing page": 2,
            "brochure site": 2, "business website": 2, "informational website": 2,
            "product showcase": 2, "marketing website": 2, "gym website": 2,
            "medical clinic": 2, "construction company": 2,
            # weight-1: could be other things too
            "website": 1, "site": 1, "blog": 1, "homepage": 1,
        },
    },
    {
        "id": "ecommerce",
        "name": "E-commerce / Online Selling",
        "access": "hybrid",
        "complexity": "medium",
        "design_family": "marketplace",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Online Store", "Multi-vendor Marketplace", "Grocery Delivery App",
            "Food Ordering App", "Restaurant Ordering System", "Pharmacy Online Store",
            "Fashion Store", "Electronics Store", "Furniture Store", "Book Store",
            "Digital Products Store", "Subscription Box Website", "Auction Website",
            "Classified Ads Website", "Rental Marketplace", "B2B Wholesale Platform",
            "Dropshipping Store", "Print-on-demand Store",
            "Online Ticket Selling System", "Online Course Marketplace",
        ],
        "keywords": {
            "online store": 3, "ecommerce": 3, "e-commerce": 3, "shop": 3,
            "marketplace": 3, "multi-vendor": 3, "grocery delivery": 3,
            "food ordering": 3, "restaurant ordering": 3, "pharmacy store": 3,
            "fashion store": 3, "electronics store": 3, "furniture store": 3,
            "book store": 3, "digital products": 3, "subscription box": 3,
            "auction website": 3, "classified ads": 3, "rental marketplace": 3,
            "wholesale platform": 3, "dropshipping": 3, "print-on-demand": 3,
            "ticket selling": 3,
            "shopping cart": 2, "product catalog": 2, "checkout": 2, "storefront": 2,
            "vendor": 2, "seller": 2, "buyer": 2, "listing": 2,
            "cart": 1, "store": 1, "sell": 1, "buying": 1,
        },
    },
    {
        "id": "business_erp",
        "name": "Business Management / ERP",
        "access": "private",
        "complexity": "enterprise",
        "design_family": "corporate",
        "has_auth": True, "has_dashboard": True, "has_public_site": False,
        "app_types": [
            "ERP System", "POS System", "Inventory Management System",
            "Stock Management System", "Sales Management System",
            "Purchase Management System", "Supplier Management System",
            "Customer Management System", "CRM System", "HRM System",
            "Payroll Management System", "Employee Attendance System",
            "Task Management System", "Project Management System",
            "Asset Management System", "Document Management System",
            "Invoice Management System", "Quotation Management System",
            "Expense Management System", "Accounting System",
        ],
        "keywords": {
            "erp system": 3, "erp": 3, "pos system": 3, "point of sale": 3,
            "inventory management": 3, "stock management": 3, "sales management": 3,
            "purchase management": 3, "supplier management": 3, "crm system": 3,
            "hrm system": 3, "hr system": 3, "payroll": 3, "attendance system": 3,
            "project management": 3, "task management": 3, "asset management": 3,
            "document management": 3, "invoice management": 3, "quotation": 3,
            "expense management": 3, "accounting system": 3,
            "customer relationship": 2, "human resource": 2, "supply chain": 2,
            "business intelligence": 2, "management system": 2,
        },
    },
    {
        "id": "booking",
        "name": "Booking / Reservation",
        "access": "hybrid",
        "complexity": "medium",
        "design_family": "saas",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Hotel Booking System", "Room Reservation System",
            "Appointment Booking System", "Doctor Appointment System",
            "Salon Booking System", "Vehicle Rental Booking",
            "Event Booking System", "Ticket Reservation System",
            "Restaurant Table Booking", "Class Booking System",
            "Travel Package Booking", "Meeting Room Booking",
            "Coworking Space Booking", "Sports Ground Booking",
            "Service Provider Booking",
        ],
        "keywords": {
            "hotel booking": 3, "room reservation": 3, "appointment booking": 3,
            "doctor appointment": 3, "salon booking": 3, "vehicle rental": 3,
            "event booking": 3, "ticket reservation": 3, "table booking": 3,
            "class booking": 3, "travel package booking": 3, "meeting room": 3,
            "coworking booking": 3, "sports booking": 3,
            "booking system": 2, "reservation system": 2, "scheduling": 2,
            "book appointment": 2, "availability": 2, "slot": 2,
            "book": 1, "reserve": 1, "schedule": 1,
        },
    },
    {
        "id": "education",
        "name": "Education / Learning",
        "access": "hybrid",
        "complexity": "medium",
        "design_family": "saas",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "LMS — Learning Management System", "Online Course Platform",
            "Student Management System", "School Management System",
            "University Management System", "Exam Management System",
            "Quiz App", "Assignment Submission System", "E-library System",
            "Online Tutoring Platform", "Language Learning App",
            "Coding Learning Platform", "Flashcard App",
            "Attendance Tracking System", "Grade Management System",
        ],
        "keywords": {
            "lms": 3, "learning management": 3, "online course platform": 3,
            "student management": 3, "school management": 3, "university management": 3,
            "exam management": 3, "quiz app": 3, "assignment submission": 3,
            "e-library": 3, "tutoring platform": 3, "language learning": 3,
            "coding learning": 3, "flashcard app": 3, "grade management": 3,
            "online course": 2, "e-learning": 2, "education platform": 2,
            "course": 2, "student portal": 2, "teacher portal": 2,
            "school": 1, "university": 1, "college": 1, "student": 1, "lesson": 1,
        },
    },
    {
        "id": "healthcare",
        "name": "Healthcare / Medical",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "corporate",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Hospital Management System", "Clinic Management System",
            "Patient Portal", "Doctor Portal", "Pharmacy Management System",
            "Lab Report Management System", "Medical Appointment System",
            "Telemedicine App", "Health Record System", "Dental Clinic System",
            "Veterinary Clinic System", "Mental Health App",
            "Fitness Tracking App", "Diet Plan Management App",
            "Blood Donation Management",
        ],
        "keywords": {
            "hospital management": 3, "clinic management": 3, "patient portal": 3,
            "doctor portal": 3, "pharmacy management": 3, "lab report": 3,
            "medical appointment": 3, "telemedicine": 3, "health record": 3,
            "dental clinic": 3, "veterinary clinic": 3, "mental health": 3,
            "blood donation": 3, "fitness tracking app": 3, "diet plan": 3,
            "emr": 2, "ehr": 2, "electronic health record": 2, "medical system": 2,
            "hospital": 2, "clinic": 2, "patient": 2, "doctor": 2, "pharmacy": 2,
            "health": 1, "medical": 1, "treatment": 1, "medication": 1,
        },
    },
    {
        "id": "finance",
        "name": "Finance / Payment",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "corporate",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Online Banking Dashboard", "Expense Tracker", "Budget Planner",
            "Loan Management System", "Microfinance System",
            "Payment Gateway Dashboard", "Subscription Billing System",
            "Donation Management System", "Crypto Portfolio Tracker",
            "Tax Management System", "Insurance Management System",
            "Digital Wallet App", "Investment Tracking App",
            "Invoice + Payment Collection", "Financial Reporting Dashboard",
        ],
        "keywords": {
            "online banking": 3, "expense tracker": 3, "budget planner": 3,
            "loan management": 3, "microfinance": 3, "payment gateway": 3,
            "subscription billing": 3, "donation management": 3,
            "crypto portfolio": 3, "tax management": 3, "insurance management": 3,
            "digital wallet": 3, "investment tracking": 3, "payment collection": 3,
            "financial reporting": 3,
            "fintech": 2, "banking": 2, "accounting": 2, "finance": 2, "payment": 2,
            "wallet": 2, "billing": 2, "invoice": 2, "ledger": 2,
            "money": 1, "transaction": 1, "revenue": 1, "expense": 1,
        },
    },
    {
        "id": "social",
        "name": "Social / Community",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "saas",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Social Media App", "Community Forum", "Discussion Board",
            "Q&A Platform", "Dating App", "Chat App", "Messaging Platform",
            "Blogging Platform", "Creator Community Platform",
            "Membership Website", "Alumni Network", "Professional Network",
            "Fan Community App", "Review / Rating Platform", "Social Event App",
        ],
        "keywords": {
            "social media app": 3, "community forum": 3, "discussion board": 3,
            "q&a platform": 3, "dating app": 3, "chat app": 3, "messaging platform": 3,
            "blogging platform": 3, "creator community": 3, "membership website": 3,
            "alumni network": 3, "professional network": 3, "fan community": 3,
            "review platform": 3, "social event": 3,
            "social network": 2, "community": 2, "forum": 2, "messaging": 2,
            "feed": 2, "follow": 2, "network": 2, "members": 2,
            "social": 1, "community": 1, "chat": 1, "connect": 1,
        },
    },
    {
        "id": "saas",
        "name": "SaaS / Productivity",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "saas",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "SaaS Dashboard", "Team Collaboration App", "Notes App",
            "Calendar App", "Reminder App", "Kanban Board",
            "To-do List App", "File Storage App", "Password Manager",
            "Form Builder", "Survey Builder", "Email Marketing SaaS",
            "Analytics Dashboard", "Report Generator", "Workflow Automation",
            "AI Writing SaaS", "AI Image Generator", "AI Chatbot Platform",
            "AI App Builder", "No-code Website Builder",
        ],
        "keywords": {
            "saas dashboard": 3, "team collaboration": 3, "notes app": 3,
            "kanban board": 3, "file storage app": 3, "password manager": 3,
            "form builder": 3, "survey builder": 3, "email marketing saas": 3,
            "analytics dashboard": 3, "report generator": 3, "workflow automation": 3,
            "ai writing": 3, "ai image generator": 3, "chatbot platform": 3,
            "no-code builder": 3, "ai app builder": 3,
            "saas": 2, "productivity": 2, "workspace": 2, "collaboration": 2,
            "automation": 2, "dashboard": 2, "tool": 2, "platform": 2,
        },
    },
    {
        "id": "admin_dashboard",
        "name": "Admin Panel / Dashboard",
        "access": "private",
        "complexity": "advanced",
        "design_family": "corporate",
        "has_auth": True, "has_dashboard": True, "has_public_site": False,
        "app_types": [
            "Admin Dashboard", "Super Admin Panel", "Analytics Dashboard",
            "Sales Dashboard", "Inventory Dashboard", "HR Dashboard",
            "Finance Dashboard", "Customer Support Dashboard",
            "Marketing Dashboard", "Website CMS Dashboard",
            "User Management Dashboard", "Role Permission Management",
            "API Monitoring Dashboard", "Server Monitoring Dashboard",
            "Business Intelligence Dashboard",
        ],
        "keywords": {
            "admin dashboard": 3, "super admin": 3, "admin panel": 3,
            "sales dashboard": 3, "inventory dashboard": 3, "hr dashboard": 3,
            "finance dashboard": 3, "customer support dashboard": 3,
            "marketing dashboard": 3, "cms dashboard": 3,
            "user management": 3, "role permission": 3, "api monitoring": 3,
            "server monitoring": 3, "business intelligence": 3,
            "admin": 2, "panel": 2, "back-office": 2, "ops": 2, "control panel": 2,
        },
    },
    {
        "id": "content_management",
        "name": "Content Management",
        "access": "hybrid",
        "complexity": "medium",
        "design_family": "editorial",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "CMS — Content Management System", "Blog Management System",
            "News Publishing System", "Article Publishing Platform",
            "Media Library App", "Video Upload Platform",
            "Podcast Platform", "Photo Gallery App", "Digital Magazine App",
            "Documentation Website", "Knowledge Base System",
            "Help Center Website", "Wiki App", "FAQ Management System",
            "Newsletter Publishing System",
        ],
        "keywords": {
            "cms": 3, "content management": 3, "blog management": 3,
            "news publishing": 3, "article publishing": 3, "media library": 3,
            "video upload": 3, "podcast platform": 3, "photo gallery": 3,
            "digital magazine": 3, "documentation website": 3, "knowledge base": 3,
            "help center": 3, "wiki app": 3, "newsletter publishing": 3,
            "publishing": 2, "editorial": 2, "content": 2, "media": 2,
            "article": 2, "post": 2, "news": 2,
            "e-library": 3, "knowledge base": 3, "wiki app": 3, "help center": 3,
        },
    },
    {
        "id": "service_marketplace",
        "name": "Service Marketplace",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "marketplace",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Freelance Marketplace", "Home Service Marketplace",
            "Tutor Finder Platform", "Doctor Finder Platform",
            "Lawyer Finder Platform", "Mechanic Finder Platform",
            "Cleaning Service Platform", "Delivery Service Platform",
            "Repair Service Booking", "Job Marketplace",
            "Gig Marketplace", "Consultant Booking Platform",
            "Agency Marketplace", "Local Business Directory",
            "Professional Service Directory",
        ],
        "keywords": {
            "freelance marketplace": 3, "home service marketplace": 3,
            "tutor finder": 3, "doctor finder": 3, "lawyer finder": 3,
            "mechanic finder": 3, "cleaning service": 3, "delivery service platform": 3,
            "repair service": 3, "job marketplace": 3, "gig marketplace": 3,
            "consultant booking": 3, "agency marketplace": 3, "local business directory": 3,
            "service directory": 3,
            "service marketplace": 2, "provider": 2, "finder": 2, "directory": 2,
            "gig": 2, "freelance": 2, "job board": 2,
        },
    },
    {
        "id": "logistics",
        "name": "Logistics / Transport",
        "access": "hybrid",
        "complexity": "enterprise",
        "design_family": "corporate",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Delivery Management System", "Courier Tracking System",
            "Fleet Management System", "Vehicle Tracking Dashboard",
            "Taxi Booking App", "Bus Ticket Booking System",
            "Cargo Management System", "Warehouse Management System",
            "Route Planning App", "Driver Management System",
            "Fuel Management System", "Transport Company ERP",
            "Vehicle Service Management", "Vehicle Sales Management",
            "Spare Parts Inventory System",
        ],
        "keywords": {
            "delivery management": 3, "courier tracking": 3, "fleet management": 3,
            "vehicle tracking": 3, "taxi booking": 3, "bus ticket": 3,
            "cargo management": 3, "warehouse management": 3, "route planning": 3,
            "driver management": 3, "fuel management": 3, "transport erp": 3,
            "vehicle service": 3, "vehicle sales": 3, "spare parts": 3,
            "logistics": 2, "transport": 2, "delivery": 2, "shipping": 2,
            "tracking": 2, "fleet": 2, "driver": 2, "warehouse": 2,
        },
    },
    {
        "id": "real_estate",
        "name": "Real Estate / Property",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "editorial",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Real Estate Listing Website", "Property Management System",
            "Rental Management System", "Apartment Management System",
            "Tenant Portal", "Land Sales Website", "House Rental Platform",
            "Property Agent CRM", "Real Estate Marketplace",
            "Construction Project Portal", "Maintenance Request System",
            "Property Booking System", "Mortgage Calculator Website",
            "Real Estate Auction Platform", "Building Management System",
        ],
        "keywords": {
            "real estate listing": 3, "property management": 3, "rental management": 3,
            "apartment management": 3, "tenant portal": 3, "land sales": 3,
            "house rental": 3, "property agent": 3, "real estate marketplace": 3,
            "construction project": 3, "maintenance request": 3, "property booking": 3,
            "mortgage calculator": 3, "real estate auction": 3, "building management": 3,
            "real estate": 2, "property": 2, "rental": 2, "housing": 2,
            "apartment": 2, "tenant": 2, "landlord": 2, "broker": 2,
        },
    },
    {
        "id": "government",
        "name": "Government / Public Service",
        "access": "hybrid",
        "complexity": "enterprise",
        "design_family": "corporate",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Citizen Service Portal", "Complaint Management System",
            "Permit Application System", "Document Verification System",
            "Public Notice Website", "Election Information Website",
            "Taxpayer Portal", "Municipal Service Portal",
            "Public Transport Info System", "Government Appointment Booking",
            "Public Health Portal", "Police Complaint Portal",
            "Court Case Tracking System", "Land Registry System",
            "Public Grievance System",
        ],
        "keywords": {
            "citizen service": 3, "complaint management": 3, "permit application": 3,
            "document verification": 3, "public notice": 3, "election information": 3,
            "taxpayer portal": 3, "municipal service": 3, "public transport info": 3,
            "government booking": 3, "public health portal": 3, "police complaint": 3,
            "court case": 3, "land registry": 3, "public grievance": 3,
            "government": 2, "public service": 2, "civic": 2, "municipal": 2,
            "citizen": 2, "portal": 2,
        },
    },
    {
        "id": "entertainment",
        "name": "Entertainment / Media",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "dark-tech",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Video Streaming Platform", "Music Streaming Website",
            "Movie Review Website", "Gaming Community Website",
            "Online Radio Platform", "Event Streaming Platform",
            "Meme Sharing App", "Fan Club Website",
            "Podcast Hosting Platform", "Digital Art Gallery",
            "Anime / Manga Website", "Sports News Website",
            "Live Score Website", "Entertainment Blog",
            "Ticket Booking for Shows",
        ],
        "keywords": {
            "video streaming": 3, "music streaming": 3, "movie review": 3,
            "gaming community": 3, "online radio": 3, "event streaming": 3,
            "meme sharing": 3, "fan club": 3, "podcast hosting": 3,
            "digital art gallery": 3, "anime website": 3, "sports news": 3,
            "live score": 3, "entertainment blog": 3, "show tickets": 3,
            "streaming": 2, "media platform": 2, "entertainment": 2, "gaming": 2,
            "podcast": 2, "music": 2, "video": 2, "sport": 2,
        },
    },
    {
        "id": "ai_automation",
        "name": "AI / Automation",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "ai-platform",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "AI Chatbot Web App", "AI Customer Support Agent",
            "AI Code Generator", "AI Website Builder",
            "AI App Generator", "AI SRS Generator",
            "AI Resume Builder", "AI Cover Letter Generator",
            "AI Image Generator", "AI Voice Generator",
            "AI Document Analyzer", "AI PDF Chat App",
            "AI Data Analysis Dashboard", "AI Marketing Assistant",
            "AI Email Writer", "AI Agent Workflow Builder",
            "AI Meeting Summary App", "AI Research Assistant",
            "AI Learning Tutor", "AI Business Plan Generator",
        ],
        "keywords": {
            "ai chatbot": 3, "ai customer support": 3, "ai code generator": 3,
            "ai website builder": 3, "ai app generator": 3, "ai srs": 3,
            "ai resume builder": 3, "ai cover letter": 3, "ai image generator": 3,
            "ai voice generator": 3, "ai document analyzer": 3, "ai pdf chat": 3,
            "ai data analysis": 3, "ai marketing": 3, "ai email": 3,
            "ai workflow": 3, "ai meeting": 3, "ai research": 3,
            "ai tutor": 3, "ai business plan": 3,
            "artificial intelligence": 2, "machine learning": 2, "llm": 2, "gpt": 2,
            "generative ai": 2, "ai-powered": 2, "ai tool": 2, "ai platform": 2,
            "ai": 1, "automation": 1, "intelligent": 1, "smart": 1,
        },
    },
    {
        "id": "security",
        "name": "Security / Access Control",
        "access": "private",
        "complexity": "advanced",
        "design_family": "corporate",
        "has_auth": True, "has_dashboard": True, "has_public_site": False,
        "app_types": [
            "Login / Register System", "Role-based Access Control App",
            "User Permission Management", "Two-factor Authentication System",
            "Admin Approval System", "Audit Log System",
            "Secure Document Portal", "Visitor Management System",
            "Identity Verification System", "Access Request Management System",
        ],
        "keywords": {
            "login register system": 3, "role-based access": 3,
            "user permission": 3, "two-factor authentication": 3,
            "admin approval": 3, "audit log": 3, "secure document": 3,
            "visitor management": 3, "identity verification": 3,
            "access request": 3,
            "rbac": 2, "authentication": 2, "authorization": 2, "security": 2,
            "permissions": 2, "access control": 2,
        },
    },
    {
        "id": "internal_portal",
        "name": "Internal Company Portal",
        "access": "private",
        "complexity": "medium",
        "design_family": "corporate",
        "has_auth": True, "has_dashboard": True, "has_public_site": False,
        "app_types": [
            "Employee Portal", "Staff Portal", "Client Portal",
            "Vendor Portal", "Partner Portal", "Franchise Portal",
            "Dealer Portal", "Manager Dashboard",
            "Internal Helpdesk", "Knowledge Sharing Portal",
        ],
        "keywords": {
            "employee portal": 3, "staff portal": 3, "client portal": 3,
            "vendor portal": 3, "partner portal": 3, "franchise portal": 3,
            "dealer portal": 3, "manager dashboard": 3,
            "internal helpdesk": 3, "knowledge sharing": 3,
            "internal portal": 2, "intranet": 2, "company portal": 2,
            "staff": 2, "employee": 2, "internal": 2,
        },
    },
    {
        "id": "hybrid_app",
        "name": "Hybrid Web App",
        "access": "hybrid",
        "complexity": "advanced",
        "design_family": "saas",
        "has_auth": True, "has_dashboard": True, "has_public_site": True,
        "app_types": [
            "Public Website + Admin Panel", "Public Website + Customer Portal",
            "E-commerce + POS", "Hospital Website + Patient Portal",
            "School Website + Student Portal",
            "Real Estate Website + Agent Dashboard",
            "Restaurant Website + Ordering System",
            "Travel Website + Booking System",
            "Company Website + HR Portal",
            "SaaS Landing Page + User Dashboard",
        ],
        "keywords": {
            "website with admin": 2, "website with portal": 2,
            "ecommerce with pos": 3, "hospital with patient": 2,
            "school with student": 2, "real estate with agent": 2,
            "restaurant with ordering": 3, "travel with booking": 2,
            "saas with dashboard": 2, "website plus": 2,
            "ordering system": 3, "with admin panel": 3,
            "with patient portal": 3, "with student portal": 3,
            "hybrid": 1, "full stack": 1, "complete system": 1,
        },
    },
]

# ---------------------------------------------------------------------------
# Fast classifier
# ---------------------------------------------------------------------------
def _score_category(cat: dict, text: str) -> float:
    """Score a category against prompt text using weighted keyword matching."""
    score = 0.0
    for kw, weight in cat["keywords"].items():
        if kw in text:
            score += weight
    return score


def _score_type(app_type: str, text: str) -> float:
    """Score a specific app type name against prompt text."""
    words = re.sub(r"[^a-z0-9 ]", " ", app_type.lower()).split()
    matches = sum(1 for w in words if len(w) > 3 and w in text)
    return matches / max(len(words), 1)


def classify(prompt: str) -> AppClassification:
    """Classify a user prompt into the full AppClassification schema.

    Algorithm:
    1. Normalize the prompt.
    2. Score ALL categories (O(n * keywords)).
    3. Pick the highest-scoring category (fallback: saas).
    4. Score app types within that category (O(types)).
    5. Return full classification.
    """
    if not prompt:
        return _default_classification()

    text = " " + re.sub(r"[^a-z0-9 /+\-]", " ", prompt.lower()) + " "

    # --- Step 1: score categories ---
    scores = [(cat, _score_category(cat, text)) for cat in _CATEGORIES]
    scores.sort(key=lambda x: x[1], reverse=True)
    best_cat, best_score = scores[0]

    # Fall back to saas when nothing matched at all (empty/gibberish prompt)
    if best_score == 0:
        return _default_classification()

    # --- Step 2: score app types within category ---
    type_scores = [(t, _score_type(t, text)) for t in best_cat["app_types"]]
    type_scores.sort(key=lambda x: x[1], reverse=True)
    best_type = type_scores[0][0] if type_scores else best_cat["app_types"][0]

    # --- Step 3: determine complexity from prompt length & keywords ---
    enterprise_kws = ["enterprise", "erp", "multi-tenant", "large scale", "corporate", "organization-wide"]
    advanced_kws = ["multi-role", "workflow", "analytics", "real-time", "api", "integration", "dashboard"]
    simple_kws = ["simple", "basic", "minimal", "one-page", "landing", "portfolio", "blog"]

    complexity = best_cat["complexity"]
    if any(k in text for k in enterprise_kws):
        complexity = "enterprise"
    elif any(k in text for k in advanced_kws) and complexity not in ("enterprise",):
        complexity = "advanced"
    elif any(k in text for k in simple_kws) and complexity not in ("enterprise", "advanced"):
        complexity = "simple"

    return AppClassification(
        category_id=best_cat["id"],
        category_name=best_cat["name"],
        app_type=best_type,
        access=best_cat["access"],
        complexity=complexity,
        has_auth=best_cat["has_auth"],
        has_dashboard=best_cat["has_dashboard"],
        has_public_site=best_cat["has_public_site"],
        design_family=best_cat["design_family"],
        section_pool=best_cat["id"],
    )


def _default_classification() -> AppClassification:
    return AppClassification(
        category_id="saas", category_name="SaaS / Productivity",
        app_type="SaaS Dashboard", access="hybrid", complexity="medium",
        has_auth=True, has_dashboard=True, has_public_site=True,
        design_family="saas", section_pool="saas",
    )


def get_category(category_id: str) -> dict | None:
    """Return the full category dict by id."""
    return next((c for c in _CATEGORIES if c["id"] == category_id), None)


def all_category_ids() -> list[str]:
    return [c["id"] for c in _CATEGORIES]


def all_app_types() -> list[str]:
    """Flat list of all 300+ app types across all categories."""
    return [t for c in _CATEGORIES for t in c["app_types"]]
