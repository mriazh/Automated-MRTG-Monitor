@echo off
REM ============================================================
REM  Build Script — MRTG Live Monitor (.exe) — ONEFILE mode
REM  Jalankan: build.bat
REM ============================================================

echo ============================================
echo   MRTG Live Monitor — Build to .exe
echo ============================================
echo.

REM 1. Pastikan PyInstaller terinstall
echo [1/3] Mengecek PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo      PyInstaller belum terinstall. Menginstall sekarang...
    pip install pyinstaller
    if errorlevel 1 (
        echo      GAGAL menginstall PyInstaller!
        pause
        exit /b 1
    )
)
echo      PyInstaller OK.
echo.

REM 2. Bersihkan folder build lama
echo [2/3] Membersihkan build lama...
if exist "build" rmdir /s /q "build"
if exist "dist\MRTG-Live-Monitor.exe" del /f "dist\MRTG-Live-Monitor.exe"
echo      Bersih.
echo.

REM 3. Build menggunakan spec file
echo [3/3] Memulai build...
echo      (Proses ini membutuhkan beberapa menit, harap tunggu)
echo.
pyinstaller mrtg_monitor.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ============================================
    echo   BUILD GAGAL! Cek error di atas.
    echo ============================================
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD BERHASIL!
echo ============================================
echo.
echo   File .exe ada di:
echo   dist\MRTG-Live-Monitor.exe
echo.
echo   Untuk menjalankan, salin file berikut
echo   ke folder yang sama dengan .exe:
echo   - .env                  (konfigurasi)
echo   - GRAPH-TITLE-MRTG.txt  (daftar graph)
echo.
echo   Lalu jalankan MRTG-Live-Monitor.exe
echo ============================================
pause
