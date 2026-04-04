from flask import Flask, render_template, request, jsonify, Response, session
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import hashlib
import threading
import secrets
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

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

SCRAPER_MAP = {}  # SCRAPER_MAP'i aşağıda tanımlayacağız

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Oturum gerekli"}), 401
        return f(*args, **kwargs)
    return decorated_function

def kullanici_anahtari():
    user_id = session.get("user_id")
    if not user_id:
        user_id = hashlib.md5(secrets.token_bytes(16)).hexdigest()[:16]
        session["user_id"] = user_id
        session.permanent = True
    return user_id

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
    return hashlib.md5(key.encode("utf-8")).hexdigest()

def _bos_siteler():
    return {s: {} for s in SCRAPER_MAP.keys()}

def fav_db_yukle():
    if not os.path.exists(FAV_DOSYA):
        return {"v": 2, "users": {}}
    try:
        with open(FAV_DOSYA, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {"v": 2, "users": {}}

    if isinstance(raw, dict) and raw.get("v") == 2:
        return raw

    return {"v": 2, "users": {}}

def fav_db_kaydet(db):
    try:
        with open(FAV_DOSYA, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def kullanici_bucket_al(db, user_key):
    if user_key not in db["users"]:
        db["users"][user_key] = {"profile": None, "by_site": _bos_siteler()}
    u = db["users"][user_key]
    if "by_site" not in u or not isinstance(u["by_site"], dict):
        u["by_site"] = _bos_siteler()
    for s in SCRAPER_MAP:
        if s not in u["by_site"]:
            u["by_site"][s] = {}
    return u

# SCRAPER FONKSİYONLARI
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

def ara_robocombo(kelime):
    if not kelime or not kelime.strip():
        return []
    base = "https://www.robocombo.com"
    filter_obj = {
        "CategoryIdList": [], "BrandIdList": [], "SupplierIdList": [],
        "TagIdList": [], "TagId": -1, "FilterObject": [], "MinStockAmount": -1,
        "IsShowcaseProduct": -1, "IsOpportunityProduct": -1, "FastShipping": -1,
        "IsNewProduct": -1, "IsDiscountedProduct": -1, "IsShippingFree": -1,
        "IsProductCombine": -1, "MinPrice": 0, "MaxPrice": 0, "Point": -1,
        "SearchKeyword": "", "StrProductIds": "", "IsSimilarProduct": False,
        "RelatedProductId":
