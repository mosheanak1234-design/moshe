"""
🚗 רובוט עסקאות רכב - יד2
שולח התראת טלגרם על כל רכב מתחת למחיר שוק
"""

import os
import json
import time
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, quote

# ============================================================
# הגדרות - שנה כאן לפי הצרכים שלך
# ============================================================

DISCOUNT_THRESHOLD = 15       # % הנחה מינימלית ממחירון
SEEN_FILE = "seen_listings.json"

# URL של חיפוש יד2 - כנס ליד2, סנן מה שאתה רוצה, העתק את הURL
YAD2_SEARCH_URLS = [


`"https://www.yad2.co.il/vehicles/cars?year=2019-2025"`
]

# CallMeBot - טלגרם
TELEGRAM_USERNAME = os.environ.get("TELEGRAM_USERNAME", "@moshe102002")

# ============================================================
# פונקציות ליד2
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
    "Referer": "https://www.yad2.co.il/",
    "Origin": "https://www.yad2.co.il",
}

def parse_yad2_url_to_api(search_url):
    parsed = urlparse(search_url)
    params = parse_qs(parsed.query)
    flat_params = {k: v[0] for k, v in params.items()}
    flat_params["rows"] = "40"
    flat_params["order"] = "date"
    flat_params["page"] = "1"
    return f"https://gw.yad2.co.il/feed-search-legacy/vehicles/cars/private-cars?{urlencode(flat_params)}"

def fetch_yad2_listings(search_url):
    listings = []
    try:
        api_url = parse_yad2_url_to_api(search_url)
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"❌ יד2 החזיר {resp.status_code}")
            return []
        data = resp.json()
        feed_items = data.get("data", {}).get("feed", {}).get("feed_items", [])
        for item in feed_items:
            if item.get("type") == "ad":
                listing = parse_yad2_item(item)
                if listing:
                    listings.append(listing)
    except Exception as e:
        print(f"❌ שגיאה בשליפת יד2: {e}")
    return listings

def parse_yad2_item(item):
    try:
        row = item.get("row", {})
        price = row.get("price")
        list_price = row.get("PriceByMechironList")
        if not price or not list_price:
            return None
        price = int(str(price).replace(",", "").replace("₪", "").strip())
        list_price = int(str(list_price).replace(",", "").replace("₪", "").strip())
        if list_price <= 0 or price <= 0:
            return None
        discount_pct = round((1 - price / list_price) * 100, 1)
        return {
            "id": item.get("id", ""),
            "title": f"{row.get('manufacturer_he', '')} {row.get('model_he', '')} {row.get('year', '')}",
            "year": row.get("year"),
            "km": row.get("km"),
            "price": price,
            "list_price": list_price,
            "discount_pct": discount_pct,
            "city": row.get("city_text", ""),
            "hand": row.get("hand", ""),
            "color": row.get("color_he", ""),
            "url": f"https://www.yad2.co.il/item/{item.get('id', '')}",
            "phone": row.get("phones", {}).get("phone1", {}).get("phone", "") if isinstance(row.get("phones"), dict) else "",
        }
    except Exception as e:
        print(f"  שגיאה בניתוח פריט: {e}")
        return None

# ============================================================
# זיכרון
# ============================================================

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_seen(seen_ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_ids)[-2000:], f)

# ============================================================
# שליחת טלגרם
# ============================================================

def send_telegram(message):
    """שולח הודעת טלגרם דרך CallMeBot"""
    try:
        encoded_msg = quote(message)
        url = f"https://api.callmebot.com/text.php?user={TELEGRAM_USERNAME}&text={encoded_msg}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            print(f"✅ טלגרם נשלח!")
            return True
        else:
            print(f"❌ שגיאת CallMeBot: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ שגיאה בשליחת טלגרם: {e}")
        return False

def build_message(listing):
    km_str = f"{listing['km']:,}".replace(",", ".") if listing.get("km") else "לא ידוע"
    price_str = f"{listing['price']:,}".replace(",", ".")
    list_price_str = f"{listing['list_price']:,}".replace(",", ".")
    saving = listing['list_price'] - listing['price']

    lines = [
        f"🚗 עסקה חדשה - {listing['discount_pct']}% מתחת למחירון!",
        f"",
        f"🔹 {listing['title']}",
        f"📍 {listing['city']} | יד {listing.get('hand', '?')} | {listing.get('color', '')}",
        f"📏 קמ: {km_str}",
        f"",
        f"💰 מחיר: {price_str} שח",
        f"📋 מחירון: {list_price_str} שח",
        f"✅ חיסכון: {saving:,} שח ({listing['discount_pct']}%)",
        f"",
        f"🔗 {listing['url']}",
        f"⏰ {datetime.now().strftime('%H:%M | %d/%m/%Y')}",
    ]
    if listing.get("phone"):
        lines.append(f"📞 {listing['phone']}")
    return "\n".join(lines)

# ============================================================
# ריצה ראשית
# ============================================================

def run():
    print(f"\n{'='*50}")
    print(f"🤖 רובוט עסקאות רכב - {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")
    print(f"🎯 סף הנחה: {DISCOUNT_THRESHOLD}%")
    print(f"{'='*50}\n")

    seen_ids = load_seen()
    print(f"📚 זיכרון: {len(seen_ids)} מודעות קיימות\n")

    all_deals = []

    print("🔍 סורק יד2...")
    for url in YAD2_SEARCH_URLS:
        listings = fetch_yad2_listings(url)
        print(f"  נמצאו {len(listings)} מודעות")
        for listing in listings:
            lid = listing["id"]
            if lid in seen_ids:
                continue
            seen_ids.add(lid)
            if listing["discount_pct"] >= DISCOUNT_THRESHOLD:
                print(f"  ✅ עסקה! {listing['title']} - {listing['discount_pct']}% הנחה")
                all_deals.append(listing)
            else:
                print(f"  ⏭  {listing['title']} - {listing['discount_pct']}% (לא מספיק)")
        time.sleep(2)

    print(f"\n📊 סיכום: {len(all_deals)} עסקאות חדשות")
    all_deals.sort(key=lambda x: x["discount_pct"], reverse=True)

    for deal in all_deals:
        msg = build_message(deal)
        send_telegram(msg)
        time.sleep(3)

    if not all_deals:
        print("😴 אין עסקאות חדשות הפעם")

    save_seen(seen_ids)
    print(f"\n✅ סריקה הסתיימה - {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    run()
