import os
import time
import random
import psycopg2
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

# Récupération des secrets
DB_URL = os.environ.get("DATABASE_URL")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = "dim.vandyck@gmail.com"

SEARCH_URLS = [
    {"name": "Maman", "url": "https://www.immoweb.be/fr/carte/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=uwnrHed~Z{D{_C|Ky~FuCwzDgNa{AhAexEe[ojAacAfv@kBx@_|@|y@}cEU_jAkF_qAb@kOpOe@vp@jOng@jAdv@kj@niE{RjsD?bcAbb@jsD|YrZjj@fSr^re@l_AxXqAdHpy@yXz_@?nfAm@zf@dHpd@?xs@m\lq@kwA~t@c@&orderBy=relevance"},
    {"name": "Namur", "url": "https://www.immoweb.be/fr/carte/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=ysurHiom\zh@m{AhQ}jAbLclG?ulCg{@ocI{WwAgyAi~BmwDiuA_eBuYmk@?ehAhp@}qDnkD{q@xnCef@vfH?ddE|q@~bFxu@tBv{AtlCj~AfsAlkBh@jqAAz{Aw[dnBgzBtvAcoAjMox@uNtY&orderBy=relevance"}
]

def envoyer_email(nb_annonces):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("⚠️ Email non configuré (Secrets manquants)")
        return
    try:
        msg = MIMEText(f"Le robot Immo a terminé. {nb_annonces} annonces ont été traitées aujourd'hui.")
        msg['Subject'] = f"🚀 Rapport Immo : {nb_annonces} annonces"
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("📧 Email envoyé avec succès.")
    except Exception as e:
        print(f"❌ Erreur email: {e}")

def save_to_db(annonce):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        query = """
            INSERT INTO annonces (id, url, prix, type, surface, chambres, zip, zone_filtre)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET prix = EXCLUDED.prix, updated_at = NOW()
            WHERE annonces.prix != EXCLUDED.prix;
        """
        cur.execute(query, (annonce['id'], annonce['url'], annonce['prix'], annonce['type'], annonce['surface'], annonce['chambres'], annonce['zip'], annonce['zone_filtre']))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Erreur DB: {e}")

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        total_found = 0

        for zone in SEARCH_URLS:
            print(f"🔎 Zone: {zone['name']}")
            page.goto(f"{zone['url']}&page=1")
            time.sleep(2)
            
            # Récupération des liens corrigée
            locators = page.locator("a[href*='/annonce/']").all()
            links = [l.get_attribute("href") for l in locators]
            unique_links = list(set([l for l in links if l and "www.immoweb.be" in l]))[:5]

            for link in unique_links:
                try:
                    page.goto(link)
                    time.sleep(1)
                    data = page.evaluate("window.classified")
                    if data:
                        annonce = {
                            "id": data.get("id"),
                            "prix": data.get("transaction", {}).get("sale", {}).get("price"),
                            "type": data.get("property", {}).get("type"),
                            "surface": data.get("property", {}).get("netHabitableSurface"),
                            "chambres": data.get("property", {}).get("bedroomCount"),
                            "zip": data.get("property", {}).get("location", {}).get("postalCode"),
                            "url": link,
                            "zone_filtre": zone['name']
                        }
                        save_to_db(annonce)
                        total_found += 1
                        print(f"✅ Annonce {annonce['id']} traitée")
                except:
                    continue
        
        browser.close()
        envoyer_email(total_found)

if __name__ == "__main__":
    run()
