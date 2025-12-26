import os
import time
import random
import psycopg2
import smtplib
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
DB_URL = os.environ.get("DATABASE_URL")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = "dim.vandyck@gmail.com"

SEARCH_URLS = [
    {"name": "Maman", "url": "https://www.immoweb.be/fr/carte/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=uwnrHed~Z{D{_C|Ky~FuCwzDgNa{AhAexEe[ojAacAfv@kBx@_|@|y@}cEU_jAkF_qAb@kOpOe@vp@jOng@jAdv@kj@niE{RjsD?bcAbb@jsD|YrZjj@fSr^re@l_AxXqAdHpy@yXz_@?nfAm@zf@dHpd@?xs@m\lq@kwA~t@c@&orderBy=relevance"},
    {"name": "Namur", "url": "https://www.immoweb.be/fr/carte/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=ysurHiom\zh@m{AhQ}jAbLclG?ulCg{@ocI{WwAgyAi~BmwDiuA_eBuYmk@?ehAhp@}qDnkD{q@xnCef@vfH?ddE|q@~bFxu@tBv{AtlCj~AfsAlkBh@jqAAz{Aw[dnBgzBtvAcoAjMox@uNtY&orderBy=relevance"}
]

def calculer_metrics(prix, type_bien, rc):
    if not prix or prix < 1000: return 0, 0
    loyer = (prix * 0.045) / 12
    capital = prix * 1.125
    taux_mensuel = 0.035 / 12
    mensualite = capital * (taux_mensuel * (1 + taux_mensuel)**240) / ((1 + taux_mensuel)**240 - 1)
    frais = 250 if "APARTMENT" in str(type_bien).upper() else 150
    taxe_rc = (float(rc or 0) * 2.5) / 12
    cashflow = loyer - mensualite - frais - taxe_rc
    renta = (loyer * 12) / prix * 100
    return round(cashflow, 2), round(renta, 2)

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
        print(f"   ❌ Erreur DB: {e}")

def run():
    with sync_playwright() as p:
        print("⚙️ Lancement du moteur avec camouflage...")
        # Utilisation d'un vrai User-Agent pour ne pas griller le bot
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        all_results = []

        for zone in SEARCH_URLS:
            print(f"\n🌍 ZONE : {zone['name']}")
            for p_num in range(1, 2): # On teste sur la page 1 d'abord
                url = f"{zone['url']}&page={p_num}"
                print(f"🔗 Navigation vers : {url}")
                page.goto(url, wait_until="networkidle", timeout=60000)
                
                # Attente aléatoire + scroll pour simuler un humain
                time.sleep(random.uniform(3, 6))
                page.mouse.wheel(0, 1000)
                time.sleep(2)

                # Sélecteur TRÈS large : on prend tous les liens qui contiennent "/fr/annonce/"
                hrefs = page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
                unique_links = list(set([h for h in hrefs if "/annonce/" in str(h) and "maison" in str(h) or "appartement" in str(h)]))
                
                print(f"📊 {len(unique_links)} liens trouvés après filtrage.")

                for link in unique_links[:10]: # On limite à 10 par zone pour tester
                    try:
                        print(f"   🔎 Analyse : {link.split('/')[-1][:20]}...")
                        page.goto(link, wait_until="domcontentloaded", timeout=60000)
                        time.sleep(random.uniform(2, 4))
                        
                        data = page.evaluate("window.classified")
                        if data:
                            prix = data.get("transaction", {}).get("sale", {}).get("price")
                            if not prix: continue
                            
                            type_b = data.get("property", {}).get("type", "UNKNOWN")
                            rc = data.get("transaction", {}).get("sale", {}).get("cadastralIncome")
                            cf, renta = calculer_metrics(prix, type_b, rc)
                            
                            item = {
                                "id": data.get("id"), "url": link, "prix": prix, "type": type_b,
                                "surface": data.get("property", {}).get("netHabitableSurface"),
                                "chambres": data.get("property", {}).get("bedroomCount"),
                                "zip": data.get("property", {}).get("location", {}).get("postalCode"),
                                "zone_filtre": zone['name'], "cf": cf, "renta": renta
                            }
                            save_to_db(item)
                            all_results.append(item)
                            print(f"      ✅ OK: {prix}€ (CF: {cf}€)")
                    except Exception as e:
                        print(f"      ⚠️ Erreur annonce: {e}")
                        continue

        browser.close()
        # Envoi de l'email seulement si on a trouvé quelque chose
        if all_results:
            corps = "\n".join([f"- {a['prix']}€ à {a['zip']} : {a['url']} (CF: {a['cf']}€)" for a in all_results])
            msg = MIMEText(f"Voici les nouvelles pépites :\n\n{corps}")
            msg['Subject'] = f"📈 {len(all_results)} Opportunités Immo"
            msg['From'], msg['To'] = EMAIL_SENDER, EMAIL_RECEIVER
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                s.login(EMAIL_SENDER, EMAIL_PASSWORD)
                s.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"🎯 FIN. {len(all_results)} en base.")

if __name__ == "__main__":
    run()
