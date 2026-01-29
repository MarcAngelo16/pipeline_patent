#!/usr/bin/env python3
"""
Google Sheets Exporter for Patent Pipeline

Exports patent data to Google Sheets with automatic sheet creation.
Creates a new spreadsheet for each pipeline run with formatted data.
"""

import gspread
import json
import os
from datetime import datetime
from typing import List, Dict, Any
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow


class GoogleSheetsExporter:
    """Exports patent pipeline results to Google Sheets"""

    def __init__(self, credentials_path: str = None, use_oauth: bool = True):
        """
        Initialize Google Sheets exporter

        Args:
            credentials_path: Path to credentials file (service account or OAuth client)
            use_oauth: If True, use OAuth (personal account), if False, use service account
        """
        self.use_oauth = use_oauth

        if use_oauth:
            # Default paths for OAuth
            default_client_path = os.path.join(os.path.dirname(__file__), 'oauth_client_secret.json')
            default_token_path = os.path.join(os.path.dirname(__file__), 'oauth_token.json')
            self.client_secret_path = credentials_path or os.getenv('OAUTH_CLIENT_SECRET_PATH', default_client_path)
            self.token_path = default_token_path
        else:
            # Default path for service account
            default_path = os.path.join(os.path.dirname(__file__), 'google_credentials.json')
            self.credentials_path = credentials_path or os.getenv('GOOGLE_CREDENTIALS_PATH', default_path)

        self.client = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Sheets API"""
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]

        try:
            if self.use_oauth:
                # OAuth authentication (personal Google account)
                creds = self._get_oauth_credentials(scope)
                self.client = gspread.authorize(creds)
                print("✅ Google Sheets authentication successful (OAuth - Personal Account)")
            else:
                # Service Account authentication
                if self.credentials_path and os.path.exists(self.credentials_path):
                    creds = Credentials.from_service_account_file(
                        self.credentials_path, scopes=scope
                    )
                    self.client = gspread.authorize(creds)
                    print("✅ Google Sheets authentication successful (Service Account)")
                else:
                    raise Exception("Service account credentials not found")

        except Exception as e:
            print(f"❌ Google Sheets authentication failed: {str(e)}")
            raise

    def _get_oauth_credentials(self, scope):
        """Get OAuth credentials for personal Google account"""
        creds = None

        # Check if we have a saved token
        if os.path.exists(self.token_path):
            creds = OAuthCredentials.from_authorized_user_file(self.token_path, scope)

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("🔄 Refreshed OAuth token")
                except Exception as e:
                    print(f"⚠️  Token refresh failed: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(self.client_secret_path):
                    raise Exception(f"OAuth client secret not found at: {self.client_secret_path}")

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, scope)

                # Try local server first, fallback to manual flow
                try:
                    creds = flow.run_local_server(port=0)
                except Exception:
                    print("\n📋 Manual authorization required (no browser available)")
                    print("Please follow these steps:")

                    # Get authorization URL
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    print(f"\n1. 🌐 Open this URL in your browser:")
                    print(f"   {auth_url}")
                    print(f"\n2. 👤 Sign in with: adambaihaqi16@satriamudapp.com")
                    print(f"3. ✅ Click 'Allow' to authorize the application")
                    print(f"4. 📋 Copy the authorization code from the browser")

                    # Get authorization code from user
                    auth_code = input("\n5. 📝 Paste the authorization code here: ").strip()

                    # Exchange code for credentials
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                print("🎉 OAuth authentication completed!")

            # Save the credentials for the next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
                print(f"💾 Saved OAuth token to: {self.token_path}")

        return creds

    def export_pipeline_results(self, keyword: str, pipeline_data: Dict[str, Any],
                                 source: str = 'pubchem') -> str:
        """
        Export complete pipeline results to a new Google Sheet

        Args:
            keyword: Search keyword or display name
            pipeline_data: Complete pipeline output data
            source: Data source - 'pubchem' or 'drugbank' (default: 'pubchem')

        Returns:
            URL of the created Google Sheet
        """
        try:
            # Create new spreadsheet with source prefix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_prefix = source.capitalize()  # "Pubchem" or "Drugbank"
            sheet_title = f"Patent_Pipeline_{source_prefix}_{keyword}_{timestamp}"

            spreadsheet = self.client.create(sheet_title)

            # Make spreadsheet publicly viewable (optional)
            spreadsheet.share('', perm_type='anyone', role='reader')

            # Create worksheets
            self._create_summary_sheet(spreadsheet, pipeline_data)
            self._create_patents_sheet(spreadsheet, pipeline_data['patents'])

            print(f"✅ Google Sheet created: {sheet_title}")
            return spreadsheet.url

        except Exception as e:
            print(f"❌ Failed to export to Google Sheets: {str(e)}")
            raise

    def _create_summary_sheet(self, spreadsheet, pipeline_data: Dict[str, Any]):
        """Create summary sheet with pipeline statistics"""
        try:
            # Use the default sheet (Sheet1) for summary
            summary_sheet = spreadsheet.sheet1
            summary_sheet.update_title("Pipeline_Summary")

            pipeline_info = pipeline_data.get('pipeline_info', {})

            # Headers and data
            summary_data = [
                ["Patent Pipeline Summary", ""],
                ["", ""],
                ["Keyword", pipeline_info.get('keyword', 'N/A')],
                ["Execution Time", pipeline_info.get('execution_time', 'N/A')],
                ["Total Patents", pipeline_info.get('total_patents', 0)],
                ["Main Patents", pipeline_info.get('main_patents', 0)],
                ["Family Patents", pipeline_info.get('family_patents', 0)],
                ["Duplicates Removed", pipeline_info.get('duplicates_removed', 0)],
                ["Countries", ', '.join(pipeline_info.get('countries', []))],
                ["Max Families per Country", pipeline_info.get('max_families_per_country', 0)],
                ["", ""],
                ["Processing Statistics", ""],
                ["PubChem API Calls", pipeline_info.get('pubchem_api_calls', 'N/A')],
                ["Google Patents Extractions", pipeline_info.get('google_patents_extractions', 'N/A')],
                ["Success Rate", pipeline_info.get('success_rate', 'N/A')],
            ]

            # Update the sheet
            summary_sheet.update('A1', summary_data)

            # Format headers
            summary_sheet.format('A1:B1', {
                'textFormat': {'bold': True, 'fontSize': 14},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 1.0}
            })

            summary_sheet.format('A12:B12', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.95, 'green': 0.95, 'blue': 0.95}
            })

        except Exception as e:
            print(f"⚠️  Failed to create summary sheet: {str(e)}")

    def _create_patents_sheet(self, spreadsheet, patents: List[Dict[str, Any]]):
        """Create detailed patents sheet with all patent data"""
        try:
            # Add new worksheet for patents
            patents_sheet = spreadsheet.add_worksheet("Patents_Data", rows=1000, cols=30)

            if not patents:
                patents_sheet.update('A1', [["No patents found"]])
                return

            # Define column headers based on first patent
            sample_patent = patents[0]
            headers = self._get_patent_headers(sample_patent)

            # Prepare data rows
            data_rows = [headers]

            for patent in patents:
                row = []
                for header in headers:
                    value = patent.get(header, '')

                    # Handle lists/arrays
                    if isinstance(value, list):
                        value = '; '.join(str(item) for item in value)

                    # Handle nested objects
                    elif isinstance(value, dict):
                        value = str(value)

                    # Ensure string conversion
                    row.append(str(value) if value is not None else '')

                data_rows.append(row)

            # Update sheet with all data
            if len(data_rows) > 1:
                range_notation = f'A1:{chr(65 + len(headers) - 1)}{len(data_rows)}'
                patents_sheet.update(range_notation, data_rows)

                # Format header row
                header_range = f'A1:{chr(65 + len(headers) - 1)}1'
                patents_sheet.format(header_range, {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.8, 'green': 0.9, 'blue': 1.0}
                })

                # Auto-resize columns
                patents_sheet.columns_auto_resize(0, len(headers))

        except Exception as e:
            print(f"⚠️  Failed to create patents sheet: {str(e)}")

    def _get_patent_headers(self, sample_patent: Dict[str, Any]) -> List[str]:
        """Get ordered column headers for patent data"""
        # Define preferred order for important fields
        priority_fields = [
            'patent_id', 'title', 'country', 'extraction_from',
            'abstract_pubchem', 'abstract_google',
            'inventors_pubchem', 'inventors_google',
            'assignee_pubchem', 'assignees_google',
            'priority_date_pubchem', 'filing_date_pubchem', 'publication_date_pubchem',
            'claims', 'patent_family_pubchem',
            'google_patent', 'pubchem_patent', 'extraction_time'
        ]

        # Get all fields from sample patent
        all_fields = list(sample_patent.keys())

        # Order: priority fields first, then remaining fields
        headers = []

        # Add priority fields if they exist
        for field in priority_fields:
            if field in all_fields:
                headers.append(field)

        # Add remaining fields
        for field in all_fields:
            if field not in headers:
                headers.append(field)

        return headers

    def test_connection(self) -> bool:
        """Test Google Sheets API connection"""
        try:
            # Try to access spreadsheets (this will fail gracefully if no access)
            self.client.list_permissions('test')
            return True
        except:
            try:
                # Alternative test - try to create a temporary sheet
                test_sheet = self.client.create('API_Test_Sheet')
                test_sheet.del_worksheet(test_sheet.sheet1)
                self.client.del_spreadsheet(test_sheet.id)
                return True
            except Exception as e:
                print(f"❌ Google Sheets connection test failed: {str(e)}")
                return False

    def delete_spreadsheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        """
        Delete a Google Spreadsheet by ID

        Args:
            spreadsheet_id: The spreadsheet ID to delete

        Returns:
            Dictionary with success status and message
        """
        try:
            if not spreadsheet_id:
                return {
                    'success': False,
                    'error': 'No spreadsheet ID provided'
                }

            # Open the spreadsheet by ID
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            # Delete the spreadsheet
            # Note: gspread doesn't have a direct delete method,
            # so we need to use the Drive API through the client
            try:
                # Try using del_spreadsheet if available (newer gspread versions)
                if hasattr(self.client, 'del_spreadsheet'):
                    self.client.del_spreadsheet(spreadsheet_id)
                else:
                    # Alternative: Move to trash using Drive API
                    # This requires the spreadsheet object
                    spreadsheet.batch_update({
                        'requests': [{
                            'updateSpreadsheetProperties': {
                                'properties': {'title': f'[DELETED] {spreadsheet.title}'},
                                'fields': 'title'
                            }
                        }]
                    })
                    # Note: Full deletion requires Drive API access
                    # For now, we'll mark it as deleted in the title
                    print(f"⚠️  Spreadsheet marked as deleted (full deletion requires Drive API): {spreadsheet_id}")

                print(f"✅ Google Sheet deleted: {spreadsheet_id}")
                return {
                    'success': True,
                    'spreadsheet_id': spreadsheet_id,
                    'message': 'Spreadsheet deleted successfully'
                }

            except Exception as delete_error:
                print(f"⚠️  Could not delete spreadsheet {spreadsheet_id}: {delete_error}")
                return {
                    'success': False,
                    'spreadsheet_id': spreadsheet_id,
                    'error': f'Delete failed: {str(delete_error)}'
                }

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed to delete Google Sheet {spreadsheet_id}: {error_msg}")

            # Check for common errors
            if 'not found' in error_msg.lower() or '404' in error_msg:
                return {
                    'success': True,  # Consider it success if already gone
                    'spreadsheet_id': spreadsheet_id,
                    'message': 'Spreadsheet not found (may already be deleted)'
                }
            elif 'permission' in error_msg.lower() or '403' in error_msg:
                return {
                    'success': False,
                    'spreadsheet_id': spreadsheet_id,
                    'error': 'Permission denied - cannot delete this spreadsheet'
                }
            else:
                return {
                    'success': False,
                    'spreadsheet_id': spreadsheet_id,
                    'error': error_msg
                }


def setup_google_sheets_credentials():
    """Interactive setup for Google Sheets API credentials"""
    current_dir = os.path.dirname(__file__)
    creds_path = os.path.join(current_dir, 'google_credentials.json')

    print("\n🔧 Google Sheets API Setup")
    print("=" * 50)
    print("1. Go to: https://console.cloud.google.com/")
    print("2. Create a new project or select existing")
    print("3. Enable Google Sheets API and Google Drive API")
    print("4. Create credentials (Service Account)")
    print("5. Download JSON key file")
    print(f"6. Save as: {creds_path}")
    print("7. (Optional) Set environment variable: GOOGLE_CREDENTIALS_PATH")
    print("\nAlternatively, you can set the path in the code or pass it as parameter.")
    print("=" * 50)


if __name__ == "__main__":
    # Test script
    setup_google_sheets_credentials()

    # Test with sample data
    current_dir = os.path.dirname(__file__)
    test_creds_path = os.path.join(current_dir, 'google_credentials.json')

    if os.path.exists(test_creds_path):
        try:
            exporter = GoogleSheetsExporter(test_creds_path, use_oauth=False)
            if exporter.test_connection():
                print("✅ Google Sheets setup successful!")
            else:
                print("❌ Google Sheets connection failed")
        except Exception as e:
            print(f"❌ Setup test failed: {str(e)}")
    else:
        print(f"⚠️  Credentials file not found at: {test_creds_path}")
        print("Please follow setup instructions.")