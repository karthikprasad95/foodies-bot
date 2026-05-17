import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlencode
import pytz

MENU_URL = "https://foodies-ams.nl/weekly-menu"
CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"
TZ = pytz.timezone("Europe/Amsterdam")

PHONE   = os.environ["WHATSAPP_PHONE"]    # e.g. 31612345678 (no +)
API_KEY = os.environ["CALLMEBOT_API_KEY"]

EMOJI = {
    "Vegan Meal":      "🌱",
    "Other Meal":      "🍗",
    "Soup":            "🥣",
    "Smoothie":        "🥤",
    "3PM snack":       "🍰",
    "3Pm snack":       "🍰",
    "Special bowl":    "🥗",
    "Composed salad":  "🥙",
    "Pick and mix":    "🍴",
    "Dessert":         "🍮",
}

DAY_NAMES = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]


def today():
    now = datetime.now(TZ)
    return now.strftime("%A"), now.strftime("%d %b")


def scrape_menu(day_name: str) -> dict:
    r = requests.get(MENU_URL, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Find heading containing today's day name
    day_header = None
    for tag in soup.find_all(["h1","h2","h3"]):
        if day_name.lower() in tag.get_text().lower():
            day_header = tag
            break

    if not day_header:
        return {}

    menu = {}
    current_cat = None

    for sib in day_header.find_next_siblings():
        txt = sib.get_text(strip=True)

        # Stop at next day heading
        if sib.name in ("h1","h2","h3"):
            if any(d in txt.lower() for d in DAY_NAMES):
                break

        # Category label (ends with ":")
        if sib.name == "p" and txt.endswith(":"):
            current_cat = txt.rstrip(":")
            menu[current_cat] = []

        # Items list
        elif sib.name == "ul" and current_cat is not None:
            for li in sib.find_all("li"):
                item = li.get_text(strip=True)
                if item:
                    menu[current_cat].append(item)

    return menu


def format_message(day_name: str, date_str: str, menu: dict) -> str:
    lines = [f"🍽️ *Foodies — {day_name} {date_str}*", ""]

    if not menu:
        lines.append("No menu found for today. Check https://foodies-ams.nl/weekly-menu")
        return "\n".join(lines)

    for cat, items in menu.items():
        if not items:
            continue
        emoji = EMOJI.get(cat, "•")
        lines.append(f"{emoji} *{cat}*")
        for item in items:
            lines.append(f"   - {item}")
        lines.append("")

    lines.append("_Enjoy your lunch! 🙌_")
    return "\n".join(lines).strip()


def send_whatsapp(message: str):
    params = {"phone": PHONE, "text": message, "apikey": API_KEY}
    url = f"{CALLMEBOT_URL}?{urlencode(params)}"
    r = requests.get(url, timeout=15)
    print(f"CallMeBot status {r.status_code}: {r.text}")
    r.raise_for_status()


def main():
    day_name, date_str = today()
    print(f"Fetching menu for {day_name} {date_str}...")

    menu = scrape_menu(day_name)
    msg  = format_message(day_name, date_str, menu)

    print("\n--- MESSAGE PREVIEW ---")
    print(msg)
    print("-----------------------\n")

    send_whatsapp(msg)
    print("✅ WhatsApp message sent.")


if __name__ == "__main__":
    main()
