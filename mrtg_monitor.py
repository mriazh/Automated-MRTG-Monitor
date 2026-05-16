"""
mrtg_monitor.py — MRTG Live Monitor Entry Point.
Berisi: GUI (LiveMonitorApp) menggunakan PySide6 dan fungsi main().
"""

import sys
import os
import time
import math
import winsound
import threading
import subprocess

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QProgressBar, QPushButton, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap, QFont

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from helpers import (
    logger, PORTAL_URL, MAX_GRAPHS, MONITOR_NAME,
    GRAPH_TITLE_FILE,
    send_telegram_alert, hitung_refresh_interval,
    cari_dan_hide_chrome, hide_chrome_hwnds,
    get_ntp_offset, get_now, sync_ntp_periodic,
    baca_graph_titles, ambil_gambar,
)
import helpers

# ========================================================
#  STYLE SHEETS (DARK / LIGHT MODE)
# ========================================================
# ========================================================
#  STYLE SHEETS (DARK / LIGHT MODE)
# ========================================================
DARK_STYLE = """
QMainWindow {
    background-color: #0f172a;
}
QLabel {
    color: #f8fafc;
}
#Header {
    background-color: #1e293b;
    border-bottom: 2px solid #334155;
}
#HeaderTitle {
    color: #4ade80;
    font-weight: bold;
    font-size: 20px;
}
#HeaderTime, #HeaderStatus {
    color: #cbd5e1;
}
#GridContainer {
    background-color: #0f172a;
}
GraphFrame {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
}
GraphTitleBar {
    background-color: #334155;
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
    border-bottom: 1px solid #475569;
}
GraphTitleText {
    color: #4ade80;
    font-weight: bold;
}
GraphUpdateText {
    color: #94a3b8;
    font-size: 11px;
}
GraphImage {
    background-color: #1e293b;
    border-bottom-left-radius: 11px;
    border-bottom-right-radius: 11px;
}
#Footer {
    background-color: #1e293b;
    border-top: 2px solid #334155;
}
QProgressBar {
    border: 1px solid #475569;
    border-radius: 5px;
    background-color: #0f172a;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #4ade80;
    border-radius: 4px;
}
QPushButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #475569;
}
"""

LIGHT_STYLE = """
QMainWindow {
    background-color: #e2e8f0;
}
QLabel {
    color: #0f172a;
}
#Header {
    background-color: #ffffff;
    border-bottom: 2px solid #cbd5e1;
}
#HeaderTitle {
    color: #16a34a;
    font-weight: bold;
    font-size: 20px;
}
#HeaderTime, #HeaderStatus {
    color: #475569;
}
#GridContainer {
    background-color: #e2e8f0;
}
GraphFrame {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
}
GraphTitleBar {
    background-color: #f1f5f9;
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
    border-bottom: 1px solid #e2e8f0;
}
GraphTitleText {
    color: #16a34a;
    font-weight: bold;
}
GraphUpdateText {
    color: #64748b;
    font-size: 11px;
}
GraphImage {
    background-color: #ffffff;
    border-bottom-left-radius: 11px;
    border-bottom-right-radius: 11px;
}
#Footer {
    background-color: #ffffff;
    border-top: 2px solid #cbd5e1;
}
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    background-color: #e2e8f0;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #16a34a;
    border-radius: 4px;
}
QPushButton {
    background-color: #f8fafc;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #f1f5f9;
}
"""


# ========================================================
#  WORKER THREAD (BACKGROUND REFRESH)
# ========================================================
class RefreshWorker(QThread):
    status_signal = Signal(str, str)         # text, color(hex)
    progress_signal = Signal(int, str)       # current_idx, title
    image_ready_signal = Signal(int, str)    # idx, image_path
    image_failed_signal = Signal(int, str)   # idx, error_reason
    crash_signal = Signal()
    finished_signal = Signal()

    def __init__(self, driver, titles, chrome_hwnds):
        super().__init__()
        self.driver = driver
        self.titles = titles
        self.chrome_hwnds = chrome_hwnds
        self.running = True

    def _is_browser_alive(self):
        try:
            _ = self.driver.title
            return True
        except Exception:
            return False

    def stop(self):
        self.running = False

    def run(self):
        try:
            if not self._is_browser_alive():
                self.crash_signal.emit()
                return

            now = get_now()
            tgl_str = now.strftime("%d/%m/%Y")
            jam_str = now.strftime("%H:%M")
            self.status_signal.emit(f"Refreshing... ({jam_str})", "#ffcc44")

            hide_chrome_hwnds(self.chrome_hwnds)

            for i, title in enumerate(self.titles):
                if not self.running:
                    break
                
                self.progress_signal.emit(i + 1, title)
                path = ambil_gambar(self.driver, title, tgl_str, jam_str)

                # Jika gagal, cek dulu apakah browser masih hidup
                if not (path and os.path.exists(path)):
                    if not self._is_browser_alive():
                        self.crash_signal.emit()
                        return
                    
                    self.status_signal.emit(f"Retry {i+1}/{len(self.titles)}: {title}...", "#ff6644")
                    try:
                        self.driver.get(PORTAL_URL)
                        time.sleep(3)
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.NAME, "graphtitle"))
                        )
                    except Exception:
                        if not self._is_browser_alive():
                            self.crash_signal.emit()
                            return
                        continue

                    path = ambil_gambar(self.driver, title, tgl_str, jam_str)

                # Hasil akhir
                if path and os.path.exists(path):
                    self.image_ready_signal.emit(i, path)
                else:
                    logger.warning(f"Gagal refresh gambar {title}")
                    self.image_failed_signal.emit(i, f"Failed: {jam_str}")

                # Reset halaman (kecuali title terakhir)
                if i < len(self.titles) - 1:
                    try:
                        self.driver.get(PORTAL_URL)
                        time.sleep(3)
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.NAME, "graphtitle"))
                        )
                    except Exception:
                        if not self._is_browser_alive():
                            self.crash_signal.emit()
                            return

            self.status_signal.emit("OK — waiting for next refresh cycle", "")
        finally:
            self.finished_signal.emit()


# ========================================================
#  UI COMPONENT SUBCLASSES (Untuk QSS)
# ========================================================
class GraphFrame(QFrame): pass
class GraphTitleBar(QFrame): pass
class GraphTitleText(QLabel): pass
class GraphUpdateText(QLabel): pass
class GraphImage(QLabel): pass

# ========================================================
#  GUI — LIVE MONITOR (PYSIDE6)
# ========================================================
class LiveMonitorApp(QMainWindow):
    def __init__(self, titles, title_mapping, driver, chrome_hwnds=None):
        super().__init__()
        self.titles = titles
        self.title_display = title_mapping
        self.driver = driver
        self.chrome_hwnds = chrome_hwnds or []
        self.refresh_interval = hitung_refresh_interval(len(self.titles))
        self.is_dark_mode = True
        
        n = len(self.titles)
        self.grid_cols = math.ceil(math.sqrt(n))
        self.grid_rows = math.ceil(n / self.grid_cols)

        self.worker = None
        self.elapsed_time = 0
        self.is_refreshing = False
        
        # Simpan path gambar terakhir untuk fitur re-render saat ganti tema
        self.current_image_paths = [None] * len(self.titles)
        
        self._setup_ui()
        self.set_dark_mode(True)
        
        # Timer untuk jam header
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

        # Timer untuk progress bar & countdown
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._update_progress)
        self.refresh_timer.start(1000)

        # Mulai siklus refresh pertama
        QTimer.singleShot(500, self._trigger_refresh)

    def _setup_ui(self):
        self.setWindowTitle("MRTG Live Monitor")
        self.showFullScreen()
        
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- HEADER ---
        header = QFrame(self)
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)

        self.lbl_title = QLabel("◉ MRTG LIVE MONITOR", header)
        self.lbl_title.setObjectName("HeaderTitle")
        self.lbl_title.setFont(QFont("Consolas", 14, QFont.Bold))
        header_layout.addWidget(self.lbl_title)
        
        header_layout.addStretch()

        self.lbl_status = QLabel("Initializing...", header)
        self.lbl_status.setObjectName("HeaderStatus")
        self.lbl_status.setFont(QFont("Consolas", 11))
        header_layout.addWidget(self.lbl_status)
        
        header_layout.addSpacing(20)

        self.lbl_time = QLabel("", header)
        self.lbl_time.setObjectName("HeaderTime")
        self.lbl_time.setFont(QFont("Consolas", 12))
        header_layout.addWidget(self.lbl_time)
        
        header_layout.addSpacing(20)

        self.btn_theme = QPushButton("🌙 Dark Mode", header)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.btn_theme.setFont(QFont("Segoe UI", 10))
        header_layout.addWidget(self.btn_theme)

        main_layout.addWidget(header)

        # --- GRID CONTAINER ---
        grid_container = QWidget(self)
        grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setContentsMargins(15, 15, 15, 15)
        self.grid_layout.setSpacing(15)
        
        self.img_labels = []
        self.update_labels = []

        # Paksa grid agar proporsional secara merata
        for c in range(self.grid_cols):
            self.grid_layout.setColumnStretch(c, 1)
        for r in range(self.grid_rows):
            self.grid_layout.setRowStretch(r, 1)

        # Font adaptif (berdasarkan jumlah grafik)
        n = len(self.titles)
        font_size = 13 if n <= 4 else 11 if n <= 6 else 10 if n <= 9 else 9

        for i, title in enumerate(self.titles):
            row = i // self.grid_cols
            col = i % self.grid_cols

            frame = GraphFrame(grid_container)
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            frame_layout.setSpacing(0)

            title_bar = GraphTitleBar(frame)
            title_bar_layout = QHBoxLayout(title_bar)
            title_bar_layout.setContentsMargins(15, 8, 15, 8)

            display_text = self.title_display.get(title, f"Graph-title : {title}")
            lbl_g_title = GraphTitleText(display_text, title_bar)
            lbl_g_title.setFont(QFont("Consolas", font_size, QFont.Bold))
            title_bar_layout.addWidget(lbl_g_title)

            title_bar_layout.addStretch()

            lbl_g_update = GraphUpdateText("", title_bar)
            lbl_g_update.setFont(QFont("Consolas", 10))
            title_bar_layout.addWidget(lbl_g_update)
            self.update_labels.append(lbl_g_update)

            frame_layout.addWidget(title_bar)

            lbl_img = GraphImage("Loading...", frame)
            lbl_img.setAlignment(Qt.AlignCenter)
            lbl_img.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            frame_layout.addWidget(lbl_img, 1) # Stretch factor 1
            self.img_labels.append(lbl_img)

            self.grid_layout.addWidget(frame, row, col)

        main_layout.addWidget(grid_container, 1)

        # --- FOOTER ---
        footer = QFrame(self)
        footer.setObjectName("Footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)

        self.progress_bar = QProgressBar(footer)
        self.progress_bar.setRange(0, self.refresh_interval)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        footer_layout.addWidget(self.progress_bar, 1) # Stretch 1

        footer_layout.addSpacing(15)

        self.lbl_countdown = QLabel(f"Next refresh in {self.refresh_interval}s", footer)
        self.lbl_countdown.setFont(QFont("Consolas", 10))
        footer_layout.addWidget(self.lbl_countdown)
        
        footer_layout.addSpacing(25)
        
        lbl_hint = QLabel("[ESC] Exit  |  [SPACE] Refresh Now", footer)
        lbl_hint.setFont(QFont("Consolas", 9))
        footer_layout.addWidget(lbl_hint)

        main_layout.addWidget(footer)

    def set_dark_mode(self, enabled):
        self.is_dark_mode = enabled
        if enabled:
            self.setStyleSheet(DARK_STYLE)
            self.btn_theme.setText("☀️ Light Mode")
        else:
            self.setStyleSheet(LIGHT_STYLE)
            self.btn_theme.setText("🌙 Dark Mode")

    def toggle_theme(self):
        self.set_dark_mode(not self.is_dark_mode)
        # Re-render gambar agar efek invert/normal ter-apply
        for idx, path in enumerate(self.current_image_paths):
            if path and os.path.exists(path):
                self._on_image_ready(idx, path)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Space:
            self._trigger_refresh()
        elif event.key() == Qt.Key_Slash:
            self.toggle_theme()

    def _update_clock(self):
        now = get_now()
        self.lbl_time.setText(now.strftime("%A, %d %B %Y  |  %H:%M:%S"))

    def _update_progress(self):
        self.elapsed_time += 1
        remaining = max(0, self.refresh_interval - self.elapsed_time)
        
        self.progress_bar.setValue(self.elapsed_time)
        self.lbl_countdown.setText(f"Next refresh in {remaining}s")
        
        # Trigger refresh jika waktu habis DAN sedang tidak refreshing
        if self.elapsed_time >= self.refresh_interval and not self.is_refreshing:
            self._trigger_refresh()

    def _trigger_refresh(self):
        if self.is_refreshing:
            return
            
        self.is_refreshing = True
        self.elapsed_time = 0
        self.progress_bar.setValue(0)
        self.lbl_countdown.setText(f"Next refresh in {self.refresh_interval}s")

        self.worker = RefreshWorker(self.driver, self.titles, self.chrome_hwnds)
        self.worker.status_signal.connect(self._on_status_update)
        self.worker.progress_signal.connect(self._on_progress_update)
        self.worker.image_ready_signal.connect(self._on_image_ready)
        self.worker.image_failed_signal.connect(self._on_image_failed)
        self.worker.crash_signal.connect(self._on_browser_crash)
        self.worker.finished_signal.connect(self._on_refresh_finished)
        self.worker.start()

    def _on_status_update(self, msg, color):
        self.lbl_status.setText(msg)
        if color:
            self.lbl_status.setStyleSheet(f"color: {color};")
        else:
            # Revert to default text color based on theme
            self.lbl_status.setStyleSheet("")

    def _on_progress_update(self, current_idx, title):
        self._on_status_update(f"Fetching {current_idx}/{len(self.titles)}: {title}...", "#ffaa22")

    def _on_image_ready(self, idx, img_path):
        self.current_image_paths[idx] = img_path
        lbl = self.img_labels[idx]
        pw = lbl.width()
        ph = lbl.height()
        
        from PySide6.QtGui import QImage
        image = QImage(img_path)
        if not image.isNull():
            if self.is_dark_mode:
                image.invertPixels(QImage.InvertMode.InvertRgb)

            pixmap = QPixmap.fromImage(image)
            scaled_pixmap = pixmap.scaled(pw, ph, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl.setPixmap(scaled_pixmap)
            
            self.update_labels[idx].setText(f"Updated: {get_now().strftime('%H:%M:%S')}")
            self.update_labels[idx].setStyleSheet("")

    def _on_image_failed(self, idx, reason):
        self.update_labels[idx].setText(reason)
        self.update_labels[idx].setStyleSheet("color: #ff4444;")

    def _on_browser_crash(self):
        self._on_status_update("BROWSER CRASH! Auto-Restarting...", "#ff4444")
        logger.error("Browser crash terdeteksi. Memulai auto-recovery...")
        
        msg = (
            "🚨 <b>MRTG Monitor CRASH DETECTED!</b>\n"
            f"⏰ Waktu: {get_now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            "🔄 Status: Auto-restarting...\n"
            f"📍 Lokasi: {MONITOR_NAME}"
        )
        send_telegram_alert(msg)
        
        try:
            beep_enabled = os.getenv("CRASH_BEEP_ENABLED", "true").lower() == "true"
            if beep_enabled:
                for _ in range(3):
                    winsound.Beep(1000, 500)
                    time.sleep(0.1)
        except Exception:
            pass
            
        # Restart script safely
        python_path = os.path.realpath(sys.executable)
        if python_path.endswith(('python.exe', 'pythonw.exe')):
            subprocess.Popen([python_path] + sys.argv)
        sys.exit(0)

    def _on_refresh_finished(self):
        self.is_refreshing = False
        self.elapsed_time = 0

    def closeEvent(self, event):
        """Dipanggil saat window ditutup (misal saat ditekan ESC)"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        try:
            self.driver.quit()
        except Exception:
            pass
        event.accept()


# ========================================================
#  MAIN
# ========================================================
def main():
    logger.info("=" * 60)
    logger.info(f"  MRTG LIVE MONITOR SESI DIMULAI - {get_now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 60)
    
    print("============================================================")
    print("  MRTG LIVE MONITOR (PySide6 Edition)")
    print("============================================================")
    print("[*] Mencari server NTP untuk sinkronisasi waktu...")

    helpers.NTP_OFFSET = get_ntp_offset()
    if helpers.NTP_OFFSET == 0.0:
        print("NTP sync gagal, menggunakan waktu lokal.\n")
    else:
        print(f"Waktu berhasil dikalibrasi (Offset: {helpers.NTP_OFFSET:.4f} detik)\n")

    # Start periodic NTP sync thread
    threading.Thread(target=sync_ntp_periodic, daemon=True).start()

    # Baca graph titles
    if not os.path.exists(GRAPH_TITLE_FILE):
        print(f"ERROR: File '{GRAPH_TITLE_FILE}' tidak ditemukan!")
        sys.exit(1)

    titles, title_mapping = baca_graph_titles(GRAPH_TITLE_FILE)
    if not titles:
        print("ERROR: Tidak ada Graph-title ditemukan di file!")
        sys.exit(1)

    if len(titles) > MAX_GRAPHS:
        print(f"\n⚠️  PERINGATAN: Ditemukan {len(titles)} grafik, melebihi batas maksimal ({MAX_GRAPHS}).")
        print(f"    Hanya {MAX_GRAPHS} grafik pertama yang akan ditampilkan.")
        titles = titles[:MAX_GRAPHS]
        # Filter title_mapping juga
        title_mapping = {k: v for k, v in title_mapping.items() if k in titles}

    refresh_interval = hitung_refresh_interval(len(titles))
    grid_cols = math.ceil(math.sqrt(len(titles)))
    grid_rows = math.ceil(len(titles) / grid_cols)

    print("\nGraph-title :")
    for t in titles:
        display = title_mapping.get(t, t)
        print(f"  {t} : {display}")
    print(f"Total : {len(titles)} grafik")
    print(f"Grid layout : {grid_cols}x{grid_rows}")
    print(f"Refresh interval : {refresh_interval} detik (otomatis)\n")

    # Buka browser
    print("Membuka browser Chrome...")
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
    except Exception as e:
        logger.warning(f"Download ChromeDriver otomatis gagal: {e}")
        try:
            # Fallback ke bawaan Selenium 4.6+
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(60)
            driver.set_script_timeout(30)
        except Exception as e2:
            logger.critical(f"Tetap tidak bisa membuka Chrome: {e2}")
            print("\n[ERROR FATAL] Tetap tidak bisa membuka Chrome")
            print("\n>>> SOLUSI MANUAL <<<")
            print("1. Cek versi Google Chrome Anda (Settings -> About Chrome).")
            print("2. Download 'chromedriver.exe' yang versinya cocok dari internet.")
            print("3. Taruh file 'chromedriver.exe' tersebut ke dalam folder ini.")
            print("4. Jalankan ulang script.")
            sys.exit(1)

    try:
        driver.get(PORTAL_URL)
    except Exception as e:
        logger.warning(f"Timeout atau lambat saat load halaman awal. Melanjutkan secara manual. Detail: {e}")
        print("\n[!] Halaman dimuat sangat lambat (Timeout). Silakan lanjutkan login secara manual di browser.")

    print("\n" + "=" * 60)
    print("  LOGIN MANUAL: masukkan username, password, captcha, MFA")
    print("  >> PENTING: Browser akan disembunyikan SETELAH login berhasil.")
    print("  >> Pastikan tidak ada screen recording software berjalan.")
    print("  Setelah login berhasil, tekan ENTER di sini.")
    print("  Script akan otomatis navigasi ke halaman List Graph.")
    print("=" * 60)
    input("  >> TEKAN ENTER SETELAH LOGIN... ")

    # Otomatis navigasi ke halaman List Graph
    print("\nNavigasi otomatis ke halaman List Graph...")
    try:
        # Klik menu "Graph"
        graph_menu = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-id='2'] span.title"))
        )
        if "Graph" not in graph_menu.text:
            raise Exception("Element mismatch: expected 'Graph' menu")
        driver.execute_script("arguments[0].click();", graph_menu)
        time.sleep(1)

        # Klik submenu "List Graph"
        list_graph = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='/graph'][data-id='1']"))
        )
        driver.execute_script("arguments[0].click();", list_graph)
        time.sleep(2)

        # Tunggu halaman List Graph siap (ada input graphtitle)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "graphtitle"))
        )
        print("  Berhasil masuk ke halaman List Graph!")
    except Exception as e:
        print(f"  [WARNING] Navigasi otomatis gagal: {e}")
        print("  Silakan navigasi manual ke halaman List Graph, lalu tekan ENTER.")
        input("  >> TEKAN ENTER SETELAH DI HALAMAN LIST GRAPH... ")

    print("\nMenyembunyikan browser sepenuhnya...")
    time.sleep(1)  # Beri waktu agar judul halaman Chrome terupdate
    chrome_hwnds = cari_dan_hide_chrome(driver)
    if chrome_hwnds:
        print(f"  Chrome disembunyikan ({len(chrome_hwnds)} jendela)")
    else:
        print("  [INFO] HWND tidak ditemukan, fallback ke minimize")
        try:
            driver.minimize_window()
        except Exception:
            pass

    # Launch GUI
    print("\nMeluncurkan UI PySide6...")
    app = QApplication(sys.argv)
    
    # Optional: Set global font if needed
    # app.setFont(QFont("Consolas", 10))

    monitor_window = LiveMonitorApp(titles, title_mapping, driver, chrome_hwnds)
    monitor_window.show()

    print("\nLive monitor aktif!")
    print("  ESC   = keluar")
    print("  SPACE = refresh sekarang")
    print("  CTRL+C di CMD = paksa berhenti\n")

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        print("\n[*] Menutup browser dan mengakhiri sesi...")
        try:
            driver.quit()
        except Exception as e:
            logger.error(f"Error saat menutup browser: {e}")
        
        logger.info("=" * 60)
        logger.info(f"  MRTG LIVE MONITOR SESI SELESAI - {get_now().strftime('%d/%m/%Y %H:%M:%S')}")
        logger.info("=" * 60)
        logger.info("")


if __name__ == "__main__":
    main()