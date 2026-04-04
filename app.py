from flask import Flask, render_template, request, jsonify, Response
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import hashlib
import threading

app = Flask(__name__)
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
ANON_USER_KEY = "anon"


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


def kullanici_anahtari():
    return ANON_USER_KEY


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

    # Eski düz { id: ürün } dosyası
    if isinstance(raw, dict) and raw and "v" not in raw:
        ilk = next(iter(raw.values()), None)
        if isinstance(ilk, dict) and "site" in ilk:
            by_site = _bos_siteler()
            for kid, p in raw.items():
                site = p.get("site")
                if site not in by_site:
                    by_site[site] = {}
                by_site[site][kid] = p
            return {
                "v": 2,
                "users": {ANON_USER_KEY: {"profile": None, "by_site": by_site}},
            }
    return {"v": 2, "users": {}}


def fav_db_kaydet(db):
    with open(FAV_DOSYA, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


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


def ara_robocombo(kelime):
    if not kelime or not kelime.strip():
        return []
    base = "https://www.robocombo.com"
    filter_obj = {
        "CategoryIdList": [],
        "BrandIdList": [],
        "SupplierIdList": [],
        "TagIdList": [],
        "TagId": -1,
        "FilterObject": [],
        "MinStockAmount": -1,
        "IsShowcaseProduct": -1,
        "IsOpportunityProduct": -1,
        "FastShipping": -1,
        "IsNewProduct": -1,
        "IsDiscountedProduct": -1,
        "IsShippingFree": -1,
        "IsProductCombine": -1,
        "MinPrice": 0,
        "MaxPrice": 0,
        "Point": -1,
        "SearchKeyword": "",
        "StrProductIds": "",
        "IsSimilarProduct": False,
        "RelatedProductId": 0,
        "ProductKeyword": kelime.strip(),
        "PageContentId": 0,
        "StrProductIDNotEqual": "",
        "IsVariantList": -1,
        "IsVideoProduct": -1,
        "ShowBlokVideo": -1,
        "VideoSetting": {"ShowProductVideo": 0, "AutoPlayVideo": -1},
        "ShowList": 1,
        "VisibleImageCount": 0,
        "ShowCounterProduct": -1,
        "ImageSliderActive": False,
        "ProductListPageId": 0,
        "ShowGiftHintActive": False,
        "IsInStock": False,
        "IsPriceRequest": True,
    }
    paging = {
        "PageItemCount": 48,
        "PageNumber": 1,
        "OrderBy": "KATEGORISIRA",
        "OrderDirection": "ASC",
    }
    params = {
        "FilterJson": json.dumps(filter_obj, ensure_ascii=False),
        "PagingJson": json.dumps(paging, ensure_ascii=False),
        "CreateFilter": "false",
        "PageType": "10",
        "PageId": "0",
    }
    try:
        r = requests.get(
            f"{base}/api/product/GetProductList",
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    if not isinstance(data, dict) or data.get("isError"):
        return []
    urunler = []
    for p in data.get("products") or []:
        if p.get("isBanner"):
            continue
        isim = (p.get("name") or "").strip()
        if not isim:
            continue
        path = p.get("defaultUrl") or p.get("url") or ""
        href = href_to_abs(path, base) if path else ""
        img_url = p.get("imageThumbPath") or ""
        fiyat_metin = (p.get("productCartPriceStr") or p.get("productSellPriceStr") or "").strip()
        fiyat = p.get("productCartPrice")
        if fiyat is None and fiyat_metin:
            fiyat = temizle_fiyat(fiyat_metin)
        elif fiyat is not None:
            try:
                fiyat = float(fiyat)
            except (TypeError, ValueError):
                fiyat = temizle_fiyat(fiyat_metin)
        urunler.append({
            "site": "robocombo.com",
            "isim": isim,
            "fiyat_metin": fiyat_metin,
            "fiyat": fiyat,
            "url": href,
            "img_url": img_url,
        })
    return urunler


SCRAPER_MAP = {
    "direnc.net": ara_direnc,
    "robotistan.com": ara_robotistan,
    "robolinkmarket.com": ara_robolinkmarket,
    "motorobit.com": ara_motorobit,
    "robocombo.com": ara_robocombo,
}


@app.route("/")
def index():
    return render_template("index.html", site_keys=list(SCRAPER_MAP.keys()))


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
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for u in sonuclar:
        u["id"] = urun_id(u)
    return jsonify(sonuclar)


@app.route("/api/favoriler", methods=["GET"])
def favoriler_listele():
    db = fav_db_yukle()
    uk = kullanici_anahtari()
    bucket = kullanici_bucket_al(db, uk)
    out = {}
    counts = {}
    total = 0
    for site in SCRAPER_MAP:
        d = bucket["by_site"].get(site, {})
        lst = []
        for kid, p in d.items():
            item = dict(p)
            item["id"] = kid
            lst.append(item)
        out[site] = lst
        counts[site] = len(lst)
        total += len(lst)
    return jsonify({"by_site": out, "counts": counts, "total": total})


@app.route("/api/favoriler", methods=["POST"])
def favori_ekle():
    urun = request.json
    if not urun or not urun.get("site"):
        return jsonify({"error": "Geçersiz ürün"}), 400
    site = urun["site"]
    if site not in SCRAPER_MAP:
        return jsonify({"error": "Bilinmeyen site"}), 400
    kid = urun.get("id") or urun_id(urun)
    db = fav_db_yukle()
    uk = kullanici_anahtari()
    bucket = kullanici_bucket_al(db, uk)
    kayit = {
        "site": urun["site"],
        "isim": urun["isim"],
        "fiyat_metin": urun.get("fiyat_metin", ""),
        "fiyat": urun.get("fiyat"),
        "url": urun.get("url", ""),
        "img_url": urun.get("img_url", ""),
    }
    bucket["by_site"][site][kid] = kayit
    fav_db_kaydet(db)
    return jsonify({"ok": True, "id": kid})


@app.route("/api/favoriler/<kid>", methods=["DELETE"])
def favori_cikar(kid):
    db = fav_db_yukle()
    uk = kullanici_anahtari()
    bucket = kullanici_bucket_al(db, uk)
    for site in bucket["by_site"]:
        if kid in bucket["by_site"][site]:
            del bucket["by_site"][site][kid]
            fav_db_kaydet(db)
            return jsonify({"ok": True})
    return jsonify({"ok": False}), 404


@app.route("/api/favoriler/kontrol", methods=["POST"])
def favori_kontrol():
    urun = request.json or {}
    kid = urun.get("id") or urun_id(urun)
    site = urun.get("site")
    db = fav_db_yukle()
    uk = kullanici_anahtari()
    bucket = kullanici_bucket_al(db, uk)
    fav = False
    if site and site in bucket["by_site"]:
        fav = kid in bucket["by_site"][site]
    else:
        for s in bucket["by_site"]:
            if kid in bucket["by_site"][s]:
                fav = True
                break
    return jsonify({"favori": fav, "id": kid})


if __name__ == "__main__":
    app.run(debug=True)
