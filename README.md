# EU Gas Storage Dashboard — AGSI

Live interactive dashboard for exploring European gas storage using the  
GIE AGSI API.

**Live App:** https://dweyts5rpqhof44uvw5tgr.streamlit.app/  

This dashboard provides:
- **EU + country-level** gas storage data
- **Time-series view** (gas in storage, TWh)
- **5-year seasonal comparison**
- **10-year min–max band** + **median** + current year
- **CSV downloads** for all chart views

---

## Features

### Time series
Daily gas-in-storage levels (TWh), with zoom + export via Plotly.

### 5-year seasonal comparison
Storage aligned by day-of-year, one line per year  
→ excellent for studying seasonality across years.

### 10-year “normal range”
For each day of year:
- min–max range (shaded band)
- median (typical year)
- current year highlighted

### EU vs Country mode
Choose:
- EU aggregate
- Any supported European country (AT, BE, CZ, DE, FR, IT, NL, PL, etc.)

### CSV downloads
Export:
- Raw time series  
- 5-year DOY pivot  
- 10-year DOY pivot  

---

## How to run locally

### 1. Clone repo
```bash
git clone https://github.com/amun0905/Gas-Storage-Dashboard.git
cd Gas-Storage-Dashboard
