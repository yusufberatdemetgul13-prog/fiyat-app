"""
Elektronik Ürün Fiyat Karşılaştırma — Trendyol tarzı kart UI
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
import re
import io

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

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
CARD_W = 210
CARD_H = 310
IMG_W, IMG_H = 180, 160
COLS = 5   # başlangıç sütun sayısı (pencere genişliğine göre değişir)

RENK = {
    "bg":        "#F3F3F3",
    "header":    "#FF6000",
    "card":      "#FFFFFF",
    "card_hov":  "#FFF5EE",
    "isim":      "#1D1D1D",
    "fiyat":     "#FF6000",
    "site":      "#888888",
    "badge_bg":  "#FF6000",
    "badge_fg":  "#FFFFFF",
    "en_ucuz":   "#00A650",
    "border":    "#E8E8E8",
    "input_bg":  "#FFFFFF",
    "btn_bg":    "#FF6000",
    "btn_fg":    "#FFFFFF",
    "text_gray": "#666666",
    "placeholder_bg": "#F0F0F0",
}

PLACEHOLDER_IMG: ImageTk.PhotoImage | None = None   # global placeholder


def _make_placeholder() -> ImageTk.PhotoImage:
    img = Image.new("RGB", (IMG_W, IMG_H), RENK["placeholder_bg"])
    draw = ImageDraw.Draw(img)
    draw.text((IMG_W // 2 - 20, IMG_H // 2 - 8), "Yükleniyor…",
              fill="#AAAAAA")
    return ImageTk.PhotoImage(img)


def temizle_fiyat(metin: str) -> float:
    if not metin:
        return float("inf")
    metin = metin.replace(".", "").replace(",", ".").strip()
    sayilar = re.findall(r"[\d.]+", metin)
    return float(sayilar[0]) if sayilar else float("inf")


def get_soup(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None


def indir_gorsel(url: str) -> ImageTk.PhotoImage | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img.thumbnail((IMG_W, IMG_H), Image.LANCZOS)
        # beyaz arkaplan üzerine ortala
        canvas = Image.new("RGB", (IMG_W, IMG_H), "white")
        ox = (IMG_W - img.width) // 2
        oy = (IMG_H - img.height) // 2
        canvas.paste(img, (ox, oy))
        return ImageTk.PhotoImage(canvas)
    except Exception:
        return None


def _href_to_abs(href: str, base: str) -> str:
    if href and not href.startswith("http"):
        return base + href
    return href or ""


# ---------------------------------------------------------------------------
# Scrapers
# ---------------------------------------------------------------------------

class DirencNetScraper:
    site_adi = "direnc.net"
    base_url = "https://www.direnc.net"

    def ara(self, kelime):
        url = f"{self.base_url}/arama?q={requests.utils.quote(kelime)}"
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
            href = _href_to_abs(isim_el.get("href", "") if isim_el else "", self.base_url)
            img_el = item.select_one("img.lazy")
            img_url = (img_el.get("data-src") or img_el.get("src", "")) if img_el else ""
            urunler.append({"site": self.site_adi, "isim": isim,
                            "fiyat_metin": fiyat_metin, "fiyat": temizle_fiyat(fiyat_metin),
                            "url": href, "img_url": img_url})
        return urunler


class RobotistanScraper:
    site_adi = "robotistan.com"
    base_url = "https://www.robotistan.com"

    def ara(self, kelime):
        url = f"{self.base_url}/arama?q={requests.utils.quote(kelime)}"
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
            href = _href_to_abs(isim_el.get("href", "") if isim_el else "", self.base_url)
            img_el = item.select_one("img.lazyload")
            img_url = (img_el.get("data-src") or img_el.get("src", "")) if img_el else ""
            urunler.append({"site": self.site_adi, "isim": isim,
                            "fiyat_metin": fiyat_metin, "fiyat": temizle_fiyat(fiyat_metin),
                            "url": href, "img_url": img_url})
        return urunler


class RobolinkMarketScraper:
    site_adi = "robolinkmarket.com"
    base_url = "https://www.robolinkmarket.com"

    def ara(self, kelime):
        url = f"{self.base_url}/arama?q={requests.utils.quote(kelime)}"
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
            href = _href_to_abs(isim_el.get("href", "") if isim_el else "", self.base_url)
            img_el = item.select_one("img.lazyload")
            img_url = (img_el.get("data-src") or "") if img_el else ""
            if not img_url:
                src_el = item.select_one("source")
                img_url = src_el.get("srcset", "") if src_el else ""
            urunler.append({"site": self.site_adi, "isim": isim,
                            "fiyat_metin": fiyat_metin, "fiyat": temizle_fiyat(fiyat_metin),
                            "url": href, "img_url": img_url})
        return urunler


class RobocomboScraper:
    site_adi = "robocombo.com"
    base_url = "https://www.robocombo.com"

    def ara(self, kelime):
        url = f"{self.base_url}/arama?q={requests.utils.quote(kelime)}"
        return [{"site": self.site_adi,
                 "isim": "Tarayıcıda ara: robocombo.com",
                 "fiyat_metin": "—", "fiyat": float("inf"),
                 "url": url, "img_url": ""}]


class MotorobitScraper:
    site_adi = "motorobit.com"
    base_url = "https://www.motorobit.com"

    def ara(self, kelime):
        url = f"{self.base_url}/arama?q={requests.utils.quote(kelime)}"
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
            href = _href_to_abs(link_el.get("href", "") if link_el else "", self.base_url)
            img_el = item.select_one("img[data-src], img[data-toggle='product-image']")
            img_url = (img_el.get("data-src") or img_el.get("src", "")) if img_el else ""
            urunler.append({"site": self.site_adi, "isim": isim,
                            "fiyat_metin": fiyat_metin, "fiyat": temizle_fiyat(fiyat_metin),
                            "url": href, "img_url": img_url})
        return urunler


SCRAPERS = [
    DirencNetScraper(),
    RobotistanScraper(),
    RobolinkMarketScraper(),
    RobocomboScraper(),
    MotorobitScraper(),
]

SITE_RENK = {
    "direnc.net":        "#E53935",
    "robotistan.com":    "#1976D2",
    "robolinkmarket.com":"#388E3C",
    "robocombo.com":     "#7B1FA2",
    "motorobit.com":     "#F57C00",
}

# ---------------------------------------------------------------------------
# Ürün Kartı Widget
# ---------------------------------------------------------------------------

class UrunKarti(tk.Frame):
    def __init__(self, parent, urun: dict, en_ucuz_fiyat: float, **kwargs):
        super().__init__(parent, bg=RENK["card"], bd=0,
                         highlightthickness=1,
                         highlightbackground=RENK["border"],
                         cursor="hand2", **kwargs)
        self.urun = urun
        self._build(en_ucuz_fiyat)
        self.bind("<Button-1>", self._ac)
        self.bind("<Enter>", self._hover_on)
        self.bind("<Leave>", self._hover_off)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._ac)
            child.bind("<Enter>", self._hover_on)
            child.bind("<Leave>", self._hover_off)

    def _build(self, en_ucuz_fiyat):
        global PLACEHOLDER_IMG
        if PLACEHOLDER_IMG is None:
            PLACEHOLDER_IMG = _make_placeholder()

        # --- Görsel ---
        self.img_label = tk.Label(self, image=PLACEHOLDER_IMG,
                                  bg=RENK["card"], width=IMG_W, height=IMG_H)
        self.img_label.pack(pady=(10, 4))
        self.img_label.bind("<Button-1>", self._ac)
        self.img_label.bind("<Enter>", self._hover_on)
        self.img_label.bind("<Leave>", self._hover_off)

        # --- Site badge ---
        site_renk = SITE_RENK.get(self.urun["site"], "#888")
        badge = tk.Label(self, text=self.urun["site"],
                         bg=site_renk, fg="white",
                         font=("Segoe UI", 7, "bold"),
                         padx=5, pady=1)
        badge.pack(anchor="w", padx=10)

        # --- İsim ---
        isim = self.urun["isim"]
        if len(isim) > 55:
            isim = isim[:52] + "…"
        tk.Label(self, text=isim, bg=RENK["card"], fg=RENK["isim"],
                 font=("Segoe UI", 9), wraplength=CARD_W - 20,
                 justify="left", anchor="w").pack(anchor="w", padx=10, pady=(4, 0))

        # --- Fiyat ---
        fiyat_frame = tk.Frame(self, bg=RENK["card"])
        fiyat_frame.pack(anchor="w", padx=10, pady=(4, 8), fill="x")

        renk_f = RENK["en_ucuz"] if self.urun["fiyat"] == en_ucuz_fiyat and self.urun["fiyat"] < float("inf") else RENK["fiyat"]
        fiyat_text = self.urun["fiyat_metin"] if self.urun["fiyat_metin"] != "-" else "—"

        tk.Label(fiyat_frame, text=fiyat_text, bg=RENK["card"],
                 fg=renk_f, font=("Segoe UI", 11, "bold")).pack(side="left")

        if self.urun["fiyat"] == en_ucuz_fiyat and self.urun["fiyat"] < float("inf"):
            tk.Label(fiyat_frame, text=" EN UCUZ", bg=RENK["en_ucuz"],
                     fg="white", font=("Segoe UI", 7, "bold"),
                     padx=3).pack(side="left", padx=(4, 0))

        # --- Görsel yükle (arka plan) ---
        if self.urun.get("img_url"):
            threading.Thread(target=self._yukle_gorsel,
                             args=(self.urun["img_url"],),
                             daemon=True).start()

    def _yukle_gorsel(self, url):
        photo = indir_gorsel(url)
        if photo:
            self._photo = photo  # GC'den koru
            try:
                self.img_label.config(image=photo)
            except Exception:
                pass

    def _ac(self, _=None):
        url = self.urun.get("url", "")
        if url.startswith("http"):
            webbrowser.open(url)

    def _hover_on(self, _=None):
        self.config(highlightbackground=RENK["fiyat"], highlightthickness=2)
        self.config(bg=RENK["card_hov"])

    def _hover_off(self, _=None):
        self.config(highlightbackground=RENK["border"], highlightthickness=1)
        self.config(bg=RENK["card"])


# ---------------------------------------------------------------------------
# Ana Uygulama
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⚡ Elektronik Fiyat Karşılaştırma")
        self.geometry("1200x780")
        self.minsize(800, 500)
        self.configure(bg=RENK["bg"])
        self._sonuclar: list[dict] = []
        self._site_vars: dict[str, tk.BooleanVar] = {}
        self._kart_widgetleri: list[UrunKarti] = []
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        # ========= HEADER =========
        hdr = tk.Frame(self, bg=RENK["header"], pady=0)
        hdr.pack(fill="x")

        logo = tk.Label(hdr, text="⚡ Fiyat Karşılaştırma",
                        font=("Segoe UI", 17, "bold"),
                        fg="white", bg=RENK["header"], pady=12, padx=16)
        logo.pack(side="left")

        # ========= ARAMA ÇUBUĞU =========
        arama_outer = tk.Frame(self, bg=RENK["header"], pady=0)
        arama_outer.pack(fill="x")

        arama_inner = tk.Frame(arama_outer, bg=RENK["header"], padx=16, pady=8)
        arama_inner.pack()

        self.arama_var = tk.StringVar()
        entry = tk.Entry(arama_inner, textvariable=self.arama_var,
                         font=("Segoe UI", 13),
                         bg=RENK["input_bg"], fg="#222",
                         insertbackground="#333",
                         relief="flat", width=42)
        entry.pack(side="left", ipady=8, padx=(0, 0))
        entry.bind("<Return>", lambda _: self._ara())

        ara_btn = tk.Button(arama_inner, text="  Ara  ",
                            command=self._ara,
                            bg="#CC4C00", fg="white",
                            font=("Segoe UI", 12, "bold"),
                            relief="flat", cursor="hand2",
                            activebackground="#AA3A00",
                            padx=10, pady=0)
        ara_btn.pack(side="left", ipady=8)

        # ========= FİLTRE ÇUBUĞU =========
        filtre_frame = tk.Frame(self, bg="#EFEFEF", pady=5, padx=16)
        filtre_frame.pack(fill="x")

        tk.Label(filtre_frame, text="Siteler:", fg="#444",
                 bg="#EFEFEF", font=("Segoe UI", 9, "bold")).pack(side="left")

        for s in SCRAPERS:
            var = tk.BooleanVar(value=True)
            self._site_vars[s.site_adi] = var
            renk = SITE_RENK.get(s.site_adi, "#888")
            cb = tk.Checkbutton(filtre_frame, text=s.site_adi,
                                variable=var, fg=renk,
                                bg="#EFEFEF", selectcolor="#EFEFEF",
                                activebackground="#EFEFEF",
                                font=("Segoe UI", 9, "bold"))
            cb.pack(side="left", padx=(6, 0))

        # Sırala
        tk.Label(filtre_frame, text="   Sırala:", fg="#444",
                 bg="#EFEFEF", font=("Segoe UI", 9)).pack(side="left")
        self.siralama_var = tk.StringVar(value="Fiyat (Artan)")
        sort_cb = ttk.Combobox(filtre_frame, textvariable=self.siralama_var,
                               values=["Fiyat (Artan)", "Fiyat (Azalan)", "Site"],
                               state="readonly", width=14)
        sort_cb.pack(side="left", padx=(4, 0))
        sort_cb.bind("<<ComboboxSelected>>", lambda _: self._goster(self._sonuclar))

        # Durum
        self.durum_var = tk.StringVar(value="Arama yapmak için ürün adı girin.")
        tk.Label(filtre_frame, textvariable=self.durum_var,
                 fg="#888", bg="#EFEFEF",
                 font=("Segoe UI", 9)).pack(side="right", padx=8)

        self.progress = ttk.Progressbar(filtre_frame, mode="indeterminate", length=120)

        # ========= KART ALANI =========
        container = tk.Frame(self, bg=RENK["bg"])
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg=RENK["bg"],
                                highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical",
                            command=self.canvas.yview)
        vsb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=vsb.set)

        self.kart_frame = tk.Frame(self.canvas, bg=RENK["bg"])
        self._frame_id = self.canvas.create_window((0, 0),
                                                   window=self.kart_frame,
                                                   anchor="nw")
        self.kart_frame.bind("<Configure>", self._on_kart_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    # ------------------------------------------------------------------
    def _on_kart_frame_configure(self, _):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._frame_id, width=event.width)
        if self._sonuclar:
            self._goster(self._sonuclar)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    def _ara(self):
        kelime = self.arama_var.get().strip()
        if not kelime:
            messagebox.showwarning("Uyarı", "Lütfen bir ürün adı girin.")
            return
        secili = [s for s in SCRAPERS if self._site_vars[s.site_adi].get()]
        if not secili:
            messagebox.showwarning("Uyarı", "En az bir site seçin.")
            return

        self._temizle_kartlar()
        self.progress.pack(side="right", padx=8)
        self.progress.start(12)
        self.durum_var.set(f"'{kelime}' aranıyor…")
        self._sonuclar = []

        def calis():
            lock = threading.Lock()
            threads = []
            for scraper in secili:
                t = threading.Thread(target=self._calistir,
                                     args=(scraper, kelime, lock),
                                     daemon=True)
                threads.append(t)
                t.start()
            for t in threads:
                t.join()
            self.after(0, self._arama_bitti)

        threading.Thread(target=calis, daemon=True).start()

    def _calistir(self, scraper, kelime, lock):
        try:
            sonuclar = scraper.ara(kelime)
        except Exception:
            sonuclar = []
        with lock:
            self._sonuclar.extend(sonuclar)

    def _arama_bitti(self):
        self.progress.stop()
        self.progress.pack_forget()
        gercek = [r for r in self._sonuclar if r["fiyat"] < float("inf")]
        self.durum_var.set(
            f"{len(gercek)} ürün bulundu — {len(self._sonuclar)} toplam sonuç"
        )
        self._goster(self._sonuclar)

    # ------------------------------------------------------------------
    def _temizle_kartlar(self):
        for w in self._kart_widgetleri:
            w.destroy()
        self._kart_widgetleri.clear()

    def _goster(self, sonuclar: list[dict]):
        self._temizle_kartlar()
        if not sonuclar:
            return

        siralama = self.siralama_var.get()
        if siralama == "Fiyat (Artan)":
            sirali = sorted(sonuclar, key=lambda r: r["fiyat"])
        elif siralama == "Fiyat (Azalan)":
            sirali = sorted(sonuclar, key=lambda r: r["fiyat"]
                            if r["fiyat"] < float("inf") else -1, reverse=True)
        else:
            sirali = sorted(sonuclar, key=lambda r: r["site"])

        gecerli = [r["fiyat"] for r in sirali if r["fiyat"] < float("inf")]
        en_ucuz = min(gecerli) if gecerli else float("inf")

        # Sütun sayısını hesapla
        canvas_w = self.canvas.winfo_width() or 1100
        cols = max(1, canvas_w // (CARD_W + 16))

        for idx, urun in enumerate(sirali):
            row = idx // cols
            col = idx % cols
            kart = UrunKarti(self.kart_frame, urun, en_ucuz,
                             width=CARD_W, height=CARD_H)
            kart.grid(row=row, column=col, padx=8, pady=8, sticky="n")
            self._kart_widgetleri.append(kart)

        self.canvas.yview_moveto(0)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = App()
    app.mainloop()
