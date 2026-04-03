from flask import Flask, render_template, request, jsonify, Response
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import hashlib
import threading

app = Flask(__name__)

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


def temizle_fiyat(metin):
    if not metin:
        return None
    metin = metin.replace(".", "").replace(",", ".").strip()
    sayilar = re.findall(r"[\d.]+", metin)
    return float(sayilar[0]) if sayilar else None


def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


def href_to_abs(href, base):
    if href and not href.startswith("http"):
        return base + href
    return href or ""


def urun_id(urun):
    key = urun.get("url") or (urun["site"] + urun["isim"])
    return hashlib.md5(key.encode()).hexdigest()


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


SCRAPER_MAP = {
    "direnc.net": ara_direnc,
    "robotistan.com": ara_robotistan,
    "robolinkmarket.com": ara_robolinkmarket,
    "motorobit.com": ara_motorobit,
}


def fav_yukle():
    if os.path.exists(FAV_DOSYA):
        try:
            with open(FAV_DOSYA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def fav_kaydet(data):
    with open(FAV_DOSYA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
        return Response(r.content, content_type=r.headers.get("Content-Type", "image/jpeg"))
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
    for t in threads: t.start()
    for t in threads: t.join()
    return jsonify(sonuclar)


@app.route("/api/favoriler", methods=["GET"])
def favoriler_listele():
    data = fav_yukle()
    return jsonify(list(data.values()))


@app.route("/api/favoriler", methods=["POST"])
def favori_ekle():
    urun = request.json
    data = fav_yukle()
    kid = urun_id(urun)
    data[kid] = {
        "site": urun["site"],
        "isim": urun["isim"],
        "fiyat_metin": urun.get("fiyat_metin", ""),
        "fiyat": urun.get("fiyat"),
        "url": urun.get("url", ""),
        "img_url": urun.get("img_url", ""),
    }
    fav_kaydet(data)
    return jsonify({"ok": True, "id": kid})


@app.route("/api/favoriler/<kid>", methods=["DELETE"])
def favori_cikar(kid):
    data = fav_yukle()
    data.pop(kid, None)
    fav_kaydet(data)
    return jsonify({"ok": True})


@app.route("/api/favoriler/kontrol", methods=["POST"])
def favori_kontrol():
    urun = request.json
    data = fav_yukle()
    kid = urun_id(urun)
    return jsonify({"favori": kid in data, "id": kid})


if __name__ == "__main__":
    app.run(debug=True)
