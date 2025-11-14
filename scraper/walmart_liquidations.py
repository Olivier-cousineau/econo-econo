#!/usr/bin/env python3
"""Collecte les liquidations Walmart pour St-Jérôme et Blainville."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import pathlib
import sys
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

try:  # pragma: no cover - dépend de l'environnement
    import requests
except ModuleNotFoundError:  # pragma: no cover - permet --demo sans dépendances
    requests = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - uniquement pour le typage
    from requests import Session as RequestsSession
else:  # pragma: no cover
    RequestsSession = Any

LOGGER = logging.getLogger(__name__)
SEARCH_URL = "https://www.walmart.ca/api/seo/catalog/search"


@dataclass
class Store:
    """Représente une succursale Walmart."""

    slug: str
    name: str
    city: str
    postal_code: str
    store_id: str


STORES: List[Store] = [
    Store(
        slug="walmart-st-jerome",
        name="Walmart Saint-Jérôme Supercentre",
        city="Saint-Jérôme",
        postal_code="J7Y5K2",
        store_id="3126",
    ),
    Store(
        slug="walmart-blainville",
        name="Walmart Blainville Supercentre",
        city="Blainville",
        postal_code="J7C0M8",
        store_id="3125",
    ),
]

DEMO_ITEMS: List[Dict[str, Any]] = [
    {
        "sku": "6000191234567",
        "title": "Téléviseur TCL 55'' 4K",
        "store": "Walmart Saint-Jérôme Supercentre",
        "city": "Saint-Jérôme",
        "price": 398.0,
        "was": 598.0,
        "pct": 33,
        "url": "https://www.walmart.ca/ip/6000191234567",
        "image": "https://i5.walmartimages.ca/images/Enlarge/123/456/6000191234567.jpg",
        "availability": "IN_STOCK",
    },
    {
        "sku": "6000209876543",
        "title": "Compresseur Mastercraft 20V",
        "store": "Walmart Blainville Supercentre",
        "city": "Blainville",
        "price": 89.0,
        "was": 149.0,
        "pct": 40,
        "url": "https://www.walmart.ca/ip/6000209876543",
        "image": "https://i5.walmartimages.ca/images/Enlarge/987/654/6000209876543.jpg",
        "availability": "LOW_STOCK",
    },
]


def request_json(session: RequestsSession, store: Store, page: int, query: str) -> Dict[str, Any]:
    params = {
        "query": query,
        "page": page,
        "pageSize": 24,
        "storeId": store.store_id,
        "sort": "relevance",
        "enableStoreSelection": "true",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) EconodealBot/1.0",
        "Accept": "application/json",
        "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
        "Referer": "https://www.walmart.ca/",
    }
    LOGGER.debug("GET %s %s", SEARCH_URL, params)
    resp = session.get(SEARCH_URL, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_pct_off(price: Optional[float], was: Optional[float]) -> Optional[int]:
    if not price or not was or was <= 0:
        return None
    pct = round((1 - (price / was)) * 100)
    return max(0, pct)


def normalize_item(raw: Dict[str, Any], store: Store) -> Dict[str, Any]:
    price_info = raw.get("price", {}) or {}
    price = (
        to_float(price_info.get("price"))
        or to_float(price_info.get("current"))
        or to_float(price_info.get("priceInteger"))
        or to_float(raw.get("price"))
    )
    was = (
        to_float(price_info.get("wasPrice"))
        or to_float(price_info.get("listPrice"))
        or to_float(price_info.get("comparisonPrice"))
    )
    pct = compute_pct_off(price, was)
    url = raw.get("productUrl") or raw.get("canonicalUrl") or raw.get("productCanonicalUrl")
    image = None
    image_info = raw.get("imageInfo") or raw.get("image") or {}
    if isinstance(image_info, dict):
        image = image_info.get("thumbnail") or image_info.get("mainUrl")
    sku = raw.get("usItemId") or raw.get("productId") or raw.get("id")
    title = raw.get("name") or raw.get("displayName") or raw.get("title")
    availability = raw.get("availabilityStatus") or raw.get("availability")
    return {
        "sku": sku,
        "title": title,
        "store": store.name,
        "city": store.city,
        "price": price,
        "was": was,
        "pct": pct,
        "url": f"https://www.walmart.ca{url}" if url and url.startswith("/") else url,
        "image": image,
        "availability": availability,
    }


def scrape_store(store: Store, session: RequestsSession, *, query: str, max_pages: int, delay: float) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        data = request_json(session, store, page, query)
        items = data.get("items") or []
        if not items:
            LOGGER.info("%s: aucune donnée à la page %s", store.city, page)
            break
        for raw in items:
            normalized = normalize_item(raw, store)
            sku = normalized.get("sku")
            if not sku or sku in seen:
                continue
            seen.add(sku)
            results.append(normalized)
        LOGGER.info("%s: %s articles récupérés (page %s)", store.city, len(items), page)
        if len(items) < 24:
            break
        time.sleep(delay)
    return results


def run_scraper(query: str, max_pages: int, delay: float, store_slugs: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    picked = [store for store in STORES if not store_slugs or store.slug in store_slugs]
    if requests is None:
        raise RuntimeError("Le module 'requests' est requis pour lancer le scraper (pip install -r requirements.txt)")
    session = requests.Session()
    payload_items: List[Dict[str, Any]] = []
    for store in picked:
        try:
            payload_items.extend(scrape_store(store, session, query=query, max_pages=max_pages, delay=delay))
        except Exception as exc:  # pragma: no cover - log pour workflow
            LOGGER.error("Erreur durant la collecte pour %s: %s", store.slug, exc)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": "https://www.walmart.ca",
        "query": query,
        "stores": [asdict(store) for store in picked],
        "items": payload_items,
    }
    return payload


def write_output(payload: Dict[str, Any], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)
    LOGGER.info("Écriture terminée dans %s", path)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/liquidations.json", help="Chemin du fichier JSON à produire")
    parser.add_argument("--query", default="clearance", help="Terme envoyé à l'API Walmart")
    parser.add_argument("--max-pages", type=int, default=2, help="Nombre maximal de pages par magasin")
    parser.add_argument("--delay", type=float, default=1.5, help="Délai (s) entre chaque page")
    parser.add_argument(
        "--stores",
        nargs="*",
        default=None,
        help="Slugs des magasins à cibler (défaut: tous)",
    )
    parser.add_argument("--demo", action="store_true", help="Enregistrer les données de démonstration sans HTTP")
    parser.add_argument("--log-level", default="INFO", help="Niveau de log (INFO, DEBUG, ...)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    output_path = pathlib.Path(args.output)
    if args.demo:
        payload = {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": "demo",
            "query": "clearance",
            "stores": [asdict(store) for store in STORES],
            "items": DEMO_ITEMS,
        }
    else:
        payload = run_scraper(args.query, args.max_pages, args.delay, store_slugs=args.stores)
    write_output(payload, output_path)
    if not payload.get("items"):
        LOGGER.warning("Aucun article collecté – vérifiez les paramètres ou réessayez plus tard")
        return 2
    LOGGER.info("%s articles enregistrés", len(payload["items"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
