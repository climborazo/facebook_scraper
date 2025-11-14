# 🕵️‍♂️ Facebook Scraper

A Python based tool for **Dynamic Facebook Dom Scraping**, designed to extract posts, authors, timestamps, links, and media from any Facebook page you manually open in Chromium.

It includes:

- An **Interactive Launcher**
- Automatic scrolling
- A powerful **Html Report Generator**
- Clean per page output directories
- No Api keys or login handled internally (the scraper attaches to your own browser session)

---

## ⚙️ Requirements

- **Python 3.9+**
- **Chromium** Installed on your system
- **Playwright** (Chromium driver)
- No Api keys required
- Facebook login performed by *you* in Chromium

Install Playwright dependencies:

```bash
pip install playwright beautifulsoup4
playwright install chromium
```

---

## 🚀 Installation (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip chromium-browser

git clone https://github.com/climborazo/facebook_scraper.git
cd facebook_scraper

python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Create a simple launcher for Chromium:

```bash
echo '#!/bin/bash
nohup chromium --remote-debugging-port=9222 >/dev/null 2>&1 & disown' > chromium.sh
chmod +x chromium.sh
```

Run it:

```bash
./chromium.sh
```

Log into Facebook manually in Chromium.

---

## 📂 Project Structure

```
facebook_scraper/
├─ facebook_scraper.py
├─ core_extractor.py
├─ facebook_adapter.py
├─ html_reporter.py
├─ utils.py
└─ reports/
   └─ <page-identifier>/
         MM.DD.YYYY_HH.MM.SS.html
```

---

## 🧰 Usage

```bash
python3 facebook_scraper.py
```

Follow the prompt:
- Choose text filter
- Enable / disable auto scroll
- Choose scroll steps

---

## 🧭 Troubleshooting

| Issue | Cause | Fix |
|------|--------|------|
| Cannot connect to Chromium | Not started with debugging | Use `./run_chromium.sh` |
| Empty report | Page not fully loaded | Enable auto scroll |
| Missing images | Lazy loading | Increase scroll steps |
| Unknown authors | Fb hides author spans | Normal behavior |
| Permalink missing | Facebook dynamic routing | Scroll or open post manually |

---

## 🪪 License

Licensed under **Gnu Gpl Version 3**.

---

## 👨‍💻 Author

Developed and maintained by **[climborazo](https://github.com/climborazo)** - Contributions and pull requests are welcome...
