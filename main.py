import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote
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


def scrape_menu(day_name: str, date_str: str) -> tuple[dict, bool]:
    """Returns (menu dict, is_current) where is_current=False means stale menu."""
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
        return {}, False

    # Check if the date in the heading matches today
    # Heading looks like "Monday 19.05" — extract the date part
    header_text = day_header.get_text(strip=True)  # e.g. "Monday 19.05"
    today_ddmm = datetime.now(TZ).strftime("%d.%m")  # e.g. "19.05"
    is_current = today_ddmm in header_text

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

    return menu, is_current


def format_message(day_name: str, date_str: str, menu: dict, is_current: bool) -> str:
    lines = [f"🍽️ *Foodies — {day_name} {date_str}*", ""]

    if not is_current and menu:
        lines.append("⚠️ *Menu not updated yet for today — this may be last week's. Check the site to be sure:*")
        lines.append("https://foodies-ams.nl/weekly-menu")
        lines.append("")

    if not menu:
        lines.append("❌ No menu found for today. Check https://foodies-ams.nl/weekly-menu")
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
    # Build URL manually so the + in the phone number doesn't get encoded as %2B
    phone = PHONE.lstrip("+")  # strip + if present, we add it manually
    text = quote(message)
    url = f"{CALLMEBOT_URL}?phone=+{phone}&text={text}&apikey={API_KEY}"
    r = requests.get(url, timeout=15)
    print(f"CallMeBot status {r.status_code}: {r.text}")
    r.raise_for_status()


def is_correct_run_time() -> bool:
    """Returns True only if it's 8:xx AM Amsterdam — guards against the off-season UTC cron fire.
    Skips the check if triggered manually."""
    if os.environ.get("MANUAL_TRIGGER") == "true":
        return True
    return datetime.now(TZ).hour == 8


def main():
    day_name, date_str = today()

    # DST guard: cron fires at two UTC times, only one will match 8 AM Amsterdam
    if not is_correct_run_time():
        print("Not the right Amsterdam time — exiting silently.")
        return

    print(f"Fetching menu for {day_name} {date_str}...")

    menu, is_current = scrape_menu(day_name, date_str)
    msg = format_message(day_name, date_str, menu, is_current)

    print("\n--- MESSAGE PREVIEW ---")
    print(msg)
    print("-----------------------\n")

    send_whatsapp(msg)
    print("✅ WhatsApp message sent.")


if __name__ == "__main__":
    main()
