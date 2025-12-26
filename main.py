import os, time, random, psycopg2, smtplib, re
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright

DB_URL = os.environ.get("DATABASE_URL")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = "dim.vandyck@gmail.com"

# --- CONFIGURATION DES LIENS (MODE RECHERCHE LISTE) ---
SEARCH_URLS = [
    {"name": "Maman", "url": "https://www.immoweb.be/fr/recherche/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=uwnrHed~Z%7BD%7B_C%7CKy~FuCwzDgNa%7BAhAexEe%5BojAacAfv@kBx@_%7C@%7Cy@%7CcEU_jAkF_qAb@kOpOe@vp@jOng@jAdv@kj@niE%7BRjsD?bcAbb@jsD%7CYrZjj@fSr%5Ere@l_AxXqAdHpy@yXz_@?nfAm@zf@dHpd@?xs@m%5Clq@kwA~t@c@&orderBy=relevance"},
    {"name": "Namur", "url": "https://www.immoweb.be/fr/recherche/maison-et-appartement/a-vendre?countries=BE&geoSearchAreas=ysurHiom%5Czh@m%7BAhQ%7CjAbLclG?ulCg%7B@ocI%7BWwAgyAi~BmwDiuA_eBuYmk@?ehAhp@%7DqDnkD%7Bq@xnCef@vfH?ddE%7Cq@~bFxu@tBv%7BAtlCj~AfsAlkBh@jqAAz{Aw%5BdnBgzBtvAcoAjMox@uNtY&orderBy=relevance"}
]

def run():
    with sync_playwright() as p:
        print("🚀 Démarrage du moteur de secours...")
        browser = p.chromium.launch(headless=True)
        # On simule un iPhone pour changer l'IP de détection
        context = browser.new_context(**p.devices["iPhone 13"])
        page = context.new_page()
        all_results = []

        for zone in SEARCH_URLS:
            print(f"\n🔎 Zone : {zone['name']}")
            try:
                # On tente d'accéder à la page
                page.goto(f"{zone['url']}&page=1", wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)
                
                # TECHNIQUE DE LA DERNIÈRE CHANCE : Extraire tous les liens par Regex
                content = page.content()
                links = re.findall(r'https://www.immoweb.be/fr/annonce/[^\s"\'<>]+/\d+', content)
                unique_links = list(set(links))
                
                print(f"📊 {len(unique_links)} annonces détectées dans le code source.")

                for link in unique_links[:5]: # Test sur les 5 premières
                    try:
                        print(f"   👉 Extraction : {link.split('/')[-1]}")
                        page.goto(link, wait_until="domcontentloaded", timeout=60000)
                        time.sleep(random.uniform(2, 4))
                        
                        data = page.evaluate("window.classified")
                        if data:
                            prix = data.get("transaction", {}).get("sale", {}).get("price")
                            item = {
                                "id": data.get("id"), "url": link, "prix": prix,
                                "type": data.get("property", {}).get("type"),
                                "zip": data.get("property", {}).get("location", {}).get("postalCode"),
                                "zone_filtre": zone['name'], "cf": 0, "renta": 0
                            }
                            all_results.append(item)
                            print(f"      ✅ Trouvé : {prix}€")
                    except: continue
            except Exception as e:
                print(f"❌ Erreur sur la zone : {e}")

        browser.close()
        print(f"🎯 Total capturé : {len(all_results)}")

if __name__ == "__main__":
    run()
