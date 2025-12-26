from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import date
from database import get_connection
from links import IMMOWEB_LINKS_VENTE
import time


def save_bien(data):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, prix_achat FROM biens_vente WHERE immoweb_id = %s
    """, (data["immoweb_id"],))

    existing = cur.fetchone()

    if existing:
        bien_id, old_price = existing
        if old_price != data["prix_achat"]:
            cur.execute("""
                INSERT INTO historiques_prix (bien_id, ancien_prix, nouveau_prix, date_changement)
                VALUES (%s, %s, %s, %s)
            """, (bien_id, old_price, data["prix_achat"], date.today()))

            cur.execute("""
                UPDATE biens_vente
                SET prix_achat=%s, date_dernier_update=%s
                WHERE id=%s
            """, (data["prix_achat"], date.today(), bien_id))
    else:
        cur.execute("""
            INSERT INTO biens_vente (
                immoweb_id, type_bien, prix_achat, surface,
                chambres, localisation, jardin,
                date_premier_scrape, date_dernier_update, url
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data["immoweb_id"],
            data["type_bien"],
            data["prix_achat"],
            data["surface"],
            data["chambres"],
            data["localisation"],
            data["jardin"],
            date.today(),
            date.today(),
            data["url"]
        ))

    conn.commit()
    cur.close()
    conn.close()


def scrape_link(page, url):
    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    soup = BeautifulSoup(page.content(), "html.parser")
    cards = soup.select("article")

    for card in cards:
        try:
            link = card.find("a", href=True)["href"]
            immoweb_id = link.split("/")[-1]

            price = card.get_text()
            price = "".join([c for c in price if c.isdigit()])
            price = int(price) if price else None

            data = {
                "immoweb_id": immoweb_id,
                "type_bien": "maison",  # simplifié pour commencer
                "prix_achat": price,
                "surface": None,
                "chambres": None,
                "localisation": "Belgique",
                "jardin": None,
                "url": "https://www.immoweb.be" + link
            }

            if price:
                save_bien(data)

        except Exception:
            continue


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for nom, url in IMMOWEB_LINKS_VENTE.items():
            print(f"Scraping : {nom}")
            scrape_link(page, url)
            time.sleep(10)

        browser.close()


if __name__ == "__main__":
    main()
