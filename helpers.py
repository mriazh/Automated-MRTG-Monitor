"""
helpers.py — Fungsi utilitas untuk MRTG Live Monitor.
Berisi: konfigurasi, logging, NTP sync, Telegram alert,
        pembacaan graph title, Windows API, dan screenshot browser.
"""

import time
import os
import sys
import threading
import ctypes
import math
import logging
from datetime import datetime, timedelta
import ntplib
from dotenv import load_dotenv
import requests
import re
import base64
from logging.handlers import RotatingFileHandler

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ========================================================
#  KONFIGURASI & LOGGING
# ========================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('monitor.log', maxBytes=5*1024*1024, backupCount=3)
    ]
)
logger = logging.getLogger("mrtg_monitor")

def validate_url(url):
    """Ensure URL uses HTTPS for security."""
    if not url.startswith("https://"):
        logger.warning(f"URL tidak menggunakan HTTPS: {url}")
        raise ValueError("PORTAL_URL harus menggunakan HTTPS")
    return url

PORTAL_URL   = validate_url(os.getenv("PORTAL_URL", "https://portal-internal.domain.com/path/to/graph"))
MAX_GRAPHS       = int(os.getenv("MAX_GRAPHS", 12))
ESTIMASI_FETCH   = int(os.getenv("ESTIMASI_FETCH_SECONDS", 20))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
MONITOR_NAME       = os.getenv("MONITOR_NAME", "Unknown Laptop")

GRAPH_TITLE_FILE = "GRAPH-TITLE-MRTG.txt"
TEMP_FOLDER      = "temp_live_monitor"


# ========================================================
#  TELEGRAM ALERT
# ========================================================
def send_telegram_alert(message):
    """Kirim alert ke Telegram jika config tersedia."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram config kosong, skip alert.")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if data.get("ok"):
            logger.info("Telegram alert sent successfully.")
        else:
            logger.error(f"Telegram API error: {data.get('description', 'Unknown error')}")
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")


# ========================================================
#  REFRESH INTERVAL
# ========================================================
def hitung_refresh_interval(jumlah_grafik):
    """Hitung refresh interval (kelipatan 30 detik) berdasarkan jumlah grafik.
    Ditambah 20 detik spare untuk kemungkinan retry."""
    return math.ceil((jumlah_grafik * ESTIMASI_FETCH + 20) / 30) * 30


# ========================================================
#  WINDOWS API: SEMBUNYIKAN CHROME
# ========================================================
def cari_dan_hide_chrome(driver):
    """Cari dan sembunyikan SEMUA jendela Chrome yang terkait Selenium.
    Return list of HWND yang berhasil disembunyikan."""
    try:
        user32 = ctypes.windll.user32
        SW_HIDE = 0
        page_title = driver.title or ""
        hidden = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    # Cocokkan jendela Chrome: judul halaman ada di title,
                    # ATAU jendela Chrome yang menampilkan halaman monitoring_portal
                    if (page_title and page_title in title) or \
                       ("Chrome" in title and "monitoring_portal" in title.lower()) or \
                       ("Chrome" in title and "mrtg" in title.lower()):
                        user32.ShowWindow(hwnd, SW_HIDE)
                        hidden.append(hwnd)
            return True

        user32.EnumWindows(enum_cb, 0)
        return hidden
    except Exception as e:
        logger.warning(f"Gagal mencari HWND Chrome: {e}")
        return []


def hide_chrome_hwnds(hwnds):
    """Sembunyikan ulang semua jendela Chrome berdasarkan HWND yang tersimpan."""
    user32 = ctypes.windll.user32
    for hwnd in hwnds:
        try:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
        except Exception:
            pass


# ========================================================
#  NTP SYNC
# ========================================================
NTP_OFFSET = 0.0
_ntp_lock = threading.Lock()


def get_ntp_offset():
    """Mengambil selisih waktu sistem dengan waktu di NTP Server menggunakan ntplib."""
    ntp_servers = [
        'id.pool.ntp.org',     # Server Indonesia (prioritas)
        'pool.ntp.org',        # Server Global
        'time.google.com',     # Google (biasanya sangat stabil)
        'time.windows.com',    # Windows
        'time.cloudflare.com'  # Cloudflare
    ]

    client = ntplib.NTPClient()

    for server in ntp_servers:
        try:
            response = client.request(server, version=3, timeout=5)
            logger.info(f"Berhasil sync NTP dengan {server}")
            return response.offset
        except Exception as e:
            logger.warning(f"Gagal sync NTP dengan {server}: {e}")
            continue

    logger.error("Semua server NTP gagal dihubungi.")
    return 0.0


def get_now():
    """Mengembalikan datetime.now() yang sudah dikoreksi dengan NTP_OFFSET."""
    with _ntp_lock:
        offset = NTP_OFFSET
    return datetime.now() + timedelta(seconds=offset)


def sync_ntp_periodic():
    """Re-sync NTP setiap 1 jam untuk mencegah clock drift."""
    global NTP_OFFSET
    while True:
        time.sleep(3600)  # 1 jam
        old_offset = NTP_OFFSET
        new_offset = get_ntp_offset()
        if new_offset != 0.0:
            with _ntp_lock:
                NTP_OFFSET = new_offset
            if abs(new_offset - old_offset) > 0.5:
                logger.warning(f"NTP re-sync: offset berubah {old_offset:.2f}s -> {new_offset:.2f}s")


# ========================================================
#  BACA GRAPH TITLE DARI FILE
# ========================================================
def baca_graph_titles(filepath):
    """Membaca file konfigurasi untuk mendapatkan daftar graph title dan custom namanya."""
    MAX_FILE_SIZE = 1024 * 100  # 100KB
    if os.path.getsize(filepath) > MAX_FILE_SIZE:
        raise ValueError(f"File terlalu besar: {filepath}")
        
    titles = []
    title_mapping = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line.startswith("Graph-title : "):
                content = line.replace("Graph-title : ", "").strip()
                if "=>" in content:
                    graph_id, custom_name = content.split("=>", 1)
                    graph_id = graph_id.strip()
                    custom_name = custom_name.strip()
                else:
                    graph_id = content
                    custom_name = f"Graph-title : {graph_id}"

                if graph_id and graph_id not in title_mapping:
                    if not re.match(r'^[a-zA-Z0-9_\-\.\:]+$', graph_id):
                        logger.warning(f"Line {line_num}: Invalid graph_id '{graph_id}', skipping")
                        continue
                    titles.append(graph_id)
                    title_mapping[graph_id] = custom_name
    return titles, title_mapping


# ========================================================
#  AMBIL GAMBAR DARI BROWSER (HARI INI, 00:00 - SEKARANG)
# ========================================================
def ambil_gambar(driver, graph_title, tanggal_str, waktu_akhir_str):
    """
    Ambil screenshot grafik untuk graph_title dari 00:00 hingga waktu sekarang.
    Return path file PNG, atau None jika gagal.
    """
    waktu_awal = f"{tanggal_str} 00:00"
    waktu_akhir = f"{tanggal_str} {waktu_akhir_str}"
    out_path = os.path.join(TEMP_FOLDER, f"live_{graph_title}.png")

    try:
        # 1. Pastikan state bersih dengan ke URL utama
        try:
            driver.get(PORTAL_URL)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "graphtitle")))
        except Exception:
            pass

        # 2. Input graph title
        input_el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "graphtitle"))
        )
        
        # Eksekusi JS untuk memastikan value benar-benar ter-clear dan memicu event
        driver.execute_script("arguments[0].value = '';", input_el)
        input_el.send_keys(graph_title)
        time.sleep(0.5)
        input_el.send_keys(Keys.ENTER)
        
        # Tunggu hasil pencarian AJAX selesai (maksimal 5 detik buffer)
        time.sleep(3)
        
        # Cek apakah hasil pencarian kosong
        try:
            tbody = driver.find_element(By.TAG_NAME, "tbody")
            if "No matching records" in tbody.text or "No data available" in tbody.text:
                raise Exception(f"Grafik {graph_title} tidak ditemukan di database.")
        except Exception as e:
            if "tidak ditemukan" in str(e):
                raise e
        
        # 3. Klik tombol grafik (buka modal)
        tombol = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-graph"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tombol)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", tombol)

        # 3. Tunggu modal terbuka (tombol filter muncul)
        WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "graphfilter"))
        )

        # 4. Set rentang waktu
        driver.execute_script("document.getElementById('startdate').value = arguments[0];", waktu_awal)
        driver.execute_script("document.getElementById('enddate').value = arguments[0];", waktu_akhir)
        driver.execute_script("document.getElementById('startdate').dispatchEvent(new Event('change'));")
        driver.execute_script("document.getElementById('enddate').dispatchEvent(new Event('change'));")
        time.sleep(0.5)

        # 5. Klik Filter
        driver.execute_script("document.getElementById('graphfilter').click();")
        
        # Wajib tunggu 5 detik agar gambar selesai di-generate dan di-download dari server
        time.sleep(5)

        # 6. Scroll & cari gambar
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

        gambar_el = None
        for _ in range(20):
            try:
                elems = driver.find_elements(By.XPATH, "//img[contains(@src, 'graph.php')]")
                if elems and elems[0].is_displayed():
                    gambar_el = elems[0]
                    break
            except Exception:
                pass
            time.sleep(0.5)

        if not gambar_el:
            raise Exception("Elemen gambar tidak ditemukan")

        # Ekstrak gambar langsung dari render memori browser menggunakan Canvas API
        # Ini menghindari gambar terpotong (cropped) oleh viewport atau sticky header
        base64_str = driver.execute_script("""
            var img = arguments[0];
            if (!img.complete || img.naturalWidth === 0) {
                return 'NOT_LOADED';
            }
            var canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            return canvas.toDataURL('image/png').split(',')[1];
        """, gambar_el)
        
        if base64_str == 'NOT_LOADED':
            raise Exception("Gambar belum selesai dimuat oleh browser")

        os.makedirs(TEMP_FOLDER, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(base64_str))

        # 7. Tutup modal dengan force JS
        try:
            close_btn = driver.find_element(By.ID, "modalclose")
            driver.execute_script("arguments[0].click();", close_btn)
        except Exception:
            try:
                driver.execute_script("if(document.getElementById('graphfilter')) document.getElementById('graphfilter').closest('.modal').style.display='none';")
            except Exception:
                pass

        time.sleep(1)
        return out_path

    except Exception as e:
        logger.error(f"ambil_gambar({graph_title}): {e}")
        try:
            driver.get(PORTAL_URL) # Force reset jika error
        except Exception:
            pass
        return None
