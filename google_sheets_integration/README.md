# Google Sheets Integration

This folder contains everything needed for Google Sheets export functionality in the Patent Pipeline.

## Files Structure

```
google_sheets_integration/
├── README.md                    # This file
├── __init__.py                  # Python package init
├── google_sheets_exporter.py    # Main Google Sheets export logic
├── setup_credentials.py         # Interactive credentials setup
└── google_credentials.json      # Your Google API credentials (you create this)
```

## Quick Setup

### 1. Run Setup Script
```bash
cd /app/AI_pipeline/google_sheets_integration
python setup_credentials.py
```

### 2. Or Manual Setup
1. **Go to:** https://console.cloud.google.com/
2. **Create Project** (e.g., "patent-pipeline")
3. **Enable APIs:** Google Sheets API + Google Drive API
4. **Create Service Account** with Editor role
5. **Download JSON key** and save as `google_credentials.json` in this folder

### 3. Test Connection
```bash
python google_sheets_exporter.py
```

### 4. Use in Pipeline
```bash
cd /app/AI_pipeline
python main_patent_pipeline.py golimumab --export-sheets
```

## What Happens

When you use `--export-sheets`, the pipeline will:

1. ✅ Run normal patent extraction (JSON output)
2. ✅ Create a new Google Sheet with timestamp
3. ✅ Export two sheets:
   - **Pipeline_Summary**: Stats, counts, execution info
   - **Patents_Data**: Detailed patent information (all 19+ fields)
4. ✅ Make sheet publicly readable
5. ✅ Display Google Sheet URL in terminal

## Example Output

```
🎉 PIPELINE COMPLETED SUCCESSFULLY!
📄 Output file: /app/AI_pipeline/output/golimumab_patents.json
📊 Total patents: 41
📊 Google Sheets: https://docs.google.com/spreadsheets/d/1ABC...
```

## Troubleshooting

### Common Issues:
- **"credentials not found"** → Run `setup_credentials.py`
- **"permission denied"** → Check service account has Editor role
- **"API not enabled"** → Enable Google Sheets API + Google Drive API
- **"invalid credentials"** → Re-download JSON key from Google Cloud

### Without Credentials:
Pipeline works normally, just skips Google Sheets export:
```bash
python main_patent_pipeline.py golimumab  # JSON only, no --export-sheets
```

## Security Notes

- ⚠️ **Never commit `google_credentials.json` to version control**
- ✅ Service account credentials are safer than OAuth for automation
- ✅ Created sheets are publicly readable by default (can be changed)
- ✅ Service account has no access to your personal Google Drive

## File Location

The credentials file MUST be at:
```
/app/AI_pipeline/google_sheets_integration/google_credentials.json
```

This is automatically detected by the exporter.