import os
import time
import random
import psycopg2
import smtplib
import math
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

# --- CONFIGURATION & SECRETS ---
DB_URL = os.environ.get("DATABASE_URL")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = "dim.vandyck@gmail.com"

SEARCH_URLS = [
    {"name": "Maman", "url": "https://www.immoweb.be/fr/carte/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=uwnrHed~Z{D{_C|Ky~FuCwzDgNa{AhAexEe[ojAacAfv@kBx@_|@|y@}cEU_jAkF_qAb@kOpOe@vp@jOng@jAdv@kj@niE{RjsD?bcAbb@jsD|YrZjj@fSr^re@l_AxXqAdHpy@yXz_@?nfAm@zf@dHpd@?xs@m\lq@kwA~t@c@&orderBy=relevance"},
    {"name": "Namur", "url": "https://www.immoweb.be/fr/carte/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=ysurHiom\zh@m{AhQ}jAbLclG?ulCg{@ocI{WwAgyAi~BmwDiuA_eBuYmk@?ehAhp@}qDnkD{q@xnCef@vfH?ddE|q@~bFxu@tBv{AtlCj~AfsAlkBh@jqAAz{Aw[dnBgzBtvAcoAjMox@uNtY&orderBy=relevance"}
]

# --- FONCTIONS DE CALCUL ---
def calculer_metrics(prix, type_bien, rc):
    if not prix: return 0, 0
    
    # Hypothèse Loyer : 4.5% du prix / 12 (Estimation prudente)
    loyer = (prix * 0.045) / 12
    
    # Emprunt (Total avec frais de notaire 12.5%) sur 20 ans à 3.5%
    capital = prix * 1.125
    taux_mensuel = 0.035 / 12
    mensualite = capital * (taux_mensuel * (1 + taux_mensuel)**240) / ((1 + taux_mensuel)**240 - 1)
    
    # Frais fixes
    frais_gestion = 250 if type_bien.upper() == "APARTMENT" else 150
    taxe_rc = (float(rc or 0) * 2.5) / 12
    
    cashflow = loyer - mensualite - frais_gestion - taxe_rc
    renta_brute = (loyer * 12) / prix * 100
    
    return round(cashflow, 2), round(renta_brute, 2)

# --- COMMUNICATION ---
def envoyer_rapport(annonces_data):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("⚠️ Erreur: Secrets Email manquants.")
        return
    
    nb = len(annonces_data)
    corps = f"Le robot a trouvé {nb} annonces.\n\n"
    for a in annonces_data:
        corps += f"- {a['type']} à {a['zip']} ({a['prix']}€) | CF: {a['cf']}€ | Renta: {a['renta']}% \n  Lien: {a['url']}\n\n"

    msg = MIMEText(corps)
    msg['Subject'] = f"📊 Rapport Immo : {nb} pépites trouvées"
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("📧 Email envoyé !")
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")

def save_to_db(a):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        query = """
            INSERT INTO annonces (id, url, prix, type, surface, chambres, zip, zone_filtre, cashflow, rentabilite)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET prix = EXCLUDED.prix, updated_at = NOW(), cashflow = EXCLUDED.cashflow;
        """
        cur.execute(query, (a['id'], a['url'], a['prix'], a['type'], a['surface'], a['chambres'], a['zip'], a['zone_filtre'], a['cf'], a['renta']))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Erreur DB sur {a['id']}: {e}")

# --- MOTEUR DE SCRAPING ---
def run():
    with sync_playwright() as p:
        print("⚙️ Lancement du moteur Cloud...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        all_results = []

        for zone in SEARCH_URLS:
            print(f"\n🌍 SCAN ZONE : {zone['name']}")
            for p_num in range(1, 3): # Scan 2 pages par zone
                target_url = f"{zone['url']}&page={p_num}"
                print(f"📄 Page {p_num} : Chargement...")
                page.goto(target_url, wait_until="networkidle")
                
                # Accepter les cookies si présents
                try: page.click("#uc-btn-accept-banner", timeout=3000)
                except: pass
                
                # On scroll pour forcer Immoweb à charger les annonces
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)

                # Capture des liens
                locators = page.locator("a.card__title-link").all() # Sélecteur plus précis
                links = [l.get_attribute("href") for l in locators if l.get_attribute("href")]
                unique_links = list(set([l for l in links if "/annonce/" in l]))
                
                print(f"✅ Trouvé {len(unique_links)} liens potentiels.")

                for link in unique_links:
                    try:
                        print(f"   🔎 Analyse : {link.split('/')[-1]}")
                        page.goto(link, wait_until="domcontentloaded")
                        data = page.evaluate("window.classified")
                        
                        if data:
                            prix = data.get("transaction", {}).get("sale", {}).get("price")
                            type_b = data.get("property", {}).get("type", "UNKNOWN")
                            rc = data.get("transaction", {}).get("sale", {}).get("cadastralIncome")
                            
                            cf, renta = calculer_metrics(prix, type_b, rc)
                            
                            item = {
                                "id": data.get("id"),
                                "url": link,
                                "prix": prix,
                                "type": type_b,
                                "surface": data.get("property", {}).get("netHabitableSurface"),
                                "chambres": data.get("property", {}).get("bedroomCount"),
                                "zip": data.get("property", {}).get("location", {}).get("postalCode"),
                                "zone_filtre": zone['name'],
                                "cf": cf,
                                "renta": renta
                            }
                            save_to_db(item)
                            all_results.append(item)
                    except Exception as e:
                        print(f"   ⚠️ Erreur sur lien : {e}")
                        continue

        browser.close()
        envoyer_rapport(all_results)
        print(f"\n🎯 TERMINÉ. {len(all_results)} annonces en base.")

if __name__ == "__main__":
    run()
