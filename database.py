import os
import psycopg2

def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS biens_vente (
        id SERIAL PRIMARY KEY,
        immoweb_id TEXT UNIQUE,
        type_bien TEXT,
        prix_achat INTEGER,
        surface INTEGER,
        chambres INTEGER,
        localisation TEXT,
        jardin BOOLEAN,
        revenu_cadastral INTEGER,
        date_premier_scrape DATE,
        date_dernier_update DATE,
        url TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS historiques_prix (
        id SERIAL PRIMARY KEY,
        bien_id INTEGER REFERENCES biens_vente(id),
        ancien_prix INTEGER,
        nouveau_prix INTEGER,
        date_changement DATE
    );
    """)

    conn.commit()
    cur.close()
    conn.close()
