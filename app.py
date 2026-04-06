# app.py
from flask import Flask, render_template, request, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import hashlib
import threading
from datetime import datetime
from urllib.parse import urljoin

app = Flask(__name__, static_folder='static', template_folder='templates')

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 15
FAV_DOSYA = os.path.join(os.path.dirname(__file__), "favoriler.json")
FAV_LOCK = threading.Lock()


def temizle_fiyat(metin):
    if not metin:
        return None
    metin = metin.replace(".", "").replace(",", ".").strip()
    m = re.search(r"[\d\.]+", metin)
    try:
        return float(m.group(0)) if m else None
    except Exception:
        return None


def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


def href_to_abs(href, base):
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return base.rstrip("/") + "/" + href.lstrip("/")


def urun_key_from(urun):
    return urun.get("url") or (urun.get("site", "") + urun.get("isim", ""))


def urun_id_from_key(key):
    return hashlib.md5(key.encode()).hexdigest()


# --- Scrapers for each site (direnc, robotistan, robolinkmarket, motorobit, robocombo) ---

def ara_direnc(kelime):
    base = "https://www.direnc.net"
    url = f"{base}/arama?q={requests.utils.quote(kelime)}"
    soup = get_soup(url)
    if not soup:
        return []
    urunler = []
    for item in soup.select(".productItem"):
        isim_el = item.select_one("a.productDescription")
        isim = isim_el.get_text(strip=True) if isim_el else ""
        if not isim:
            continue
        fiyat_el = item.select_one(".currentPrice")
        fiyat_metin = fiyat_el.get_text(strip=True) if fiyat_el else ""
        href = href_to_abs(isim_el.get("href", "") if isim_el else "", base)
        img_el = item.select_one("img.lazy")
        img_url = (img_el.get("data-src") or img_el.get("src", "")) if img_el else ""
        urunler.append({"site": "direnc.net", "isim": isim,
                        "fiyat_metin": fiyat_metin, "fiyat": temizle_fiyat(fiyat_metin),
                        "url": href, "img_url": img_url})
    return urunler


def ara_robotistan(kelime):
    base = "https://www.robotistan.com"
    url = f"{base}/arama?q={requests.utils.quote(kelime)}"
    soup = get_soup(url)
    if not soup:
        return []
    urunler = []
    for item in soup.select(".product-item"):
        isim_el = item.select_one("a.product-title")
        isim = isim_el.get_text(strip=True) if isim_el else ""
        if not isim:
            continue
        fiyat_el = item.select_one("strong.product-price")
        fiyat_metin = (fiyat_el.get_text(strip=True) + " TL") if fiyat_el else ""
        href = href_to_abs(isim_el.get("href", "") if isim_el else "", base)
        img_el = item.select_one("img.lazyload")
        img_url = (img_el.get("data-src") or img_el.get("src", "")) if img_el else ""
        urunler.append({"site": "robotistan.com", "isim": isim,
                        "fiyat_metin": fiyat_metin, "fiyat": temizle_fiyat(fiyat_metin),
                        "url": href, "img_url": img_url})
    return urunler


def ara_robolinkmarket(kelime):
    base = "https://www.robolinkmarket.com"
    url = f"{base}/arama?q={requests.utils.quote(kelime)}"
    soup = get_soup(url)
    if not soup:
        return []
    urunler = []
    for item in soup.select(".product-item"):
        isim_el = item.select_one(".product-title a")
        isim = isim_el.get_text(strip=True) if isim_el else ""
        if not isim:
            continue
        fiyat_el = item.select_one(".yeni-fiyat")
        fiyat_metin = fiyat_el.get_text(strip=True) if fiyat_el else ""
        href = href_to_abs(isim_el.get("href", "") if isim_el else "", base)
        img_el = item.select_one("img.lazyload")
        img_url = (img_el.get("data-src") or "") if img_el else ""
        if not img_url:
            src_el = item.select_one("source")
            img_url = src_el.get("srcset", "") if src_el else ""
        urunler.append({"site": "robolinkmarket.com", "isim": isim,
                        "fiyat_metin": fiyat_metin, "fiyat": temizle_fiyat(fiyat_metin),
                        "url": href, "img_url": img_url})
    return urunler


def ara_motorobit(kelime):
    base = "https://www.motorobit.com"
    url = f"{base}/arama?q={requests.utils.quote(kelime)}"
    soup = get_soup(url)
    if not soup:
        return []
    urunler = []
    for item in soup.select("[data-toggle='product']"):
        link_el = item.select_one("a[data-toggle='product-url']")
        isim = (link_el.get("title") or link_el.get_text(strip=True)) if link_el else ""
        if not isim:
            continue
        fiyat_el = item.select_one(".text-primary.font-bold")
        fiyat_metin = ""
        if fiyat_el:
            raw = fiyat_el.get_text(separator=" ", strip=True)
            m = re.search(r"[\d\.,]+", raw)
            if m:
                fiyat_metin = m.group(0) + " TL"
        href = href_to_abs(link_el.get("href", "") if link_el else "", base)
        img_el = item.select_one("img[data-src], img[data-toggle='product-image']")
        img_url = (img_el.get("data-src") or img_el.get("src", "")) if img_el else ""
        urunler.append({"site": "motorobit.com", "isim": isim,
                        "fiyat_metin": fiyat_metin, "fiyat": temizle_fiyat(fiyat_metin),
                        "url": href, "img_url": img_url})
    return urunler


# --- Enhanced robocombo scraper (tries ld+json, inline state, discovered endpoints, fallback selectors) ---
def ara_robocombo(kelime):
    base = "https://www.robocombo.com"
    url = f"{base}/arama?q={requests.utils.quote(kelime)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    # 1) ld+json
    items = []
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            continue
        if isinstance(data, dict):
            data = [data]
        for d in data:
            if not isinstance(d, dict):
                continue
            if d.get("@type") in ("Product", "Offer") or "offers" in d:
                name = d.get("name") or d.get("headline") or ""
                offers = d.get("offers") or {}
                price = None
                price_text = ""
                if isinstance(offers, dict):
                    price = offers.get("price")
                    price_text = (offers.get("priceCurrency", "") + " " + str(price)).strip()
                image = d.get("image") or ""
                link = d.get("url") or ""
                items.append({"site": "robocombo.com", "isim": name,
                              "fiyat_metin": price_text, "fiyat": float(price) if price else None,
                              "url": link, "img_url": image})
    if items:
        return items

    # 2) inline global state
    scripts_text = "".join([s.string or "" for s in soup.select("script")])
    m = re.search(r'(window\.__INITIAL_STATE__|__INITIAL_STATE__|window\.__DATA__|__DATA__)\s*=\s*({.+?});', scripts_text, re.S)
    if m:
        js = m.group(2)
        try:
            data = json.loads(js)
        except Exception:
            try:
                js2 = re.sub(r'(\w+):', r'"\1":', js)
                data = json.loads(js2)
            except Exception:
                data = None
        if data:
            found = []
            def walk(o):
                if isinstance(o, dict):
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for el in o:
                        if isinstance(el, dict):
                            name = el.get("name") or el.get("title") or el.get("productName") or ""
                            price = el.get("price") or (el.get("offers", {}).get("price") if isinstance(el.get("offers"), dict) else None)
                            img = el.get("image") or el.get("img") or ""
                            link = el.get("url") or el.get("link") or ""
                            if name:
                                found.append({"site": "robocombo.com", "isim": name,
                                              "fiyat_metin": str(price) if price else "", "fiyat": float(price) if price else None,
                                              "url": urljoin(base, link) if link else "", "img_url": img})
                            else:
                                walk(el)
            walk(data)
            if found:
                return found

    # 3) discover API endpoints in scripts and try them
    endpoints = set()
    for mm in re.finditer(r'["\'](\/[a-zA-Z0-9_\-\/]*?(?:api|search|arama|products|product|catalog)[a-zA-Z0-9_\-\/]*?)["\']', r.text):
        endpoints.add(urljoin(base, mm.group(1)))
    for mm in re.finditer(r'["\'](https?:\/\/[^"\']*?(?:api|search|arama|products|product|catalog)[^"\']*)["\']', r.text):
        endpoints.add(mm.group(1))
    for ep in endpoints:
        try:
            rr = requests.get(ep, params={"q": kelime}, headers=HEADERS, timeout=8)
            if rr.status_code != 200:
                rr = requests.post(ep, json={"q": kelime}, headers=HEADERS, timeout=8)
            if rr.status_code == 200:
                try:
                    data = rr.json()
                except Exception:
                    data = None
                if isinstance(data, dict):
                    for key in ("items", "products", "data", "results", "hits"):
                        if key in data and isinstance(data[key], list):
                            found = []
                            for el in data[key]:
                                if not isinstance(el, dict):
                                    continue
                                name = el.get("name") or el.get("title") or el.get("productName") or ""
                                price = el.get("price") or (el.get("offers", {}).get("price") if isinstance(el.get("offers"), dict) else None)
                                img = el.get("image") or el.get("img") or ""
                                link = el.get("url") or el.get("link") or ""
                                if name:
                                    found.append({"site": "robocombo.com", "isim": name,
                                                  "fiyat_metin": str(price) if price else "", "fiyat": float(price) if price else None,
                                                  "url": urljoin(base, link) if link else "", "img_url": img})
                            if found:
                                return found
                elif isinstance(data, list):
                    found = []
                    for el in data:
                        if isinstance(el, dict):
                            name = el.get("name") or el.get("title") or ""
                            price = el.get("price")
                            img = el.get("image") or ""
                            link = el.get("url") or ""
                            if name:
                                found.append({"site": "robocombo.com", "isim": name,
                                              "fiyat_metin": str(price) if price else "", "fiyat": float(price) if price else None,
                                              "url": urljoin(base, link) if link else "", "img_url": img})
                    if found:
                        return found
        except Exception:
            continue

    # 4) fallback: HTML selectors
    fallback = []
    for item in soup.select(".product-item, .product, .productCard, .item, .product-list-item, .product-card"):
        isim_el = item.select_one("a.product-title, a.title, .product-title a, .title a, h2 a, h3 a, a")
        if not isim_el:
            continue
        isim = isim_el.get_text(strip=True)
        fiyat_el = item.select_one(".price, .product-price, .price-new, .price-current, .price-amount")
        fiyat_metin = fiyat_el.get_text(strip=True) if fiyat_el else ""
        href = isim_el.get("href") or ""
        img_el = item.select_one("img, .product-image img")
        img_url = (img_el.get("data-src") or img_el.get("src")) if img_el else ""
        fallback.append({"site": "robocombo.com", "isim": isim,
                         "fiyat_metin": fiyat_metin, "fiyat": None if not fiyat_metin else temizle_fiyat(fiyat_metin),
                         "url": urljoin(base, href), "img_url": img_url})
    return fallback


SCRAPER_MAP = {
    "direnc.net": ara_direnc,
    "robotistan.com": ara_robotistan,
    "robolinkmarket.com": ara_robolinkmarket,
    "motorobit.com": ara_motorobit,
    "robocombo.com": ara_robocombo,
}


# --- Favorites (device-based) storage helpers ---
def fav_yukle():
    if os.path.exists(FAV_DOSYA):
        try:
            with open(FAV_DOSYA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def fav_kaydet(data):
    with FAV_LOCK:
        with open(FAV_DOSYA, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/proxy/img")
def proxy_img():
    url = request.args.get("url", "")
    if not url.startswith("http"):
        return "", 400
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        content_type = r.headers.get("Content-Type", "image/jpeg")
        return Response(r.content, content_type=content_type)
    except Exception:
        return "", 404


@app.route("/api/ara")
def ara():
    kelime = request.args.get("q", "").strip()
    siteler = request.args.getlist("siteler")
    if not kelime:
        return jsonify({"error": "Arama kelimesi gerekli"}), 400
    if not siteler:
        siteler = list(SCRAPER_MAP.keys())
    sonuclar = []
    lock = threading.Lock()

    def calistir(site_adi):
        fn = SCRAPER_MAP.get(site_adi)
        if fn:
            try:
                res = fn(kelime)
            except Exception:
                res = []
            with lock:
                sonuclar.extend(res)

    threads = [threading.Thread(target=calistir, args=(s,), daemon=True) for s in siteler]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return jsonify(sonuclar)


# Favoriler: cihaz bazlı
@app.route("/api/favoriler", methods=["GET"])
def favoriler_listele():
    device_id = request.args.get("device_id", "").strip()
    if not device_id:
        return jsonify({"error": "device_id gerekli"}), 400
    data = fav_yukle()
    device_map = data.get(device_id, {})
    return jsonify(list(device_map.values()))


@app.route("/api/favoriler", methods=["POST"])
def favori_ekle():
    payload = request.json or {}
    device_id = payload.get("device_id") or request.args.get("device_id")
    if not device_id:
        return jsonify({"error": "device_id gerekli"}), 400
    urun = {
        "site": payload.get("site", ""),
        "isim": payload.get("isim", ""),
        "fiyat_metin": payload.get("fiyat_metin", ""),
        "fiyat": payload.get("fiyat"),
        "url": payload.get("url", ""),
        "img_url": payload.get("img_url", ""),
    }
    key = urun_key_from(urun)
    kid = urun_id_from_key(key)
    with FAV_LOCK:
        data = fav_yukle()
        device_map = data.setdefault(device_id, {})
        device_map[key] = {"id": kid, **urun}
        fav_kaydet(data)
    return jsonify({"ok": True, "id": kid, "key": key})


@app.route("/api/favoriler", methods=["DELETE"])
def favori_cikar():
    device_id = request.args.get("device_id", "").strip()
    key = request.args.get("key", "").strip()
    if not device_id or not key:
        return jsonify({"error": "device_id ve key gerekli"}), 400
    with FAV_LOCK:
        data = fav_yukle()
        device_map = data.get(device_id, {})
        if key in device_map:
            device_map.pop(key, None)
            data[device_id] = device_map
            fav_kaydet(data)
    return jsonify({"ok": True})


@app.route("/api/favoriler/kontrol", methods=["POST"])
def favori_kontrol():
    payload = request.json or {}
    device_id = payload.get("device_id")
    urun = payload.get("urun") or {}
    if not device_id:
        return jsonify({"error": "device_id gerekli"}), 400
    key = urun.get("url") or (urun.get("site", "") + urun.get("isim", ""))
    data = fav_yukle()
    device_map = data.get(device_id, {})
    exists = key in device_map
    return jsonify({"favori": exists, "key": key, "id": device_map.get(key, {}).get("id")})


@app.route("/sitemap.xml")
def sitemap():
    base_url = request.url_root.rstrip("/")
    urls = []
    urls.append({"loc": base_url + "/", "lastmod": datetime.utcnow().date().isoformat(), "changefreq": "daily", "priority": "1.0"})
    urls.append({"loc": base_url + "/?q=", "lastmod": datetime.utcnow().date().isoformat(), "changefreq": "weekly", "priority": "0.5"})
    favs = fav_yukle()
    for device_map in favs.values():
        for v in device_map.values():
            url = v.get("url")
            if url:
                if url.startswith("http"):
                    urls.append({"loc": url, "lastmod": datetime.utcnow().date().isoformat(), "changefreq": "monthly", "priority": "0.6"})
                else:
                    urls.append({"loc": base_url + url, "lastmod": datetime.utcnow().date().isoformat(), "changefreq": "monthly", "priority": "0.6"})
    xml_items = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml_items.append("  <url>")
        xml_items.append(f"    <loc>{u['loc']}</loc>")
        if u.get("lastmod"):
            xml_items.append(f"    <lastmod>{u['lastmod']}</lastmod>")
        if u.get("changefreq"):
            xml_items.append(f"    <changefreq>{u['changefreq']}</changefreq>")
        if u.get("priority"):
            xml_items.append(f"    <priority>{u['priority']}</priority>")
        xml_items.append("  </url>")
    xml_items.append("</urlset>")
    xml = "\n".join(xml_items)
    return Response(xml, content_type="application/xml")


if __name__ == "__main__":
    app.run(debug=True)
