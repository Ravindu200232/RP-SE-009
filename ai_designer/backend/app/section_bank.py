"""Section bank — landing pages composed from REMIXED design pieces.

The pieces were learned from the user's own projects (CleanMate, lms-ui,
Audio shop, photoShop, CTSE) and rewritten into our token + copy-slot system:
each section is an independent JSX fragment with UNIQUE const names and a
unique slice of the copy anchors, so any combination stays valid JSX and
`landing_copy.apply` fills every chosen section. A composed landing = one
hero + N MIDDLE sections from section_catalog + closing CTA/footer — hundreds of
orderings, so no two generated sites assemble the same page.
"""
import os
import random

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library_next", "sections")

HEROES = [
    ("HeroSlider",          "hero_slider.jsx"),
    ("HeroSplitRadial",     "hero_split_radial.jsx"),
    ("HeroGradientGlow",    "hero_gradient_glow.jsx"),
    ("HeroMinimalLeft",     "hero_minimal_left.jsx"),
    ("HeroProductCard",     "hero_product_card.jsx"),
    ("HeroEditorialSerif",  "hero_editorial_serif.jsx"),
    ("HeroSplitScreen",     "hero_split_screen.jsx"),
    ("HeroStatsStrip",      "hero_stats_strip.jsx"),
    ("HeroCenteredClean",   "hero_centered_clean.jsx"),
    ("HeroPhotoLeftDark",   "hero_photo_left_dark.jsx"),
]
_HERO_BY_FILE = {f: (n, f) for n, f in HEROES}

# Map design_plane hero_variant → preferred hero JSX file
_PLANE_HERO_FILE = {
    "product-showcase":   "hero_product_card.jsx",
    "full-image":         "hero_editorial_serif.jsx",
    "saas-split":         "hero_split_radial.jsx",
    "dashboard-preview":  "hero_stats_strip.jsx",
    "search-booking":     "hero_split_screen.jsx",
    "editorial":          "hero_editorial_serif.jsx",
    "split":              "hero_split_radial.jsx",
    "card-stack":         "hero_centered_clean.jsx",
    "stats-first":        "hero_stats_strip.jsx",
    "ai-demo":            "hero_gradient_glow.jsx",
    "cinematic-hero":     "hero_slider.jsx",
    "entertainment-dark": "hero_photo_left_dark.jsx",
    "civic-centered":     "hero_centered_clean.jsx",
    "fintech-trust":      "hero_gradient_glow.jsx",
    "clinical-split":     "hero_minimal_left.jsx",
    "portal-access":      "hero_minimal_left.jsx",
    "security-shield":    "hero_minimal_left.jsx",
}

MIDDLES = [
    ("StatsAmbient",  "stats_ambient.jsx"),
    ("FeatureTiles",  "feature_tiles.jsx"),
    ("GalleryMosaic", "gallery_mosaic.jsx"),
    ("WhyChooseSplit","whychoose_split.jsx"),
    ("ReviewsGrid",   "reviews_grid.jsx"),
    ("PricingTiers",  "pricing_tiers.jsx"),
    ("FaqList",       "faq_list.jsx"),
    ("BannerCta",     "banner_cta.jsx"),
]
CLOSER = ("CtaFooter", "cta_footer.jsx")

_HEADER = """'use client';
import * as React from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { Icon } from '@/components/ui/icon';

"""

# ---------------------------------------------------------------------------
# Category-specific heading / eyebrow overrides.
# Keys are the generic placeholder text found in section catalog templates.
# Values are what that text should become for each category.
# Applied as string substitution after rendering — zero JSX changes needed.
# ---------------------------------------------------------------------------
_CATEGORY_COPY: dict[str, dict[str, str]] = {
    "public_website": {
        "Everything you need in one place":    "Everything on our menu",
        "A simpler way to run the day to day": "An unforgettable dining experience awaits",
        "Up and running in three steps":        "Reserve your table in three easy steps",
        "A look inside":                        "A taste of the experience",
        "Trusted by teams everywhere":          "Loved by food enthusiasts everywhere",
        "Capabilities":                         "What we offer",
        "Why us":                               "Why dine with us",
        "How it works":                         "How to make a reservation",
        "Platform":                             "About our restaurant",
        "Results teams can measure":            "Moments guests remember forever",
        "One workspace, every angle":           "Every detail, perfectly crafted",
        "See it in action":                     "Take a virtual tour",
        "A two-minute walkthrough":             "Explore our restaurant in 2 minutes",
        "Built by a team that sweats the details": "Crafted with passion, served with love",
        "About":                                "Our story",
        "Browse by what you need":              "Browse our menu",
        "Featured Products":                    "Featured dishes",
        "Expert doctors, compassionate care":   "Authentic cuisine, exceptional service",
        "Latest Articles":                      "Chef's journal",
    },
    "ecommerce": {
        "Everything you need in one place":    "Shop everything you love, all in one place",
        "A simpler way to run the day to day": "Shopping the way it should be",
        "Up and running in three steps":        "Order in three easy steps",
        "A look inside":                        "From our latest collection",
        "Trusted by teams everywhere":          "Loved by shoppers worldwide",
        "Capabilities":                         "Why shop with us",
        "Why us":                               "Why customers love us",
        "How it works":                         "How to place an order",
        "Platform":                             "Our collections",
        "Results teams can measure":            "Results that drive sales",
        "One workspace, every angle":           "One store, endless possibilities",
        "See it in action":                     "See our collections",
        "A two-minute walkthrough":             "Shop smarter in 2 minutes",
        "Built by a team that sweats the details": "Curated with care, delivered with love",
        "About":                                "Our brand story",
        "Browse by what you need":              "Shop by category",
        "Featured Products":                    "Best sellers",
        "Expert doctors, compassionate care":   "Premium quality, exceptional value",
        "Latest Articles":                      "Style journal",
    },
    "business_erp": {
        "Everything you need in one place":    "All your operations, one dashboard",
        "A simpler way to run the day to day": "Run your business with clarity and control",
        "Up and running in three steps":        "Go live in three simple steps",
        "A look inside":                        "The platform in action",
        "Trusted by teams everywhere":          "Trusted by businesses like yours",
        "Capabilities":                         "Platform capabilities",
        "Why us":                               "Why businesses choose us",
        "How it works":                         "How to get started",
        "Platform":                             "The platform",
        "Results teams can measure":            "Business outcomes you can measure",
        "One workspace, every angle":           "One platform, every operation",
        "See it in action":                     "See the platform",
        "A two-minute walkthrough":             "Your ERP in 2 minutes",
        "Built by a team that sweats the details": "Built for the way real businesses work",
        "About":                                "About the platform",
        "Latest Articles":                      "Business insights",
    },
    "booking": {
        "Everything you need in one place":    "Your perfect stay, all in one place",
        "A simpler way to run the day to day": "Reserve, arrive, and relax",
        "Up and running in three steps":        "Book your stay in three simple steps",
        "A look inside":                        "Our rooms and spaces",
        "Trusted by teams everywhere":          "Loved by travellers worldwide",
        "Capabilities":                         "Why guests love us",
        "Why us":                               "Why book with us",
        "How it works":                         "How to book your stay",
        "Platform":                             "Our property",
        "Results teams can measure":            "Why guests keep coming back",
        "One workspace, every angle":           "One booking, every detail handled",
        "See it in action":                     "See our property",
        "A two-minute walkthrough":             "Your stay in 2 minutes",
        "Built by a team that sweats the details": "Designed for unforgettable stays",
        "About":                                "About our property",
        "Browse by what you need":              "Browse room types",
        "Latest Articles":                      "Travel journal",
    },
    "education": {
        "Everything you need in one place":    "Everything you need to master your craft",
        "A simpler way to run the day to day": "A better way to learn, every day",
        "Up and running in three steps":        "Start learning in three steps",
        "A look inside":                        "From our course library",
        "Trusted by teams everywhere":          "Trusted by thousands of learners",
        "Capabilities":                         "What you'll learn",
        "Why us":                               "Why students choose us",
        "How it works":                         "How learning works",
        "Platform":                             "The platform",
        "Results teams can measure":            "Measurable learning outcomes",
        "One workspace, every angle":           "One platform, endless learning paths",
        "See it in action":                     "See the learning experience",
        "A two-minute walkthrough":             "Learning in 2 minutes",
        "Built by a team that sweats the details": "Built by educators, for learners",
        "About":                                "Our story",
        "Latest Articles":                      "Learning resources",
    },
    "healthcare": {
        "Everything you need in one place":    "Complete care, all in one place",
        "A simpler way to run the day to day": "A better patient experience, end to end",
        "Up and running in three steps":        "Book an appointment in three steps",
        "A look inside":                        "Our modern facilities",
        "Trusted by teams everywhere":          "Trusted by patients and providers",
        "Capabilities":                         "Our specialities",
        "Why us":                               "Why patients choose us",
        "How it works":                         "How to book an appointment",
        "Platform":                             "Our clinic",
        "Results teams can measure":            "Health outcomes that matter",
        "One workspace, every angle":           "Comprehensive care, under one roof",
        "See it in action":                     "Inside our clinic",
        "A two-minute walkthrough":             "Your care in 2 minutes",
        "Built by a team that sweats the details": "Built with compassion, designed for care",
        "About":                                "About our clinic",
        "Browse by what you need":              "Find a specialist",
        "Latest Articles":                      "Health & wellness",
    },
    "finance": {
        "Everything you need in one place":    "All your finances in one clear view",
        "A simpler way to run the day to day": "Financial clarity at a glance",
        "Up and running in three steps":        "Track your finances in three steps",
        "A look inside":                        "Your financial dashboard",
        "Trusted by teams everywhere":          "Trusted by finance professionals",
        "Capabilities":                         "What you get",
        "Why us":                               "Why finance teams use us",
        "How it works":                         "How it works",
        "Platform":                             "The platform",
        "Results teams can measure":            "Financial results, month after month",
        "One workspace, every angle":           "Every transaction, fully in view",
        "See it in action":                     "See the dashboard",
        "A two-minute walkthrough":             "Your finances in 2 minutes",
        "Built by a team that sweats the details": "Built by finance experts, for finance teams",
        "About":                                "About us",
        "Latest Articles":                      "Finance insights",
    },
    "social": {
        "Everything you need in one place":    "Everything your community needs",
        "A simpler way to run the day to day": "Connect, share, and grow together",
        "Up and running in three steps":        "Join the community in three steps",
        "A look inside":                        "Community highlights",
        "Trusted by teams everywhere":          "Loved by communities worldwide",
        "Capabilities":                         "Platform features",
        "Why us":                               "Why members love us",
        "How it works":                         "How to get started",
        "Platform":                             "The community",
        "Results teams can measure":            "Community impact in numbers",
        "One workspace, every angle":           "One community, endless connections",
        "See it in action":                     "See the community",
        "A two-minute walkthrough":             "The community in 2 minutes",
        "Built by a team that sweats the details": "Built to bring people together",
        "About":                                "About our community",
        "Latest Articles":                      "Community news",
    },
    "saas": {
        "Everything you need in one place":    "Every tool your team needs, in one place",
        "A simpler way to run the day to day": "Ship faster, collaborate better",
        "Up and running in three steps":        "Launch your workspace in three steps",
        "A look inside":                        "The platform in action",
        "Trusted by teams everywhere":          "Trusted by high-growth teams",
        "Capabilities":                         "What you can build",
        "Why us":                               "Why teams switch to us",
        "How it works":                         "How to get started",
        "Platform":                             "The platform",
        "Results teams can measure":            "Team performance, measured",
        "One workspace, every angle":           "One platform, every workflow",
        "See it in action":                     "See the platform",
        "A two-minute walkthrough":             "The platform in 2 minutes",
        "Built by a team that sweats the details": "Built by builders, for builders",
        "About":                                "About us",
        "Latest Articles":                      "Product updates",
    },
    "admin_dashboard": {
        "Everything you need in one place":    "Full platform control, centralized",
        "A simpler way to run the day to day": "Total control, zero complexity",
        "Up and running in three steps":        "Set up your admin panel in three steps",
        "A look inside":                        "Dashboard at a glance",
        "Trusted by teams everywhere":          "Trusted by ops teams everywhere",
        "Capabilities":                         "Admin capabilities",
        "Why us":                               "Why ops teams trust us",
        "How it works":                         "How to set up",
        "Platform":                             "The admin suite",
        "Results teams can measure":            "Operations outcomes, tracked",
        "One workspace, every angle":           "One panel, total control",
        "See it in action":                     "See the admin panel",
        "A two-minute walkthrough":             "The panel in 2 minutes",
        "Built by a team that sweats the details": "Built for the teams that keep things running",
        "About":                                "About the suite",
        "Latest Articles":                      "Ops insights",
    },
    "content_management": {
        "Everything you need in one place":    "All your content, perfectly organized",
        "A simpler way to run the day to day": "Publish smarter, reach further",
        "Up and running in three steps":        "Start publishing in three steps",
        "A look inside":                        "Latest articles",
        "Trusted by teams everywhere":          "Trusted by content teams everywhere",
        "Capabilities":                         "Publishing capabilities",
        "Why us":                               "Why content teams choose us",
        "How it works":                         "How to get started",
        "Platform":                             "The CMS",
        "Results teams can measure":            "Content results that matter",
        "One workspace, every angle":           "One CMS, every content type",
        "See it in action":                     "See the editor",
        "A two-minute walkthrough":             "Your CMS in 2 minutes",
        "Built by a team that sweats the details": "Built for modern content teams",
        "Latest Articles":                      "From the blog",
    },
    "service_marketplace": {
        "Everything you need in one place":    "Every service, every skill, one platform",
        "A simpler way to run the day to day": "Hire top talent in minutes",
        "Up and running in three steps":        "Get started in three steps",
        "A look inside":                        "Featured services",
        "Trusted by teams everywhere":          "Trusted by clients worldwide",
        "Capabilities":                         "What you can do",
        "Why us":                               "Why clients choose us",
        "How it works":                         "How it works",
        "Platform":                             "The marketplace",
        "Results teams can measure":            "Results clients can rely on",
        "One workspace, every angle":           "One marketplace, every service",
        "See it in action":                     "Browse services",
        "A two-minute walkthrough":             "The marketplace in 2 minutes",
        "Built by a team that sweats the details": "Built to connect great work with great clients",
        "Latest Articles":                      "Success stories",
    },
    "logistics": {
        "Everything you need in one place":    "Every shipment, every route, one dashboard",
        "A simpler way to run the day to day": "Deliver smarter, every time",
        "Up and running in three steps":        "Set up your fleet in three steps",
        "A look inside":                        "Fleet operations view",
        "Trusted by teams everywhere":          "Trusted by logistics teams everywhere",
        "Capabilities":                         "Fleet capabilities",
        "Why us":                               "Why carriers choose us",
        "How it works":                         "How it works",
        "Platform":                             "The platform",
        "Results teams can measure":            "Delivery results that count",
        "One workspace, every angle":           "One platform, every delivery",
        "See it in action":                     "See fleet tracking",
        "A two-minute walkthrough":             "Fleet management in 2 minutes",
        "Built by a team that sweats the details": "Built for the road ahead",
        "Latest Articles":                      "Logistics insights",
    },
    "real_estate": {
        "Everything you need in one place":    "Every property, every listing, one place",
        "A simpler way to run the day to day": "Find your perfect home, faster",
        "Up and running in three steps":        "Find your property in three steps",
        "A look inside":                        "Browse our listings",
        "Trusted by teams everywhere":          "Trusted by buyers and sellers nationwide",
        "Capabilities":                         "What we offer",
        "Why us":                               "Why choose us",
        "How it works":                         "How to find a property",
        "Platform":                             "Our agency",
        "Results teams can measure":            "Deals closed, dreams fulfilled",
        "One workspace, every angle":           "Every property, fully covered",
        "See it in action":                     "Browse listings",
        "A two-minute walkthrough":             "Property search in 2 minutes",
        "Built by a team that sweats the details": "Built for buyers, sellers, and agents",
        "Latest Articles":                      "Property market insights",
    },
    "government": {
        "Everything you need in one place":    "All citizen services, one portal",
        "A simpler way to run the day to day": "Government services made simple",
        "Up and running in three steps":        "Access services in three steps",
        "A look inside":                        "Service overview",
        "Trusted by teams everywhere":          "Serving residents across the region",
        "Capabilities":                         "Available services",
        "Why us":                               "Why use this portal",
        "How it works":                         "How to apply",
        "Platform":                             "The citizen portal",
        "Results teams can measure":            "Citizens served, processes improved",
        "One workspace, every angle":           "One portal, every public service",
        "See it in action":                     "Explore services",
        "A two-minute walkthrough":             "The portal in 2 minutes",
        "Built by a team that sweats the details": "Built to serve every citizen, efficiently",
        "Latest Articles":                      "Public notices",
    },
    "entertainment": {
        "Everything you need in one place":    "All your entertainment, one subscription",
        "A simpler way to run the day to day": "Watch, listen, and enjoy — anywhere",
        "Up and running in three steps":        "Start watching in three steps",
        "A look inside":                        "Trending now",
        "Trusted by teams everywhere":          "Loved by millions of fans worldwide",
        "Capabilities":                         "What's included",
        "Why us":                               "Why subscribers love us",
        "How it works":                         "How to subscribe",
        "Platform":                             "The platform",
        "Results teams can measure":            "Engagement numbers that speak",
        "One workspace, every angle":           "One subscription, endless entertainment",
        "See it in action":                     "Browse content",
        "A two-minute walkthrough":             "The platform in 2 minutes",
        "Built by a team that sweats the details": "Built for the fans, by the fans",
        "Latest Articles":                      "Behind the scenes",
    },
    "ai_automation": {
        "Everything you need in one place":    "All your AI tools, one intelligent platform",
        "A simpler way to run the day to day": "Automate smarter, scale faster",
        "Up and running in three steps":        "Go live with AI in three steps",
        "A look inside":                        "AI capabilities in action",
        "Trusted by teams everywhere":          "Trusted by forward-thinking teams",
        "Capabilities":                         "AI capabilities",
        "Why us":                               "Why teams choose our AI",
        "How it works":                         "How it works",
        "Platform":                             "The AI platform",
        "Results teams can measure":            "AI-driven results, measurable",
        "One workspace, every angle":           "One platform, infinite automation",
        "See it in action":                     "See AI in action",
        "A two-minute walkthrough":             "AI automation in 2 minutes",
        "Built by a team that sweats the details": "Built for the age of intelligent automation",
        "Latest Articles":                      "AI research",
    },
    "security": {
        "Everything you need in one place":    "All your security controls, one panel",
        "A simpler way to run the day to day": "Security made simple, compliance made easy",
        "Up and running in three steps":        "Secure your organization in three steps",
        "A look inside":                        "Security dashboard",
        "Trusted by teams everywhere":          "Trusted by security teams worldwide",
        "Capabilities":                         "Security capabilities",
        "Why us":                               "Why security teams choose us",
        "How it works":                         "How to get started",
        "Platform":                             "The security platform",
        "Results teams can measure":            "Threats blocked, compliance achieved",
        "One workspace, every angle":           "One platform, total security coverage",
        "See it in action":                     "See the security dashboard",
        "A two-minute walkthrough":             "Your security in 2 minutes",
        "Built by a team that sweats the details": "Built to keep your organization safe",
        "Latest Articles":                      "Security insights",
    },
    "internal_portal": {
        "Everything you need in one place":    "Every HR tool, one employee portal",
        "A simpler way to run the day to day": "HR workflows made simple for everyone",
        "Up and running in three steps":        "Get your team onboarded in three steps",
        "A look inside":                        "Employee portal overview",
        "Trusted by teams everywhere":          "Trusted by HR teams everywhere",
        "Capabilities":                         "Portal capabilities",
        "Why us":                               "Why HR teams choose us",
        "How it works":                         "How to get started",
        "Platform":                             "The employee portal",
        "Results teams can measure":            "Employee satisfaction, improved",
        "One workspace, every angle":           "One portal, every employee need",
        "See it in action":                     "See the portal",
        "A two-minute walkthrough":             "The portal in 2 minutes",
        "Built by a team that sweats the details": "Built for the modern workforce",
        "Latest Articles":                      "Company updates",
    },
    "hybrid_app": {
        "Everything you need in one place":    "Every feature you need, one unified app",
        "A simpler way to run the day to day": "One app, multiple powerful experiences",
        "Up and running in three steps":        "Get started in three steps",
        "A look inside":                        "The platform in action",
        "Trusted by teams everywhere":          "Trusted by users worldwide",
        "Capabilities":                         "Platform capabilities",
        "Why us":                               "Why users love us",
        "How it works":                         "How to get started",
        "Platform":                             "The platform",
        "Results teams can measure":            "Results that matter",
        "One workspace, every angle":           "One platform, every experience",
        "See it in action":                     "See the platform",
        "A two-minute walkthrough":             "The platform in 2 minutes",
        "Built by a team that sweats the details": "Built to do more, together",
        "Latest Articles":                      "Platform updates",
    },
}


# Second-pass overrides: per-category replacements for section headings not
# already in _CATEGORY_COPY (testimonials, FAQ, CTA, team, pricing labels, etc.)
_SECTION_HEADINGS: dict[str, dict[str, str]] = {
    "public_website":    {"Don&apos;t just take our word for it": "What our guests say", "Questions, answered": "Restaurant FAQs", "Ready to get started?": "Ready to reserve a table?", "Final call-to-action headline": "Reserve your table tonight", "The people behind the work": "Meet our team", "Simple, honest pricing": "Dining options", "Loved by customers": "Guest reviews", "Get the occasional good email": "Join our mailing list", "See how we stack up": "Why we stand out", "How we got here": "Our culinary story", "10,000+ happy customers": "Thousands of happy diners", "From idea to impact": "From farm to table", "We started with a problem. We built the solution.": "Born from a love of great food.", "Locations near you": "Find us", "FAQ": "FAQs"},
    "ecommerce":         {"Don&apos;t just take our word for it": "What our shoppers say", "Questions, answered": "Shopping FAQs", "Ready to get started?": "Ready to start shopping?", "Final call-to-action headline": "Explore our latest collection", "The people behind the work": "The team behind the brand", "Simple, honest pricing": "Flexible options", "Loved by customers": "Customer reviews", "Get the occasional good email": "Get early access & exclusive offers", "See how we stack up": "Why shop with us", "How we got here": "Our brand story", "10,000+ happy customers": "10,000+ satisfied shoppers", "From idea to impact": "From concept to delivery", "We started with a problem. We built the solution.": "We saw a gap in the market. We filled it.", "Upcoming events": "Sale events", "FAQ": "FAQs"},
    "business_erp":      {"Don&apos;t just take our word for it": "What our customers say", "Questions, answered": "Platform FAQs", "Ready to get started?": "Ready to streamline your operations?", "Final call-to-action headline": "Start your free trial today", "The people behind the work": "Our leadership team", "Simple, honest pricing": "Transparent pricing", "Loved by customers": "Customer testimonials", "Get the occasional good email": "Get product updates", "See how we stack up": "See the difference", "How we got here": "Our journey", "10,000+ happy customers": "1,000+ businesses trust us", "From idea to impact": "From planning to execution", "Works with your favourite tools": "Works with your existing tools", "FAQ": "FAQs"},
    "booking":           {"Don&apos;t just take our word for it": "What our guests say", "Questions, answered": "Booking FAQs", "Ready to get started?": "Ready to book your stay?", "Final call-to-action headline": "Book your perfect stay today", "The people behind the work": "Our hospitality team", "Simple, honest pricing": "Room rates", "Loved by customers": "Guest reviews", "Get the occasional good email": "Get exclusive member rates", "See how we stack up": "Why we stand apart", "How we got here": "Our property story", "10,000+ happy customers": "50,000+ happy guests", "From idea to impact": "From check-in to checkout", "Locations near you": "Our properties", "FAQ": "FAQs"},
    "education":         {"Don&apos;t just take our word for it": "What our students say", "Questions, answered": "Learning FAQs", "Ready to get started?": "Ready to start learning?", "Final call-to-action headline": "Enrol in your first course today", "The people behind the work": "Meet our instructors", "Simple, honest pricing": "Course pricing", "Loved by customers": "Student reviews", "Get the occasional good email": "Get learning tips & new courses", "See how we stack up": "Why learners choose us", "How we got here": "Our mission", "10,000+ happy customers": "50,000+ graduates", "From idea to impact": "From enrolment to certification", "FAQ": "FAQs"},
    "healthcare":        {"Don&apos;t just take our word for it": "What our patients say", "Questions, answered": "Patient FAQs", "Ready to get started?": "Ready to book an appointment?", "Final call-to-action headline": "Book your appointment today", "The people behind the work": "Our medical team", "Simple, honest pricing": "Service costs", "Loved by customers": "Patient testimonials", "Get the occasional good email": "Health tips & appointment reminders", "See how we stack up": "Why patients choose us", "How we got here": "Our clinic story", "10,000+ happy customers": "10,000+ patients treated", "From idea to impact": "From diagnosis to recovery", "Locations near you": "Find a clinic", "FAQ": "FAQs"},
    "finance":           {"Don&apos;t just take our word for it": "What finance teams say", "Questions, answered": "Finance FAQs", "Ready to get started?": "Ready to take control of your finances?", "Final call-to-action headline": "Start your free financial dashboard", "The people behind the work": "Our finance experts", "Simple, honest pricing": "Simple, transparent pricing", "Loved by customers": "Customer reviews", "Get the occasional good email": "Get financial insights & tips", "See how we stack up": "How we compare", "How we got here": "Our story", "10,000+ happy customers": "10,000+ finance professionals trust us", "From idea to impact": "From tracking to optimizing", "FAQ": "FAQs"},
    "social":            {"Don&apos;t just take our word for it": "What our members say", "Questions, answered": "Community FAQs", "Ready to get started?": "Ready to join the community?", "Final call-to-action headline": "Join thousands of members today", "The people behind the work": "Our community team", "Simple, honest pricing": "Membership plans", "Loved by customers": "Member stories", "Get the occasional good email": "Stay in the loop", "See how we stack up": "Why our community is different", "How we got here": "How the community grew", "10,000+ happy customers": "50,000+ active members", "From idea to impact": "From idea to conversation", "Upcoming events": "Community events", "FAQ": "FAQs"},
    "saas":              {"Don&apos;t just take our word for it": "What our customers say", "Questions, answered": "Product FAQs", "Ready to get started?": "Ready to ship faster?", "Final call-to-action headline": "Start your 14-day free trial", "The people behind the work": "The team building it", "Simple, honest pricing": "Simple, honest pricing", "Loved by customers": "Customer love", "Get the occasional good email": "Get product updates", "See how we stack up": "How we compare", "How we got here": "How we got here", "10,000+ happy customers": "10,000+ teams trust us", "From idea to impact": "From idea to production", "Works with your favourite tools": "Works with your stack", "FAQ": "FAQs"},
    "admin_dashboard":   {"Don&apos;t just take our word for it": "What admins say", "Questions, answered": "Admin FAQs", "Ready to get started?": "Ready to take control?", "Final call-to-action headline": "Get started with your admin panel", "The people behind the work": "Our team", "Simple, honest pricing": "Plan options", "Loved by customers": "Admin reviews", "Get the occasional good email": "Get platform updates", "See how we stack up": "Why teams switch to us", "How we got here": "Our story", "10,000+ happy customers": "500+ teams trust us", "From idea to impact": "From setup to scale", "FAQ": "FAQs"},
    "content_management":{"Don&apos;t just take our word for it": "What content teams say", "Questions, answered": "Publishing FAQs", "Ready to get started?": "Ready to publish smarter?", "Final call-to-action headline": "Start publishing today", "The people behind the work": "Our content team", "Simple, honest pricing": "Publisher plans", "Loved by customers": "Editor reviews", "Get the occasional good email": "Get content strategy tips", "See how we stack up": "How we compare", "How we got here": "Our story", "10,000+ happy customers": "5,000+ publishers trust us", "FAQ": "FAQs"},
    "service_marketplace":{"Don&apos;t just take our word for it": "What clients say", "Questions, answered": "Marketplace FAQs", "Ready to get started?": "Ready to find your perfect match?", "Final call-to-action headline": "Post your first project today", "The people behind the work": "Our marketplace team", "Simple, honest pricing": "Pricing & commissions", "Loved by customers": "Client reviews", "Get the occasional good email": "Get project opportunities", "See how we stack up": "Why clients choose us", "10,000+ happy customers": "50,000+ projects completed", "FAQ": "FAQs"},
    "logistics":         {"Don&apos;t just take our word for it": "What carriers say", "Questions, answered": "Logistics FAQs", "Ready to get started?": "Ready to optimise your fleet?", "Final call-to-action headline": "Start your free fleet trial", "The people behind the work": "Our operations team", "Simple, honest pricing": "Fleet plans", "Loved by customers": "Carrier reviews", "Get the occasional good email": "Get logistics insights", "See how we stack up": "How we compare", "10,000+ happy customers": "1,000+ fleets managed", "Locations near you": "Our depots", "FAQ": "FAQs"},
    "real_estate":       {"Don&apos;t just take our word for it": "What buyers and sellers say", "Questions, answered": "Property FAQs", "Ready to get started?": "Ready to find your dream home?", "Final call-to-action headline": "Browse our latest listings", "The people behind the work": "Our agents", "Simple, honest pricing": "Agent fees", "Loved by customers": "Client testimonials", "Get the occasional good email": "Get new listings in your area", "See how we stack up": "Why choose us", "10,000+ happy customers": "1,000+ happy home owners", "Locations near you": "Our offices", "FAQ": "FAQs"},
    "government":        {"Don&apos;t just take our word for it": "What residents say", "Questions, answered": "Citizen FAQs", "Ready to get started?": "Access services online today", "Final call-to-action headline": "Access your citizen services", "The people behind the work": "Our team", "Simple, honest pricing": "Service fees", "Loved by customers": "Resident feedback", "Get the occasional good email": "Stay informed", "See how we stack up": "Our commitments", "10,000+ happy customers": "100,000+ residents served", "Locations near you": "Service centres near you", "FAQ": "FAQs"},
    "entertainment":     {"Don&apos;t just take our word for it": "What subscribers say", "Questions, answered": "Subscription FAQs", "Ready to get started?": "Ready to start streaming?", "Final call-to-action headline": "Start your free trial today", "The people behind the work": "Our creative team", "Simple, honest pricing": "Subscription plans", "Loved by customers": "Fan reviews", "Get the occasional good email": "Get new release alerts", "See how we stack up": "Why we're different", "10,000+ happy customers": "1M+ happy subscribers", "Upcoming events": "Live events & premieres", "FAQ": "FAQs"},
    "ai_automation":     {"Don&apos;t just take our word for it": "What AI teams say", "Questions, answered": "AI platform FAQs", "Ready to get started?": "Ready to automate at scale?", "Final call-to-action headline": "Start building with AI today", "The people behind the work": "Our AI research team", "Simple, honest pricing": "AI compute pricing", "Loved by customers": "Customer success stories", "Get the occasional good email": "Get AI research updates", "See how we stack up": "How our AI compares", "10,000+ happy customers": "500+ AI-powered teams", "Works with your favourite tools": "Works with your ML stack", "FAQ": "FAQs"},
    "security":          {"Don&apos;t just take our word for it": "What security teams say", "Questions, answered": "Security FAQs", "Ready to get started?": "Ready to secure your organisation?", "Final call-to-action headline": "Start your security audit today", "The people behind the work": "Our security experts", "Simple, honest pricing": "Security plans", "Loved by customers": "Security team reviews", "Get the occasional good email": "Get security alerts & updates", "See how we stack up": "How we compare", "10,000+ happy customers": "500+ organisations secured", "FAQ": "FAQs"},
    "internal_portal":   {"Don&apos;t just take our word for it": "What employees say", "Questions, answered": "Portal FAQs", "Ready to get started?": "Ready to modernise your HR portal?", "Final call-to-action headline": "Get your team onboarded today", "The people behind the work": "Our HR team", "Simple, honest pricing": "Portal plans", "Loved by customers": "Employee reviews", "Get the occasional good email": "Get HR best practices", "See how we stack up": "Why teams choose us", "10,000+ happy customers": "200+ companies using us", "FAQ": "FAQs"},
    "hybrid_app":        {"Don&apos;t just take our word for it": "What users say", "Questions, answered": "App FAQs", "Ready to get started?": "Ready to get started?", "Final call-to-action headline": "Get started for free", "The people behind the work": "Our team", "Simple, honest pricing": "App plans", "Loved by customers": "User reviews", "Get the occasional good email": "Get app updates", "10,000+ happy customers": "10,000+ active users", "FAQ": "FAQs"},
}


def _adapt_content(src: str, category_id: str) -> str:
    """Replace generic placeholder phrases with category-specific copy (two passes)."""
    overrides = _CATEGORY_COPY.get(category_id)
    if overrides:
        for generic, specific in overrides.items():
            src = src.replace(generic, specific)
    section_overrides = _SECTION_HEADINGS.get(category_id)
    if section_overrides:
        for generic, specific in section_overrides.items():
            src = src.replace(generic, specific)
    return src


def _pick_hero(hero_file: str | None, hero_variant: str | None, rng: random.Random) -> tuple[str, str]:
    """Pick the best hero JSX for this plane. Prefers explicit hero_file,
    then maps hero_variant from the design plane, then falls back to random."""
    if hero_file and hero_file in _HERO_BY_FILE:
        return _HERO_BY_FILE[hero_file]
    if hero_variant and hero_variant in _PLANE_HERO_FILE:
        fname = _PLANE_HERO_FILE[hero_variant]
        return _HERO_BY_FILE.get(fname) or rng.choice(HEROES)
    return rng.choice(HEROES)


def _read(fname: str) -> str:
    with open(os.path.join(_DIR, fname), encoding="utf-8") as f:
        return f.read()


def compose_landing(
    rng: random.Random | None = None,
    hero_file: str | None = None,
    prompt_text: str = "",
    design_plane: dict | None = None,
    category_id: str = "",
) -> tuple[str, str, set[str]]:
    """Return (description, source, used_families) for a freshly remixed landing page.

    If `design_plane` is supplied (from app_taxonomy + design_planes), the plane's
    curated section sequence is used — delivering 12-16 world-class sections that are
    appropriate for the specific app category. Without a plane, falls back to the
    original 4-6 section random selection.

    `category_id` enables post-render content substitution so section headings
    match the app domain (e.g. "Everything you need" → "Everything on our menu").

    The returned `used_families` set lets callers exclude those families from
    sub-pages so no section type repeats across pages of the same app.

    A page = one HERO + N MIDDLE sections from section_catalog + CtaFooter.
    """
    from app import section_catalog
    rng = rng or random.Random()

    # Per-prompt sequence rotation: same domain, different prompt → different
    # starting position in the curated plane, so two apps of the same type look
    # distinct rather than bit-for-bit identical.
    if design_plane and prompt_text:
        seq = design_plane.get("section_sequence") or []
        if seq:
            offset = abs(hash(prompt_text)) % len(seq)
            design_plane = dict(design_plane)   # don't mutate the shared plane
            design_plane["section_sequence"] = seq[offset:] + seq[:offset]

    hero_variant = (design_plane or {}).get("hero_variant") if design_plane else None
    hero = _pick_hero(hero_file, hero_variant, rng)

    if design_plane:
        # World-class path: use the design plane's curated section sequence
        from app import design_planes as _dp
        min_sections = design_plane.get("min_sections", 12)
        count = max(min_sections, rng.randint(min_sections, min_sections + 3))
        plane_entries = _dp.pick_sections(design_plane, count, rng, prompt_text)
        middles = []
        for fam, tone in plane_entries:
            entry = next(
                (e for e in section_catalog.CATALOG if e["family"] == fam and e["tone"] == tone),
                next((e for e in section_catalog.CATALOG if e["family"] == fam), None),
            )
            if entry:
                middles.append(entry)
    else:
        # Legacy path: 4-6 tag-matched sections
        count = rng.randint(4, 6)
        middles = section_catalog.pick_middles(rng, count, prompt_text)

    parts = [_HEADER, _read(hero[1]).rstrip() + "\n\n"]
    mid_names = []
    for i, entry in enumerate(middles):
        nm = f"Section{i + 1}"
        parts.append(section_catalog.render(entry, nm).rstrip() + "\n\n")
        mid_names.append(nm)
    parts.append(_read(CLOSER[1]).rstrip() + "\n\n")

    names = [hero[0]] + mid_names + [CLOSER[0]]
    render_str = "\n      ".join(f"<{nm} />" for nm in names)
    parts.append(
        "export default function Home() {\n"
        "  return (\n"
        "    <div className=\"w-full\">\n"
        f"      {render_str}\n"
        "    </div>\n"
        "  );\n"
        "}\n"
    )

    src = "".join(parts)

    # Apply category-specific content overrides to make headings domain-relevant
    if category_id:
        src = _adapt_content(src, category_id)

    used_families: set[str] = {e["family"] for e in middles}
    desc = hero[0] + " + " + "/".join(e["family"] for e in middles)
    return desc, src, used_families
