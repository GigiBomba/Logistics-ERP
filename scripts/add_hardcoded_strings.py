#!/usr/bin/env python3
"""Add all hardcoded UI strings from the codebase to en.json as i18n keys."""
from __future__ import annotations


import json
import os

EN_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "translations", "en.json")

with open(EN_PATH, encoding="utf-8-sig") as f:
    en = json.load(f)

def ensure(d, key):
    parts = key.split(".")
    for p in parts:
        d = d.setdefault(p, {})
    return d

def set_val(d, key, value):
    parts = key.split(".")
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value

# ── Python UI files already importing t() ──────────────────────────

# team_view.py
set_val(en, "team.validation_title", "Validation")
set_val(en, "team.email_required", "Email is required.")
set_val(en, "team.password_required", "Password is required.")
set_val(en, "team.deactivate_user", "Deactivate User")
set_val(en, "team.deactivate_confirm", "Are you sure you want to deactivate {email}?")
set_val(en, "team.deactivate_button", "Deactivate")
set_val(en, "team.error_title", "Error")
set_val(en, "team.no_api_client", "No API client or database available.")
set_val(en, "team.success_title", "Success")
set_val(en, "team.user_added", "User added successfully.")
set_val(en, "team.add_user_failed", "Failed to add user: {error}")
set_val(en, "team.deactivate_failed", "Failed to deactivate user: {error}")

# login_dialog.py
set_val(en, "login.email_placeholder", "admin@example.com")
set_val(en, "login.password_placeholder", "············")

# main_window.py (PlaceholderView)
set_val(en, "main.module_not_migrated", "{module}\n(Module not yet migrated)")

# document_center.py
set_val(en, "docs.entity_documents_title", "Documents — {title}")
set_val(en, "docs.entity_documents_default", "Entity Documents")

# maintenance_control_panel.py
set_val(en, "maint.filter_placeholder", "Filter...")

# maintenance_view.py
set_val(en, "maint.unit_km", " km")
set_val(en, "maint.unit_months", " months")

# settings_fields.py
set_val(en, "settings.unit_seconds", " seconds")

# trip_card.py
set_val(en, "trip.speed_display", "{speed:.0f} km/h")

# notification_center.py (doesn't import t yet)
set_val(en, "notification.test_message", "This is a test notification from the Operations Engine.")

# ── React TSX strings (marketing pages) ────────────────────────────

# home.tsx - Features section
set_val(en, "home.feature_route_planning_title", "Intelligent Route Planning")
set_val(en, "home.feature_route_planning_desc", "Optimize routes in seconds with advanced algorithms that consider distance, traffic, fuel costs, and delivery windows.")
set_val(en, "home.feature_tracking_title", "Real-Time Fleet Tracking")
set_val(en, "home.feature_tracking_desc", "Monitor every vehicle in your fleet with live GPS tracking, geofencing, and instant alerts.")
set_val(en, "home.feature_dispatch_title", "Smart Dispatch")
set_val(en, "home.feature_dispatch_desc", "Assign jobs automatically based on driver availability, truck status, and proximity.")
set_val(en, "home.feature_ocr_title", "OCR Document Processing")
set_val(en, "home.feature_ocr_desc", "Scan and digitize invoices, CMRs, and receipts with AI-powered OCR.")
set_val(en, "home.feature_analytics_title", "Advanced Analytics")
set_val(en, "home.feature_analytics_desc", "Gain actionable insights with dashboards, KPIs, and customizable reports.")
set_val(en, "home.feature_driver_title", "Driver Management")
set_val(en, "home.feature_driver_desc", "Manage driver profiles, licenses, medical certificates, and performance.")

# home.tsx - Benefits section
set_val(en, "home.benefit_cost_title", "Reduce Operational Costs")
set_val(en, "home.benefit_cost_desc", "Cut fuel consumption by up to 20%% with optimized routing, reduce idle time, and minimize maintenance costs.")
set_val(en, "home.benefit_speed_title", "Increase Delivery Speed")
set_val(en, "home.benefit_speed_desc", "Complete more deliveries per day with intelligent route optimization and real-time traffic avoidance.")
set_val(en, "home.benefit_paperwork_title", "Eliminate Paperwork")
set_val(en, "home.benefit_paperwork_desc", "Digitize all documents with OCR, automate invoicing, and go fully paperless.")
set_val(en, "home.benefit_scale_title", "Scale With Confidence")
set_val(en, "home.benefit_scale_desc", "From 5 vehicles to 500, our platform grows with your business without missing a beat.")

# home.tsx - Testimonials
set_val(en, "home.testimonial_1", "Operion transformed our operations. We cut route planning time by 80%% and fuel costs by 15%% in the first quarter.")
set_val(en, "home.testimonial_1_author", "Mihai Popescu")
set_val(en, "home.testimonial_1_role", "Fleet Manager, TransLogistic")
set_val(en, "home.testimonial_2", "Having real-time visibility into our fleet has been a game-changer. Our customers love the accurate ETAs.")
set_val(en, "home.testimonial_2_author", "Sarah Müller")
set_val(en, "home.testimonial_2_role", "Operations Director, EuroFreight")
set_val(en, "home.testimonial_3", "We scaled from 10 to 50 vehicles without adding a single dispatcher. Operion's automation is incredible.")
set_val(en, "home.testimonial_3_author", "John Smith")
set_val(en, "home.testimonial_3_role", "CEO, Smith Logistics")

# home.tsx - Hero/CTA
set_val(en, "home.page_title", "Operion ERP — Enterprise Logistics, Simplified")
set_val(en, "home.hero_headline", "Enterprise Logistics, Simplified")
set_val(en, "home.hero_description", "Operion ERP gives your fleet the power to plan smarter, dispatch faster, and grow bigger.")
set_val(en, "home.cta_start_trial", "Start Free Trial")
set_val(en, "home.cta_see_how", "See How It Works")
set_val(en, "home.section_features", "Everything you need to run your fleet")
set_val(en, "home.section_features_desc", "Powerful tools that work together to streamline every aspect of your logistics operations.")
set_val(en, "home.section_benefits", "Built for real logistics results")
set_val(en, "home.section_benefits_desc", "Every feature is designed to solve a real problem our customers faced.")
set_val(en, "home.section_testimonials", "Trusted by logistics leaders")
set_val(en, "home.section_testimonials_desc", "See how Operion is helping companies transform their logistics operations.")
set_val(en, "home.section_mission", "Our Mission")
set_val(en, "home.section_mission_desc", "Our mission is to make enterprise logistics software accessible, powerful, and easy to use.")
set_val(en, "home.section_cta_title", "Ready to Transform Your Logistics?")
set_val(en, "home.section_cta_desc", "Join hundreds of companies that trust Operion to run their fleet operations.")
set_val(en, "home.cta_talk_sales", "Talk to Sales")

# features.tsx
set_val(en, "features.page_title", "Features - Operion ERP")
set_val(en, "features.page_header", "Powerful Features for Modern Logistics")
set_val(en, "features.page_header_desc", "Everything you need to run your fleet efficiently, from route planning to analytics.")

# features.tsx - Route Planning
set_val(en, "features.category_route_planning", "Route Planning & Optimization")
set_val(en, "features.route_planning_title", "Intelligent Route Planning")
set_val(en, "features.route_planning_desc", "Advanced algorithms optimize for time, distance, fuel, and toll costs across Europe.")
set_val(en, "features.multi_stop_title", "Multi-Stop Optimization")
set_val(en, "features.multi_stop_desc", "Plan complex multi-stop routes with up to 50 waypoints and automated sequencing.")
set_val(en, "features.traffic_title", "Real-Time Traffic Integration")
set_val(en, "features.traffic_desc", "Routes adjust dynamically based on live traffic conditions and road closures.")

# features.tsx - Fleet
set_val(en, "features.category_fleet", "Fleet Management")
set_val(en, "features.gps_tracking_title", "Real-Time GPS Tracking")
set_val(en, "features.gps_tracking_desc", "Monitor every vehicle's location, speed, and status on an interactive map.")
set_val(en, "features.maintenance_title", "Vehicle Maintenance Tracking")
set_val(en, "features.maintenance_desc", "Schedule and track maintenance with automated alerts for inspections, insurance, and services.")
set_val(en, "features.geofencing_title", "Geofencing & Alerts")
set_val(en, "features.geofencing_desc", "Set geographic boundaries and receive instant notifications when vehicles enter or leave zones.")

# features.tsx - Dispatch
set_val(en, "features.category_dispatch", "Dispatch & Operations")
set_val(en, "features.auto_assign_title", "Automated Job Assignment")
set_val(en, "features.auto_assign_desc", "Match jobs to the best available drivers and trucks based on location, skills, and compliance.")
set_val(en, "features.pod_title", "Digital Proof of Delivery")
set_val(en, "features.pod_desc", "Capture signatures, photos, and timestamps at delivery for complete proof of delivery.")
set_val(en, "features.status_updates_title", "Real-Time Status Updates")
set_val(en, "features.status_updates_desc", "Track every job from assignment to completion with live status updates.")

# features.tsx - Documents
set_val(en, "features.category_documents", "Document Management")
set_val(en, "features.ocr_ai_title", "AI-Powered OCR")
set_val(en, "features.ocr_ai_desc", "Scan and digitize invoices, CMRs, receipts, and contracts with AI-powered OCR.")
set_val(en, "features.digital_archive_title", "Digital Archive")
set_val(en, "features.digital_archive_desc", "Store and search all documents with version history, tags, and full-text search.")
set_val(en, "features.auto_invoicing_title", "Automated Invoicing")
set_val(en, "features.auto_invoicing_desc", "Generate invoices from delivery data automatically and email them to clients.")

# features.tsx - Analytics
set_val(en, "features.category_analytics", "Analytics & Reporting")
set_val(en, "features.dashboards_title", "Custom Dashboards")
set_val(en, "features.dashboards_desc", "Build personalized views with KPIs, charts, and real-time data.")
set_val(en, "features.kpi_title", "KPI Tracking")
set_val(en, "features.kpi_desc", "Monitor key performance indicators including profit per mile, fuel efficiency, and driver performance.")
set_val(en, "features.export_title", "Export & Integration")
set_val(en, "features.export_desc", "Export reports in multiple formats and integrate with your existing ERP and accounting software.")

# features.tsx - Drivers
set_val(en, "features.category_drivers", "Driver Management")
set_val(en, "features.driver_profiles_title", "Driver Profiles")
set_val(en, "features.driver_profiles_desc", "Complete driver database with licenses, medical certificates, contracts, and documents.")
set_val(en, "features.driver_performance_title", "Performance Tracking")
set_val(en, "features.driver_performance_desc", "Monitor driver efficiency, safety scores, tachograph compliance, and driving hours.")
set_val(en, "features.schedule_title", "Schedule Management")
set_val(en, "features.schedule_desc", "Plan driver shifts, manage availability, and track working hours.")

# about.tsx
set_val(en, "about.page_title", "About - Operion ERP")
set_val(en, "about.page_header", "About Operion")
set_val(en, "about.page_header_desc", "We're building the future of enterprise logistics software.")
set_val(en, "about.story_title", "Our Story")
set_val(en, "about.story_p1", "Operion was founded in 2024 with a clear mission: make enterprise-grade logistics software accessible to fleets of all sizes.")
set_val(en, "about.story_p2", "Our team combines decades of experience in logistics, software engineering, and AI to build tools that solve real-world problems.")
set_val(en, "about.story_p3", "Today, Operion powers fleets across Europe, helping them plan smarter, dispatch faster, and grow bigger.")
set_val(en, "about.values_title", "Our Values")
set_val(en, "about.values_desc", "The principles that guide every decision we make.")
set_val(en, "about.value_customer_title", "Customer First")
set_val(en, "about.value_customer_desc", "Every feature we build starts with real customer needs and feedback.")
set_val(en, "about.value_reliability_title", "Reliability")
set_val(en, "about.value_reliability_desc", "Your operations depend on our software. We take that responsibility seriously.")
set_val(en, "about.value_innovation_title", "Innovation")
set_val(en, "about.value_innovation_desc", "We invest heavily in R&D to bring cutting-edge AI and optimization to logistics.")
set_val(en, "about.value_transparency_title", "Transparency")
set_val(en, "about.value_transparency_desc", "Clear pricing, honest communication, and no hidden fees.")
set_val(en, "about.value_security_title", "Security")
set_val(en, "about.value_security_desc", "Enterprise-grade encryption, GDPR compliance, and regular security audits.")
set_val(en, "about.value_partnership_title", "Partnership")
set_val(en, "about.value_partnership_desc", "We don't just sell software. We partner with our customers for their success.")
set_val(en, "about.team_title", "Our Team")
set_val(en, "about.team_desc", "Our team combines decades of experience in logistics, software engineering, and AI.")

# auth pages
set_val(en, "auth.login_title", "Sign In — Operion ERP")
set_val(en, "auth.login_back", "Back to home")
set_val(en, "auth.login_brand", "Operion")
set_val(en, "auth.login_welcome", "Welcome back")
set_val(en, "auth.login_subtitle", "Sign in to your Operion account")
set_val(en, "auth.email_label", "Email")
set_val(en, "auth.email_placeholder", "you@company.com")
set_val(en, "auth.password_label", "Password")
set_val(en, "auth.forgot_password", "Forgot password?")
set_val(en, "auth.password_placeholder", "Enter your password")
set_val(en, "auth.hide_password", "Hide password")
set_val(en, "auth.show_password", "Show password")
set_val(en, "auth.signing_in", "Signing in\u2026")
set_val(en, "auth.sign_in", "Sign in")
set_val(en, "auth.no_account", "Don't have an account?")
set_val(en, "auth.sign_up_link", "Sign up")
set_val(en, "auth.signed_in_success", "Signed in successfully!")
set_val(en, "auth.sign_in_failed", "Failed to sign in")

# validation messages
set_val(en, "auth.validation_invalid_email", "Please enter a valid email")
set_val(en, "auth.validation_password_required", "Password is required")
set_val(en, "auth.validation_password_max", "Password must be at most 72 characters")

set_val(en, "auth.register_title", "Create Account — Operion ERP")
set_val(en, "auth.register_back", "Back to home")
set_val(en, "auth.register_brand", "Operion")
set_val(en, "auth.register_welcome", "Create your account")
set_val(en, "auth.register_subtitle", "Start your 14-day free trial")
set_val(en, "auth.name_label", "Full Name")
set_val(en, "auth.name_placeholder", "John Doe")
set_val(en, "auth.company_label", "Company Name (optional)")
set_val(en, "auth.company_placeholder", "Acme Inc.")
set_val(en, "auth.password_min_hint", "At least 8 characters")
set_val(en, "auth.confirm_password_label", "Confirm Password")
set_val(en, "auth.confirm_password_placeholder", "Repeat your password")
set_val(en, "auth.creating_account", "Creating account\u2026")
set_val(en, "auth.create_account", "Create account")
set_val(en, "auth.has_account", "Already have an account?")
set_val(en, "auth.sign_in_link", "Sign in")
set_val(en, "auth.account_created", "Account created successfully!")
set_val(en, "auth.create_account_failed", "Failed to create account")
set_val(en, "auth.validation_name_min", "Name must be at least 2 characters")
set_val(en, "auth.validation_password_min", "Password must be at least 8 characters")
set_val(en, "auth.validation_passwords_match", "Passwords don't match")

# Write
with open(EN_PATH, "w", encoding="utf-8", newline="\n") as f:
    json.dump(en, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("All hardcoded strings added to en.json successfully.")
