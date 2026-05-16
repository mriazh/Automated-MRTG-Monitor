# 📊 Automated Network Graph Monitor

A robust, Python-based desktop application for monitoring internal network bandwidth graphs (like MRTG) in real-time. Built with **PySide6 (Qt)** for a beautiful, responsive GUI and **Selenium** for reliable automated background extraction from legacy/internal web portals.

![Monitor Screenshot](docs/screenshot.png) *(Note: Replace with your own anonymized screenshot)*

## 🚀 Features

- **Real-Time Automated Refresh**: Fetches updated network graphs in the background without interrupting the user.
- **Smart Wait & Canvas Extraction**: Bypasses viewport cropping, sticky-header interference, and heavy AJAX table filtering using injected Javascript Canvas API.
- **Resilient Authentication**: Uses a human-in-the-loop manual login approach to easily bypass Captchas and MFA, ensuring zero downtime when the portal updates its login page.
- **Auto-Recovery & Crash Handling**: Automatically restarts and recovers if the browser crashes or the connection drops.
- **Telegram Alert Integration**: Pushes crash notifications directly to your phone.
- **Dark / Light Mode**: Sleek UI with an instant toggle (press `/`).
- **NTP Synchronization**: Calibrates internal timers with global NTP servers to ensure accurate refresh intervals.

## 🛠️ Prerequisites

- **Python 3.10+**
- Google Chrome installed on your machine.

## 📦 Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/Automated-Bandwidth-Monitor.git
   cd Automated-Bandwidth-Monitor
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Setup your environment variables:
   - Rename `.env.example` to `.env`.
   - Fill in your internal portal URL and optional Telegram Bot credentials.

4. Configure your graphs:
   - Create a file named `GRAPH-TITLE-MRTG.txt` in the root directory.
   - Add the graph IDs you want to monitor. Format:
     ```text
     Graph-title : 12345 => UPLINK SERVER A (12345)
     Graph-title : 67890 => DOWNLINK SERVER B (67890)
     ```

## 🎮 Usage

Simply run the main script:
```bash
python mrtg_monitor.py
```
A terminal will pop up asking you to log in to your portal manually. Once logged in, press `ENTER` in the terminal, and the automated dashboard will take over!

## 🛡️ Security & Disclaimer

This tool is designed to automate repetitive tasks on **authorized internal networks only**.
- **DO NOT** commit your `.env` or `GRAPH-TITLE-MRTG.txt` files containing sensitive internal URLs or IDs.
- The use of this tool must comply with your organization's IT security policies. The author is not responsible for any misuse.

## 📄 License

MIT License
