"""
Seed Data Script: Generates 5,000+ realistic customers & comprehensive e-commerce
relational data across all 10 tables in the 'public' schema.

Usage:
  py seed_data.py [--users 5000] [--clean]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
from core.db import DB

# Seed for reproducible realistic generation
random.seed(42)

# --- Realistic Master Dictionaries ---
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Aarav", "Priya", "Rohan", "Ananya", "Rahul", "Sneha", "Vikram", "Neha",
    "Kavya", "Aditya", "Siddharth", "Pooja", "Arjun", "Deepika", "Karthik", "Rhea"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Sharma", "Patel", "Verma", "Reddy", "Gupta", "Nair", "Kapoor", "Rao", "Chopra"
]

DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "proton.me", "enterprise.com"]

CITIES_ADDRESSES = [
    ("742 Evergreen Terrace", "Springfield", "OR", "97477"),
    ("123 Main Street", "Austin", "TX", "78701"),
    ("456 Market St, Apt 4B", "San Francisco", "CA", "94103"),
    ("789 Broadway Ave", "New York", "NY", "10003"),
    ("101 Ocean Drive", "Miami", "FL", "33139"),
    ("202 Michigan Ave", "Chicago", "IL", "60601"),
    ("303 Pine St", "Seattle", "WA", "98101"),
    ("404 Peachtree St", "Atlanta", "GA", "30308"),
    ("505 MG Road, Indiranagar", "Bangalore", "KA", "560038"),
    ("606 Bandra West, Hill Road", "Mumbai", "MH", "400050"),
    ("707 Connaught Place", "New Delhi", "DL", "110001"),
    ("808 Jubilee Hills, Rd 36", "Hyderabad", "TS", "500033"),
]

CATEGORY_SPECS = [
    ("Electronics & Gadgets", "electronics-gadgets", "Smartphones, laptops, smart home devices and audio gear.", "https://assets.store.com/icons/electronics.svg", 1),
    ("Laptops & Computers", "laptops-computers", "Ultrabooks, gaming rigs, workstations and PC accessories.", "https://assets.store.com/icons/laptop.svg", 2),
    ("Smartphones & Tablets", "smartphones-tablets", "Flagship 5G phones, iOS/Android tablets and styluses.", "https://assets.store.com/icons/phone.svg", 3),
    ("Audio & Headphones", "audio-headphones", "Noise-cancelling headphones, wireless earbuds and studio monitors.", "https://assets.store.com/icons/audio.svg", 4),
    ("Smart Home & IoT", "smart-home-iot", "Smart lights, plugs, thermostats and security cameras.", "https://assets.store.com/icons/smarthome.svg", 5),
    ("Wearables & Fitness", "wearables-fitness", "Smartwatches, fitness bands and heart rate monitors.", "https://assets.store.com/icons/watch.svg", 6),
    ("Men's Apparel", "mens-apparel", "Shirts, denim, jackets, activewear and tailored suits.", "https://assets.store.com/icons/mens-fashion.svg", 7),
    ("Women's Fashion", "womens-fashion", "Dresses, tops, skirts, outerwear and designer collections.", "https://assets.store.com/icons/womens-fashion.svg", 8),
    ("Footwear & Sneakers", "footwear-sneakers", "Running shoes, casual sneakers, boots and formal loafers.", "https://assets.store.com/icons/shoes.svg", 9),
    ("Home & Living", "home-living", "Modern furniture, bedding, rugs and home decor accents.", "https://assets.store.com/icons/home.svg", 10),
    ("Kitchen & Dining", "kitchen-dining", "Cookware, espresso machines, blenders and dinnerware.", "https://assets.store.com/icons/kitchen.svg", 11),
    ("Beauty & Skincare", "beauty-skincare", "Serums, moisturizers, organic cosmetics and fragrances.", "https://assets.store.com/icons/beauty.svg", 12),
    ("Health & Wellness", "health-wellness", "Vitamins, protein supplements, yoga gear and massage tools.", "https://assets.store.com/icons/health.svg", 13),
    ("Sports & Outdoors", "sports-outdoors", "Trekking gear, bicycles, camping tents and gym equipment.", "https://assets.store.com/icons/sports.svg", 14),
    ("Books & Stationery", "books-stationery", "Bestsellers, technical books, notebooks and fountain pens.", "https://assets.store.com/icons/books.svg", 15),
    ("Toys & Games", "toys-games", "Board games, educational kits, action figures and puzzles.", "https://assets.store.com/icons/toys.svg", 16),
    ("Office Supplies", "office-supplies", "Ergonomic chairs, standing desks, monitors and organizers.", "https://assets.store.com/icons/office.svg", 17),
    ("Automotive Accessories", "automotive-accessories", "Car dashcams, chargers, emergency kits and detailing tools.", "https://assets.store.com/icons/auto.svg", 18),
    ("Pet Supplies", "pet-supplies", "Premium food, toys, collars and grooming essentials for pets.", "https://assets.store.com/icons/pets.svg", 19),
    ("Gourmet & Groceries", "gourmet-groceries", "Artisanal coffee, chocolates, olive oils and specialty snacks.", "https://assets.store.com/icons/gourmet.svg", 20),
]

PRODUCT_TEMPLATES = [
    ("Pro Ultra Wireless Noise-Cancelling Headphones", 299.99, 15, "Premium over-ear ANC headphones with 40-hour battery life and Hi-Res LDAC support.", "High-fidelity wireless sound."),
    ("QuantumBook Pro 16-inch M3", 2499.00, 10, "High-performance workstation laptop featuring 36GB unified memory and 1TB NVMe SSD.", "Ultimate workstation power."),
    ("Apex 5G Flagship Smartphone 256GB", 899.99, 5, "OLED 120Hz display with triple 50MP camera array and Snapdragon processor.", "Flagship 5G performance."),
    ("UltraFit Smart Watch Series 8", 199.99, 20, "Always-on AMOLED display with ECG, SPO2 tracking, GPS and waterproof chassis.", "Advanced health companion."),
    ("ErgoGlide Standing Desk 60x30", 449.00, 0, "Dual-motor electric standing desk with 4 memory presets and solid bamboo desktop.", "Ergonomic workspace foundation."),
    ("AeroMesh Ergonomic Task Chair", 329.50, 12, "Adjustable 4D armrests, lumbar support and breathable high-tensile mesh back.", "All-day comfort seating."),
    ("SmartGlow RGB Ambient Light Bar", 69.99, 25, "App-controlled sync-to-sound dynamic RGB light bar for monitor and TV setups.", "Immersive gaming illumination."),
    ("Velocita Mechanical Keyboard RGB", 129.99, 10, "Hot-swappable mechanical switches, PBT double-shot keycaps and aluminum frame.", "Tactile typing precision."),
    ("PureMist Ultrasonic Humidifier 4L", 49.99, 15, "Whisper-quiet cool mist humidifier with essential oil tray and auto shut-off.", "Clean home atmosphere."),
    ("Precision Espresso Maker 15-Bar", 189.99, 8, "Stainless steel Italian pump espresso machine with steam wand for microfoam.", "Cafe quality espresso at home."),
    ("Titanium Multi-Ply 10-Piece Cookware Set", 279.00, 15, "Non-toxic non-stick induction-compatible cookware with stay-cool riveted handles.", "Master-chef grade durability."),
    ("HydroShield Waterproof Hiking Backpack 45L", 119.00, 20, "Ripstop nylon waterproof backpack with ergonomic hip belt and rain cover.", "Rugged outdoor expedition pack."),
    ("CarbonStride Carbon-Plated Running Shoes", 159.99, 10, "Responsive supercritical foam midsole paired with full-length carbon fiber plate.", "Effortless marathon speed."),
    ("Organic Glow Vitamin C Facial Serum 50ml", 38.00, 0, "Dermatologist-tested 20% Vitamin C serum with Hyaluronic Acid and Ferulic acid.", "Radiant skin brightness."),
    ("Luxe Velvet Bedding Duvet Set King", 149.00, 18, "Silky soft breathable washed micro-velvet duvet cover with matching pillow shams.", "Hotel luxury bedroom comfort."),
    ("SwiftCharge 65W GaN Fast Charger 3-Port", 45.99, 20, "Compact Gallium Nitride wall charger with 2x USB-C PD and 1x USB-A ports.", "Pocketable multi-device power."),
    ("PulseMax Deep Tissue Massage Gun", 89.99, 30, "Brushless high-torque motor with 6 interchangeable massage heads and travel case.", "Instant muscle recovery."),
    ("AeroStream Smart Air Purifier HEPA H13", 159.99, 12, "True HEPA filtration capturing 99.97% of airborne particles with PM2.5 display.", "Pure allergen-free air."),
    ("Heritage Leather Bi-Fold Wallet RFID", 49.50, 0, "Full-grain top leather handmade wallet with integrated RFID-blocking technology.", "Classic everyday accessory."),
    ("ZeroGravity Lightweight Camping Hammock", 34.99, 15, "Heavy-duty 210T parachute nylon portable hammock with tree-friendly straps.", "Relax anywhere outdoors.")
]

ORDER_STATUSES = ["COMPLETED", "COMPLETED", "COMPLETED", "CONFIRMED", "PENDING", "INQUIRY_SENT", "CANCELLED"]
USER_ROLES = ["USER", "USER", "USER", "USER", "USER", "USER", "USER", "ADMIN"]
PRODUCT_STATUSES = ["PUBLISHED", "PUBLISHED", "PUBLISHED", "PUBLISHED", "OUT_OF_STOCK", "DRAFT"]
AUDIT_ACTIONS = ["CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT", "ACCESS", "EXPORT"]
NOTIFICATION_TYPES = ["ORDER_STATUS", "STOCK_ALERT", "DISCOUNT_ALERT", "ADMIN_MESSAGE"]

REVIEW_SNIPPETS = [
    (5, "Absolutely exceeded my expectations! Build quality is top-notch and delivery was super fast."),
    (5, "Best purchase I've made this year. High performance, premium materials, and easy setup."),
    (4, "Great product overall. Minor learning curve with the settings, but works flawlessly now."),
    (4, "Very solid and well-designed. Exactly as described in the listing. Recommended!"),
    (5, "Super happy with the customer service and the product finish. 10/10 would buy again."),
    (3, "Decent quality for the price, but shipping took slightly longer than expected."),
    (4, "Good value for money. Looks great and performs well under daily use."),
    (5, "Outstanding! Packaged securely and works even better than advertised.")
]


def random_date(start_days_ago: int = 365, end_days_ago: int = 0) -> datetime:
    delta = random.randint(end_days_ago, start_days_ago)
    secs = random.randint(0, 86400)
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=delta, seconds=secs)


def execute_batch_insert(db: DB, table: str, columns: list[str], rows: list[tuple], chunk_size: int = 1000):
    """Inserts rows in fast chunked batches using DBAPI cursor."""
    if not rows:
        return
    col_str = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    query = f'INSERT INTO "public"."{table}" ({col_str}) VALUES ({placeholders})'

    with db._engine.connect() as conn:
        raw_conn = conn.connection
        cur = raw_conn.cursor()
        try:
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i:i + chunk_size]
                cur.executemany(query, chunk)
            raw_conn.commit()
        except Exception:
            raw_conn.rollback()
            raise
        finally:
            cur.close()


def main():
    parser = argparse.ArgumentParser(description="Seed 5000+ realistic customers & e-commerce data into database.")
    parser.add_argument("--users", type=int, default=5000, help="Number of customers to generate (default: 5000)")
    parser.add_argument("--clean", action="store_true", help="Truncate existing tables before inserting")
    args = parser.parse_args()

    db_url = os.getenv("DB_URL")
    if not db_url:
        print("ERROR: DB_URL not found in .env")
        sys.exit(1)

    db = DB(db_url)
    num_users = args.users
    print(f"[*] Starting Real-Time Data Seeding for {num_users:,} Customers...")
    t0 = time.time()

    if args.clean:
        print("[*] Truncating existing tables...")
        tables_in_order = [
            "audit_logs", "notifications", "reviews", "wishlist", "cart",
            "order_items", "orders", "products", "categories", "users"
        ]
        with db._engine.connect() as conn:
            raw_conn = conn.connection
            cur = raw_conn.cursor()
            try:
                for t in tables_in_order:
                    cur.execute(f'TRUNCATE TABLE "public"."{t}" CASCADE;')
                raw_conn.commit()
                print("[+] Tables truncated successfully.")
            except Exception as e:
                raw_conn.rollback()
                print(f"[!] Truncate warning: {e}")
            finally:
                cur.close()

    # -------------------------------------------------------------------------
    # 1. Insert Categories (20 Root Categories)
    # -------------------------------------------------------------------------
    print("\n[1/9] Generating 20 Categories...")
    category_ids = []
    category_rows = []
    for name, slug, desc, icon, order in CATEGORY_SPECS:
        cid = str(uuid.uuid4())
        category_ids.append(cid)
        created_at = random_date(400, 300)
        category_rows.append((cid, created_at, desc, order, icon, name, slug))

    execute_batch_insert(
        db, "categories",
        ["id", "created_at", "description", "display_order", "icon_url", "name", "slug"],
        category_rows
    )
    print(f"  + Inserted {len(category_rows)} categories.")

    # -------------------------------------------------------------------------
    # 2. Insert Users (5,000 Customers + 5 Admins)
    # -------------------------------------------------------------------------
    print(f"\n[2/9] Generating {num_users + 5:,} Users ({num_users:,} Customers + 5 Admins)...")
    admin_ids = []
    customer_ids = []
    user_rows = []
    used_emails = set()

    # Admins
    admin_names = [("System", "Administrator"), ("Data", "Governor"), ("Operations", "Lead"), ("Security", "Officer"), ("Catalog", "Manager")]
    for fn, ln in admin_names:
        uid = str(uuid.uuid4())
        admin_ids.append(uid)
        email = f"{fn.lower()}.{ln.lower()}@enterprisestore.internal"
        used_emails.add(email)
        created_at = random_date(500, 400)
        user_rows.append((
            uid, f"Senior {ln} for the enterprise commerce platform.", "Enterprise Commerce Global Inc.",
            created_at, email, f"{fn} {ln}", True, random_date(5, 0),
            "$2b$12$KIXpZ65eJ3e3D4v1Qn8vceM3n9O8rK7l2V0bW4v9R2lP8qM7yN0xO", "+1-800-555-0100",
            f"https://assets.store.com/avatars/{fn.lower()}.png", "ADMIN", created_at + timedelta(days=random.randint(1, 30))
        ))

    # Customers
    for i in range(num_users):
        uid = str(uuid.uuid4())
        customer_ids.append(uid)
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        domain = random.choice(DOMAINS)
        
        # Ensure unique email
        email = f"{fn.lower()}.{ln.lower()}{i+1}@{domain}"
        while email in used_emails:
            email = f"{fn.lower()}.{ln.lower()}{uuid.uuid4().hex[:4]}@{domain}"
        used_emails.add(email)

        created_at = random_date(350, 5)
        last_login = created_at + timedelta(days=random.randint(0, 30)) if random.random() > 0.1 else None
        phone = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        role = random.choice(USER_ROLES)
        company = f"{ln} Ventures LLC" if random.random() < 0.25 else None
        bio = f"Verified customer & tech enthusiast from {random.choice(CITIES_ADDRESSES)[1]}." if random.random() < 0.4 else None

        user_rows.append((
            uid, bio, company, created_at, email, f"{fn} {ln}",
            True if random.random() > 0.03 else False,
            last_login,
            "$2b$12$eX8mP2q1L9v7K6j5H4g3F2d1S0a9Z8x7C6v5B4n3M2l1K0j9H8g7F",
            phone, f"https://api.dicebear.com/7.x/avataaars/svg?seed={fn}_{ln}",
            role, created_at + timedelta(days=random.randint(0, 10))
        ))

    execute_batch_insert(
        db, "users",
        ["id", "bio", "company_name", "created_at", "email", "full_name", "is_active",
         "last_login", "password_hash", "phone", "profile_picture_url", "role", "updated_at"],
        user_rows, chunk_size=1000
    )
    print(f"  + Inserted {len(user_rows):,} users.")

    # -------------------------------------------------------------------------
    # 3. Insert Products (500 Products across 20 Categories)
    # -------------------------------------------------------------------------
    num_products = 500
    print(f"\n[3/9] Generating {num_products:,} Products...")
    product_ids = []
    product_rows = []
    product_prices = {}
    product_titles = {}

    for i in range(num_products):
        pid = str(uuid.uuid4())
        product_ids.append(pid)
        base_title, base_price, discount, desc, short_desc = random.choice(PRODUCT_TEMPLATES)
        cat_id = random.choice(category_ids)
        admin_id = random.choice(admin_ids)
        
        # Add slight variation to title and price
        variant_num = (i // len(PRODUCT_TEMPLATES)) + 1
        title = f"{base_title} (Gen {variant_num})" if variant_num > 1 else base_title
        if i % 10 == 0:
            title = f"{title} - Special Edition"
            
        price = round(base_price * random.uniform(0.85, 1.25), 2)
        disc_pct = float(discount) if random.random() > 0.3 else 0.0
        final_price = round(price * (1.0 - disc_pct / 100.0), 2)
        sku = f"SKU-{cat_id[:4].upper()}-{i+10001:05d}"
        stock = random.randint(10, 850)
        views = random.randint(50, 15000)
        created_at = random_date(300, 10)
        updated_at = created_at + timedelta(days=random.randint(1, 15))

        images_json = json.dumps([
            f"https://assets.store.com/products/{sku.lower()}-front.jpg",
            f"https://assets.store.com/products/{sku.lower()}-side.jpg",
            f"https://assets.store.com/products/{sku.lower()}-angle.jpg"
        ])
        specs_json = json.dumps({
            "warranty_months": random.choice([12, 24, 36]),
            "weight_kg": round(random.uniform(0.2, 5.5), 2),
            "certifications": ["CE", "FCC", "RoHS"],
            "country_of_origin": random.choice(["USA", "Germany", "Japan", "South Korea", "Taiwan"])
        })

        product_prices[pid] = final_price
        product_titles[pid] = title

        product_rows.append((
            pid, created_at, desc, disc_pct, final_price, images_json,
            False, True if random.random() < 0.15 else False,
            price, short_desc, sku, specs_json, random.choice(PRODUCT_STATUSES), stock,
            f"https://assets.store.com/products/{sku.lower()}-thumb.jpg",
            title, updated_at, views, cat_id, admin_id
        ))

    execute_batch_insert(
        db, "products",
        ["id", "created_at", "description", "discount_percentage", "final_price",
         "images_urls", "is_deleted", "is_featured", "price", "short_description",
         "sku", "specifications", "status", "stock_quantity", "thumbnail_url",
         "title", "updated_at", "views_count", "category_id", "created_by_admin_id"],
        product_rows, chunk_size=500
    )
    print(f"  + Inserted {len(product_rows):,} products.")

    # -------------------------------------------------------------------------
    # 4. Insert Orders & Order Items (7,500 Orders with 1-4 Items Each)
    # -------------------------------------------------------------------------
    num_orders = 7500
    print(f"\n[4/9] Generating {num_orders:,} Orders & associated Order Items...")
    order_ids = []
    order_rows = []
    order_item_rows = []

    for i in range(num_orders):
        oid = str(uuid.uuid4())
        order_ids.append(oid)
        uid = random.choice(customer_ids)
        
        # User details
        addr, city, state, zip_c = random.choice(CITIES_ADDRESSES)
        cust_addr = f"{addr}, {city}, {state} {zip_c}"
        cust_email = f"customer_{uid[:8]}@{random.choice(DOMAINS)}"
        cust_phone = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        
        order_num = f"ORD-{datetime.now().year}-{i+100001:06d}"
        status = random.choice(ORDER_STATUSES)
        order_date = random_date(200, 1)
        created_at = order_date
        
        confirmation_at = created_at + timedelta(minutes=random.randint(5, 60)) if status != "pending" else None
        completed_at = confirmation_at + timedelta(days=random.randint(1, 5)) if status == "completed" else None
        updated_at = completed_at or confirmation_at or created_at
        
        # Items in this order
        num_items = random.choices([1, 2, 3, 4], weights=[0.45, 0.35, 0.15, 0.05])[0]
        selected_pids = random.sample(product_ids, num_items)
        
        total_amt = 0.0
        for pid in selected_pids:
            qty = random.randint(1, 3)
            p_price = product_prices[pid]
            subtotal = round(p_price * qty, 2)
            total_amt += subtotal
            
            order_item_rows.append((
                str(uuid.uuid4()), p_price, product_titles[pid], qty, subtotal, oid, pid
            ))

        total_amt = round(total_amt, 2)
        disc_amt = round(total_amt * 0.10, 2) if random.random() < 0.20 else 0.0
        final_amt = round(max(0.0, total_amt - disc_amt), 2)
        wa_link = f"https://wa.me/{cust_phone.replace('-', '')}?text=Order_{order_num}"
        wa_sent = confirmation_at + timedelta(minutes=2) if confirmation_at else None
        notes = "Deliver to door / ring bell." if random.random() < 0.3 else None

        order_rows.append((
            oid, completed_at, confirmation_at, created_at, cust_addr,
            cust_email, cust_phone, disc_amt, final_amt, order_date,
            order_num, notes, status, total_amt, updated_at, wa_link,
            wa_sent, uid
        ))

    execute_batch_insert(
        db, "orders",
        ["id", "completed_at", "confirmation_at", "created_at", "customer_address",
         "customer_email", "customer_phone", "discount_applied", "final_amount",
         "order_date", "order_number", "special_notes", "status", "total_amount",
         "updated_at", "whatsapp_link", "whatsapp_sent_at", "user_id"],
        order_rows, chunk_size=1000
    )
    print(f"  + Inserted {len(order_rows):,} orders.")

    execute_batch_insert(
        db, "order_items",
        ["id", "product_price", "product_title", "quantity", "subtotal", "order_id", "product_id"],
        order_item_rows, chunk_size=2000
    )
    print(f"  + Inserted {len(order_item_rows):,} order items.")

    # -------------------------------------------------------------------------
    # 5. Insert Carts (3,500 Active Carts)
    # -------------------------------------------------------------------------
    num_carts = min(3500, len(customer_ids))
    print(f"\n[5/9] Generating {num_carts:,} Shopping Carts...")
    cart_rows = []
    cart_users = random.sample(customer_ids, num_carts)
    
    for uid in cart_users:
        cid = str(uuid.uuid4())
        cart_pids = random.sample(product_ids, random.randint(1, 4))
        items_payload = [
            {"product_id": pid, "title": product_titles[pid], "price": product_prices[pid], "quantity": random.randint(1, 2)}
            for pid in cart_pids
        ]
        cart_rows.append((cid, json.dumps(items_payload), random_date(10, 0), uid))

    execute_batch_insert(
        db, "cart",
        ["id", "items", "updated_at", "user_id"],
        cart_rows, chunk_size=1000
    )
    print(f"  + Inserted {len(cart_rows):,} cart records.")

    # -------------------------------------------------------------------------
    # 6. Insert Wishlist Items (5,000 Wishlist entries)
    # -------------------------------------------------------------------------
    num_wishlist = 5000
    print(f"\n[6/9] Generating {num_wishlist:,} Wishlist entries...")
    wishlist_rows = []
    wishlist_pairs = set()

    for _ in range(num_wishlist):
        uid = random.choice(customer_ids)
        pid = random.choice(product_ids)
        if (uid, pid) in wishlist_pairs:
            continue
        wishlist_pairs.add((uid, pid))
        wishlist_rows.append((str(uuid.uuid4()), random_date(180, 1), pid, uid))

    execute_batch_insert(
        db, "wishlist",
        ["id", "created_at", "product_id", "user_id"],
        wishlist_rows, chunk_size=1500
    )
    print(f"  + Inserted {len(wishlist_rows):,} wishlist items.")

    # -------------------------------------------------------------------------
    # 7. Insert Reviews (4,000 Product Reviews)
    # -------------------------------------------------------------------------
    num_reviews = 4000
    print(f"\n[7/9] Generating {num_reviews:,} Product Reviews...")
    review_rows = []
    
    for _ in range(num_reviews):
        rid = str(uuid.uuid4())
        pid = random.choice(product_ids)
        uid = random.choice(customer_ids)
        rating, text = random.choice(REVIEW_SNIPPETS)
        created_at = random_date(180, 2)
        updated_at = created_at if random.random() > 0.15 else created_at + timedelta(days=random.randint(1, 10))
        helpful = random.randint(0, 45)

        review_rows.append((
            rid, created_at, helpful, True, rating, text, updated_at, pid, uid
        ))

    execute_batch_insert(
        db, "reviews",
        ["id", "created_at", "helpful_count", "is_verified_purchase", "rating",
         "review_text", "updated_at", "product_id", "user_id"],
        review_rows, chunk_size=1500
    )
    print(f"  + Inserted {len(review_rows):,} reviews.")

    # -------------------------------------------------------------------------
    # 8. Insert Notifications (6,000 Customer Notifications)
    # -------------------------------------------------------------------------
    num_notifications = 6000
    print(f"\n[8/9] Generating {num_notifications:,} Notifications...")
    notif_rows = []

    for _ in range(num_notifications):
        nid = str(uuid.uuid4())
        uid = random.choice(customer_ids)
        ntype = random.choice(NOTIFICATION_TYPES)
        oid = random.choice(order_ids) if random.random() < 0.6 else None
        pid = random.choice(product_ids) if not oid and random.random() < 0.5 else None
        
        titles_and_msgs = {
            "ORDER_STATUS": ("Order Status Update", "Your order has been confirmed and is being prepped for dispatch."),
            "STOCK_ALERT": ("Item Back in Stock!", "An item on your wishlist is back in stock."),
            "DISCOUNT_ALERT": ("Flash Sale is Live!", "Explore top electronics and home decor with up to 30% discount."),
            "ADMIN_MESSAGE": ("Account Security Notice", "Please review your recent account activity.")
        }
        title, msg = titles_and_msgs[ntype]
        is_read = random.random() < 0.65
        created_at = random_date(90, 0)

        notif_rows.append((
            nid, created_at, is_read, msg, title, ntype, oid, pid, uid
        ))

    execute_batch_insert(
        db, "notifications",
        ["id", "created_at", "is_read", "message", "title", "type",
         "related_order_id", "related_product_id", "user_id"],
        notif_rows, chunk_size=2000
    )
    print(f"  + Inserted {len(notif_rows):,} notifications.")

    # -------------------------------------------------------------------------
    # 9. Insert Audit Logs (3,000 Admin Audit Events)
    # -------------------------------------------------------------------------
    num_audits = 3000
    print(f"\n[9/9] Generating {num_audits:,} Governance & Audit Logs...")
    audit_rows = []

    for _ in range(num_audits):
        aid = str(uuid.uuid4())
        action = random.choice(AUDIT_ACTIONS)
        etype = random.choice(["product", "order", "category", "user"])
        eid = random.choice(product_ids if etype == "product" else order_ids if etype == "order" else category_ids if etype == "category" else customer_ids)
        admin = random.choice(admin_ids)
        ip = f"{random.randint(10,210)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        changes = json.dumps({"field": "status", "old": "pending", "new": "active", "updated_by": admin}) if action in ("CREATE", "UPDATE", "DELETE") else None
        created_at = random_date(180, 0)

        audit_rows.append((
            aid, action, changes, created_at, eid, etype, ip, ua, admin
        ))

    execute_batch_insert(
        db, "audit_logs",
        ["id", "action", "changes", "created_at", "entity_id", "entity_type", "ip_address", "user_agent", "admin_id"],
        audit_rows, chunk_size=1500
    )
    print(f"  + Inserted {len(audit_rows):,} audit logs.")

    total_time = time.time() - t0
    total_rows = (
        len(category_rows) + len(user_rows) + len(product_rows) +
        len(order_rows) + len(order_item_rows) + len(cart_rows) +
        len(wishlist_rows) + len(review_rows) + len(notif_rows) + len(audit_rows)
    )

    print("\n" + "=" * 65)
    print(f"[DONE] SEEDING COMPLETE in {total_time:.2f} seconds!")
    print(f"[INFO] Total Records Inserted across 10 Tables: {total_rows:,}")
    print("=" * 65)


if __name__ == "__main__":
    main()
