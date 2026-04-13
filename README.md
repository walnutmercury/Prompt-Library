# Report Viewer

Streamlit app for viewing MicroStrategy migrated reports via IBM DB2.

## Quick Start

```
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

The app runs in **demo mode** automatically if `.env` is missing or incomplete.
Demo mode uses realistic sample data — no DB2 connection required.

---

## Connecting to DB2

1. Find your DSN name:
   - Windows Start > search "ODBC Data Sources"
   - Click the **System DSN** tab
   - Find the entry Toad for Data uses — copy the name exactly

2. Edit `.env`:
   ```
   DB2_DSN=YourDSNNameHere
   DB2_USERNAME=your_username
   DB2_PASSWORD=your_password
   ```

3. Restart the app. The blue demo banner disappears when connected.

---

## Adding Reports

### Option A — Generate from MicroStrategy Report Details

```
python generate_report_config.py input.txt
python add_to_config.py
```

### Option B — Add manually to reports.json

Each report entry follows this structure:

```json
{
  "name": "Report Name",
  "description": "Optional description",
  "sql": "SELECT col FROM schema.table WHERE col IN :token",
  "columns": ["Display Name 1", "Display Name 2"],
  "filters": [
    {
      "name": "Filter Label",
      "type": "multiselect",
      "column": "DB2_COLUMN",
      "table": "SCHEMA.TABLE",
      "token": ":token",
      "default": null
    }
  ]
}
```

Filter types: `multiselect`, `date`, `numeric`

---

## Troubleshooting

**DSN not found**
Check the exact DSN name under ODBC Data Sources > System DSN.
Names are case-sensitive.

**Authentication failed**
Verify DB2_USERNAME and DB2_PASSWORD in `.env`.
Test the same credentials in Toad.

**SQL execution error**
The app shows the exact SQL that ran and the DB2 error.
Common cause: token not replaced — check filter token names match SQL placeholders.
