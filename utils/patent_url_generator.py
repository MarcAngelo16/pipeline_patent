#!/usr/bin/env python3
"""
Patent URL Generator for Patent Family Derivatives

Creates Google Patents and PubChem URLs for patent family patents
that don't have URLs from the original fetcher.
"""


class PatentURLGenerator:
    """Generate URLs for patent family derivatives"""

    def __init__(self):
        self.google_base = "https://patents.google.com/patent"
        self.pubchem_base = "https://pubchem.ncbi.nlm.nih.gov/patent"

    def generate_google_patents_url(self, patent_id):
        """
        Generate Google Patents URL by removing hyphens
        Example: WO-2024184281-A1 → https://patents.google.com/patent/WO2024184281A1/en
        """
        if not patent_id:
            return ""

        # Remove all hyphens and spaces
        clean_id = patent_id.replace("-", "").replace(" ", "").strip()
        return f"{self.google_base}/{clean_id}/en"

    def generate_pubchem_url(self, patent_id):
        """
        Generate PubChem patent URL (keeps original format with hyphens)
        Example: WO-2024184281-A1 → https://pubchem.ncbi.nlm.nih.gov/patent/WO-2024184281-A1
        """
        if not patent_id:
            return ""

        # Keep original format
        clean_id = patent_id.strip()
        return f"{self.pubchem_base}/{clean_id}"

    def generate_both_urls(self, patent_id):
        """Generate both Google Patents and PubChem URLs"""
        return {
            "google_patent": self.generate_google_patents_url(patent_id),
            "pubchem_patent": self.generate_pubchem_url(patent_id)
        }


def test_url_generation():
    """Test URL generation with sample patent IDs"""
    generator = PatentURLGenerator()

    test_patents = [
        "WO-2024184281-A1",
        "US-12345678-A1",
        "EP-3456789-A1",
        "LU-92099-I2"
    ]

    print("=== TESTING URL GENERATION ===")
    for patent_id in test_patents:
        urls = generator.generate_both_urls(patent_id)
        print(f"\nPatent ID: {patent_id}")
        print(f"Google:   {urls['google_patent']}")
        print(f"PubChem:  {urls['pubchem_patent']}")


if __name__ == "__main__":
    test_url_generation()