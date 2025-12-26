import os
import time
import random
import psycopg2
from playwright.sync_api import sync_playwright

# Récupération du mot de passe de la base de données depuis les "Secrets" GitHub
DB_URL = os.environ.get("DATABASE_URL")

SEARCH_URLS = [
   {"name": "Maman", "url": "https://www.immoweb.be/fr/carte/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=uwnrHed~Z{D{_C|Ky~FuCwzDgNa{AhAexEe[ojAacAfv@kBx@_|@|y@}cEU_jAkF_qAb@kOpOe@vp@jOng@jAdv@kj@niE{RjsD?bcAbb@jsD|YrZjj@fSr^re@l_AxXqAdHpy@yXz_@?nfAm@zf@dHpd@?xs@m\lq@kwA~t@c@&orderBy=relevance"},
   # Ajoutez vos autres liens ici
]

def save_to_db(annonce):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # Insertion ou mise à jour si le prix change
        query = """
            INSERT INTO annonces (id, url, prix, type, surface, chambres, zip, zone_filtre)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE 
            SET prix = EXCLUDED.prix, updated_at = NOW()
            WHERE annonces.prix != EXCLUDED.prix;
        """
        cur.execute(query, (
            annonce['id'], annonce['url'], annonce['prix'], annonce['type'],
            annonce['surface'], annonce['chambres'], annonce['zip'], annonce['zone_filtre']
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Sauvegardé : {annonce['id']}")
    except Exception as e:
        print(f"Erreur DB: {e}")

def run():
    with sync_playwright() as p:
        # IMPORTANT POUR LE CLOUD : headless=True (pas d'interface graphique)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        page = context.new_page()

        for zone in SEARCH_URLS:
            print(f"Zone: {zone['name']}")
            page.goto(f"{zone['url']}&page=1")
            
            # Gestion cookies
            try: page.locator("#uc-btn-accept-banner").click(timeout=3000)
            except: pass
            
            time.sleep(2)
            
            # Récupération simple des liens (à adapter selon le layout)
            links = page.locator("a[href*='/annonce/']").all_links()
            unique_links = list(set([l for l in links if "www.immoweb.be" in l]))[:5] # Limite à 5 pour test rapide

            for link in unique_links:
                try:
                    page.goto(link)
                    time.sleep(random.uniform(1, 2))
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
                        if annonce['id'] and annonce['prix']:
                            save_to_db(annonce)
                except Exception as e:
                    print(f"Erreur lien: {e}")

        browser.close()

if __name__ == "__main__":
    run()

import smtplib
from email.mime.text import MIMEText

def envoyer_email(nb_annonces):
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    receiver = os.environ.get("EMAIL_RECEIVER")
    
    msg = MIMEText(f"Le robot Immo a terminé. {nb_annonces} annonces ont été traitées et analysées aujourd'hui.")
    msg['Subject'] = f"Rapport Immo : {nb_annonces} annonces"
    msg['From'] = sender
    msg['To'] = receiver

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
