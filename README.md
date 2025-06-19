# Flask Warranty Tracker

A web application for tracking assets, warranties, and alerts. Built with Flask.

## Features

- Asset management (add, edit, delete)
- Warranty tracking and expiration alerts
- Dashboard with statistics
- Data export functionality
- Customizable alert settings

## Project Structure

```
flask-wip/
├── app/
│   ├── __init__.py
│   ├── database.py
│   └── routes/
│       ├── __init__.py
│       ├── alerts.py
│       ├── assets.py
│       ├── export.py
│       ├── main.py
│       ├── settings.py
│       └── stats.py
├── app.py
├── config.py
├── requirements.txt
├── static/
│   ├── css/
│   └── js/
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── edit_asset.html
│   ├── error.html
│   ├── upload.html
│   ├── alert_settings.html
│   └── _asset_table.html
└── warranty.db
```

## Getting Started

### Prerequisites

- Python 3.8+
- pip

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Toymakerftw/warranty_dash.git
   cd warranty_dash
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up the database:**
   - The app uses `warranty.db` (SQLite). If not present, it will be created on first run.

### Running the Application

```bash
flask run
```

Or, if you use `app.py` as the entry point:

```bash
python app.py
```

The app will be available at [http://127.0.0.1:5000](http://127.0.0.1:5000).

## CSV Upload Format

To bulk import assets, upload a CSV file with the following columns:

- `asset_tag` (required)
- `service_tag` (required)
- `manufacturer` (required)
- `model` (optional)
- `warranty_end_date` (optional, format: YYYY-MM-DD)

**Example:**

```csv
asset_tag,service_tag,manufacturer,model,warranty_end_date
ASSET001,SVC12345,Dell,Latitude 5400,2025-12-31
ASSET002,SVC67890,HP,EliteBook 840,2024-08-15
ASSET003,SVC54321,Apple,MacBook Pro,2026-03-10
```

## Configuration

- Edit `config.py` to adjust settings (e.g., secret key, database URI).

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*Feel free to contribute or open issues!* 