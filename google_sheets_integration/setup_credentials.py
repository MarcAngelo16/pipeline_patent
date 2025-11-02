#!/usr/bin/env python3
"""
Google Sheets Credentials Setup

Interactive script to help users set up Google Sheets API credentials
specifically for the patent pipeline google_sheets_integration folder.
"""

import os
import json
import sys


def main():
    """Main setup function"""
    current_dir = os.path.dirname(__file__)
    creds_path = os.path.join(current_dir, 'google_credentials.json')

    print("\n🔧 PATENT PIPELINE - Google Sheets Setup")
    print("=" * 60)
    print(f"📁 Credentials will be saved to: {creds_path}")
    print()

    # Check if credentials already exist
    if os.path.exists(creds_path):
        print(f"✅ Credentials file already exists: {creds_path}")
        choice = input("Do you want to replace it? (y/N): ").strip().lower()
        if choice != 'y':
            print("Setup cancelled.")
            return

    print("\nStep-by-step Google Sheets API setup:")
    print("-" * 40)

    print("\n1. 🌐 Go to Google Cloud Console:")
    print("   https://console.cloud.google.com/")

    print("\n2. 📁 Create or Select Project:")
    print("   - Create a new project OR select existing project")
    print("   - Name it something like 'patent-pipeline'")

    print("\n3. 🔌 Enable APIs:")
    print("   - Go to 'APIs & Services' > 'Library'")
    print("   - Search and enable: 'Google Sheets API'")
    print("   - Search and enable: 'Google Drive API'")

    print("\n4. 🔑 Create Service Account:")
    print("   - Go to 'APIs & Services' > 'Credentials'")
    print("   - Click 'Create Credentials' > 'Service Account'")
    print("   - Name: 'patent-pipeline-service'")
    print("   - Role: 'Editor' (or 'Owner' for full access)")

    print("\n5. 📥 Download JSON Key:")
    print("   - Click on created service account")
    print("   - Go to 'Keys' tab")
    print("   - Click 'Add Key' > 'Create new key' > 'JSON'")
    print("   - Download the JSON file")

    print("\n6. 📁 Place Credentials File:")
    print(f"   - Save the downloaded JSON as: {creds_path}")

    input("\n⏳ Press Enter after completing the above steps...")

    # Check if file exists now
    if not os.path.exists(creds_path):
        print(f"\n❌ Credentials file not found at: {creds_path}")
        print("Please make sure you:")
        print("1. Downloaded the JSON file")
        print("2. Renamed it to 'google_credentials.json'")
        print(f"3. Placed it in: {current_dir}")
        return

    # Validate credentials file
    try:
        with open(creds_path, 'r') as f:
            creds_data = json.load(f)

        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in creds_data]

        if missing_fields:
            print(f"❌ Invalid credentials file. Missing fields: {missing_fields}")
            return

        if creds_data.get('type') != 'service_account':
            print("❌ Invalid credentials file. Must be a service account key.")
            return

        print(f"✅ Credentials file validated!")
        print(f"   Project: {creds_data.get('project_id')}")
        print(f"   Service Account: {creds_data.get('client_email')}")

    except json.JSONDecodeError:
        print("❌ Invalid JSON in credentials file")
        return
    except Exception as e:
        print(f"❌ Error validating credentials: {str(e)}")
        return

    # Test the credentials
    print("\n🧪 Testing Google Sheets connection...")
    try:
        sys.path.append(current_dir)
        from google_sheets_exporter import GoogleSheetsExporter

        exporter = GoogleSheetsExporter(creds_path)
        if exporter.test_connection():
            print("✅ Google Sheets connection successful!")
        else:
            print("⚠️  Connection test inconclusive")

    except Exception as e:
        print(f"⚠️  Connection test failed: {str(e)}")
        print("This might be normal - the pipeline should still work.")

    print("\n🎉 Setup Complete!")
    print("-" * 30)
    print("You can now run the patent pipeline with Google Sheets export:")
    print("python ../main_patent_pipeline.py golimumab --export-sheets")
    print("\nThe pipeline will create a new Google Sheet for each run.")
    print(f"Credentials are stored at: {creds_path}")


if __name__ == "__main__":
    main()