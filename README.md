# EconoDeal – Liquidations Walmart

Ce mini-projet propose :

1. Une interface web (`index.html`) qui affiche les liquidations et permet de filtrer par magasin, ville et rabais.
2. Un scraper Python (`scraper/walmart_liquidations.py`) qui va chercher les liquidations Walmart pour les magasins Saint-Jérôme et Blainville.
3. Un workflow GitHub Actions qui exécute le scraper automatiquement afin de garder `data/liquidations.json` à jour.

## Utilisation rapide

### 1. Installer les dépendances
```
pip install -r requirements.txt
```

### 2. Générer les données
```
python scraper/walmart_liquidations.py --output data/liquidations.json
```

En local (sans accès réseau) vous pouvez utiliser :
```
python scraper/walmart_liquidations.py --demo
```

### 3. Visualiser
Ouvrez `index.html` dans votre navigateur. Les cartes sont alimentées par `data/liquidations.json`.

## Workflow GitHub Actions

Le fichier `.github/workflows/scrape.yml` lance le scraper :

- à la demande (`workflow_dispatch`)
- tous les jours à 15h (heure du Québec, 20h UTC)

Le workflow :

1. installe Python
2. exécute `python scraper/walmart_liquidations.py`
3. commit automatiquement la sortie (`data/liquidations.json`)

Pour que le commit passe, laissez `GITHUB_TOKEN` avec les permissions par défaut (écriture sur le dépôt).

## Personnalisation

- Ajoutez des magasins dans `STORES` (fichier `scraper/walmart_liquidations.py`).
- Ajustez la requête envoyée à Walmart via `--query`.
- Changez la fréquence du workflow en adaptant la clé `cron`.

> ⚠️ Walmart applique parfois des limites réseau. Ajoutez un proxy, augmentez `--delay` ou utilisez `--max-pages 1` si besoin.
