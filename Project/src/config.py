"""
Shared configuration for DineIQ Analytics.

Everything the generator and the pipeline both need to agree on lives here -
folder paths, the menu, the locations, channel mix, and the thresholds the
classifier uses. Keeping it in one place means a "surprise modification" during
evaluation (add a location, tweak a threshold, add a category) is a one-line
change, not a treasure hunt.

Dataset scale is deliberately sized to clear the SRS minimums:
  >= 1,000,000 order-lines · >= 100,000 orders · >= 50,000 customers
  >= 150 menu items · >= 10 categories · >= 20 locations · >= 12 months history
  >= 100,000 ratings · >= 50,000 wastage records · multi price/promo history
"""
from pathlib import Path
import numpy as np

# ---- folders -------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
PROCESSED = ROOT / "processed_data"
OUTPUTS = ROOT / "outputs"
for _d in (RAW, PROCESSED, OUTPUTS):
    _d.mkdir(exist_ok=True)

SEED = 20260926          # reproducible everything
ANALYSIS_END = "2026-09-25"
HISTORY_DAYS = 365       # 12 months of transaction history

# ---- volume targets (the generator sizes itself off these) ---------------
N_CUSTOMERS = 52000      # >= 50k
ORDERS_PER_CELL = 34     # avg orders per (location, day) before rhythm mult
BASKET_LAMBDA = 2.6      # poisson mean for (basket_size - 1)

# ---- reference data ------------------------------------------------------
# 10 categories, each with 15 dishes -> 150 items.
MENU = {
    "Starters": [
        "Truffle Fries", "Loaded Nachos", "Soup of the Day", "Calamari Rings",
        "Chicken Wings", "Spring Rolls", "Garlic Bread", "Bruschetta",
        "Hummus Platter", "Stuffed Mushrooms", "Cheese Sticks", "Onion Rings",
        "Prawn Tempura", "Caesar Salad", "Greek Salad",
    ],
    "Signature Mains": [
        "Signature Ribeye", "Butter Chicken", "Grilled Salmon", "Mushroom Risotto",
        "Beef Stroganoff", "Chicken Alfredo", "Lamb Rogan Josh", "Thai Green Curry",
        "Roast Chicken", "Beef Wellington", "Duck Confit", "Vegetable Korma",
        "Chicken Parmesan", "Pan-Seared Steak", "Paneer Tikka Masala",
    ],
    "Grills & BBQ": [
        "Smoked Brisket", "BBQ Ribs Full Rack", "Peri Peri Chicken", "Lamb Chops",
        "Grilled Kebab Platter", "Tandoori Chicken", "BBQ Pulled Pork",
        "Grilled Lamb Skewers", "Char-Grilled Steak", "Smoked Sausage Plate",
        "Chicken Tikka Skewers", "Grilled Veg Platter", "Beef Short Ribs",
        "Spicy Buffalo Wings", "Mixed Grill",
    ],
    "Pizza & Pasta": [
        "Margherita Pizza", "Pepperoni Pizza", "Truffle Carbonara", "Four Cheese Pasta",
        "BBQ Chicken Pizza", "Veggie Supreme Pizza", "Spaghetti Bolognese",
        "Penne Arrabbiata", "Lasagne al Forno", "Meat Feast Pizza", "Hawaiian Pizza",
        "Mushroom Pizza", "Seafood Linguine", "Mac and Cheese", "Pesto Pasta",
    ],
    "Burgers & Sandwiches": [
        "Classic Beef Burger", "Cheeseburger Deluxe", "Crispy Chicken Burger",
        "Double Bacon Burger", "Veggie Burger", "Pulled Pork Sandwich",
        "Club Sandwich", "Grilled Chicken Wrap", "Fish Burger", "Steak Sandwich",
        "Falafel Wrap", "Philly Cheesesteak", "BBQ Bacon Burger",
        "Spicy Zinger Burger", "Halloumi Burger",
    ],
    "Rice & Biryani": [
        "Chicken Biryani", "Mutton Biryani", "Veg Biryani", "Egg Fried Rice",
        "Chicken Fried Rice", "Prawn Biryani", "Jeera Rice", "Mushroom Rice",
        "Beef Pulao", "Vegetable Pulao", "Schezwan Fried Rice", "Kabuli Pulao",
        "Lemon Rice", "Hyderabadi Biryani", "Steamed Basmati",
    ],
    "Seafood": [
        "Grilled Prawns", "Fish and Chips", "Butter Garlic Shrimp", "Crab Cakes",
        "Lobster Thermidor", "Fried Calamari", "Grilled Octopus", "Seafood Platter",
        "Salmon Teriyaki", "Prawn Curry", "Baked Cod", "Mussels Marinara",
        "Tuna Steak", "Fish Tacos", "Shrimp Scampi",
    ],
    "Desserts": [
        "Molten Lava Cake", "New York Cheesecake", "Gelato Trio", "Tiramisu",
        "Chocolate Brownie", "Creme Brulee", "Apple Pie", "Sticky Toffee Pudding",
        "Banoffee Pie", "Panna Cotta", "Fruit Tart", "Ice Cream Sundae",
        "Baklava", "Carrot Cake", "Red Velvet Slice",
    ],
    "Beverages": [
        "Fresh Lemonade", "Craft Cold Brew", "Mango Smoothie", "Iced Latte",
        "Masala Chai", "Fresh Orange Juice", "Sparkling Water", "Cappuccino",
        "Strawberry Milkshake", "Green Tea", "Coca-Cola", "Virgin Mojito",
        "Espresso", "Berry Smoothie", "Salted Caramel Frappe",
    ],
    "Sides & Extras": [
        "French Fries", "Mashed Potatoes", "Steamed Vegetables", "Coleslaw",
        "Side Salad", "Garlic Naan", "Buttered Corn", "Cheese Dip",
        "Sweet Potato Fries", "Rice Bowl", "Pita Bread", "Grilled Corn",
        "Extra Cheese", "Dinner Roll", "Pickle Plate",
    ],
}
CATEGORIES = list(MENU.keys())

# per-category (min_price, max_price) band - the economics builder draws in here
_PRICE_BAND = {
    "Starters": (5.0, 11.0), "Signature Mains": (14.0, 30.0),
    "Grills & BBQ": (16.0, 30.0), "Pizza & Pasta": (12.0, 20.0),
    "Burgers & Sandwiches": (9.0, 16.0), "Rice & Biryani": (10.0, 20.0),
    "Seafood": (15.0, 30.0), "Desserts": (5.0, 10.0),
    "Beverages": (3.0, 7.0), "Sides & Extras": (3.0, 8.0),
}


def _build_dishes():
    """
    Turn the curated menu into (name, category, base_price, food_cost, popularity)
    tuples. Prices sit inside each category's band; food-cost fraction and
    popularity are drawn independently so the menu naturally spans all four
    performance quadrants (high/low demand x high/low margin) - a few deliberate
    loss-leaders too so the classifier has genuine volume-driver traps to catch.
    """
    r = np.random.default_rng(SEED + 7)
    dishes = []
    for cat, names in MENU.items():
        lo, hi = _PRICE_BAND[cat]
        for nm in names:
            price = round(float(r.uniform(lo, hi)), 2)
            # most items 30-55% food cost; ~1 in 6 is a loss-leader (up to 70%)
            frac = float(r.uniform(0.30, 0.55))
            if r.random() < 0.16:
                frac = float(r.uniform(0.58, 0.72))
            cost = round(price * frac, 2)
            # popularity: skewed - a handful of stars, a long tail of slow movers
            pop = round(float(np.clip(r.beta(1.7, 3.2) * 1.15, 0.05, 1.0)), 2)
            dishes.append((nm, cat, price, cost, pop))
    return dishes


DISHES = _build_dishes()          # 150 items

# 20 restaurant locations across a few cities
LOCATIONS = [
    ("Downtown", "Metro City"), ("Harborview", "Metro City"),
    ("Uptown", "Metro City"), ("Airport Terminal", "Metro City"),
    ("Riverside", "Metro City"), ("Grand Mall", "Northgate"),
    ("Old Town", "Northgate"), ("Lakeside", "Northgate"),
    ("Tech Park", "Northgate"), ("Station Square", "Northgate"),
    ("Beachfront", "Sunport"), ("Marina Bay", "Sunport"),
    ("Hillcrest", "Sunport"), ("Sunset Plaza", "Sunport"),
    ("Central Station", "Eastvale"), ("Green Valley", "Eastvale"),
    ("University District", "Eastvale"), ("Business Bay", "Eastvale"),
    ("Silver Heights", "Westbrook"), ("Palm Court", "Westbrook"),
]

CHANNELS = ["Dine-in", "Takeaway", "Website / App", "Delivery"]
# rough share of orders per channel - dine-in still leads but delivery is big
CHANNEL_WEIGHTS = [0.38, 0.18, 0.20, 0.24]

PROMOTIONS = [
    ("Weekday Lunch Combo", "combo", 15),
    ("Family Combo", "combo", 25),           # the "trap" - discounts profitable mains
    ("App-Only 20% Off", "channel", 20),
    ("Dessert Add-on", "upsell", 10),
    ("Happy Hour Drinks", "timed", 30),
    ("Weekend Feast", "combo", 22),
    ("Student Discount", "channel", 12),
    ("Loyalty Reward", "loyalty", 8),
    ("Seasonal Special", "timed", 18),
]

# segments we bucket customers into after RFM scoring
SEGMENT_ORDER = [
    "High-Value Loyal", "Frequent", "Promotion-Driven",
    "Occasional", "New", "At-Risk",
]

# ---- classification thresholds (data-driven, but the cut points live here) --
# demand & profit are scored 0..1 relative to the whole menu; these are the
# lines that split the four quadrants. Change these for a surprise mod.
DEMAND_CUT = 0.55
PROFIT_CUT = 0.45

# ---- forecasting ---------------------------------------------------------
FORECAST_HORIZON = 14    # days ahead
HOLDOUT_DAYS = 14        # kept unseen to measure honest error
