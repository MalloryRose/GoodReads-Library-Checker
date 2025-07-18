import requests
import time
import re
import csv
from urllib.parse import quote
from bs4 import BeautifulSoup
import json
from dataclasses import dataclass
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from app import *



if __name__ == "__main__":
    start_time = time.time()
    print("Loading books from Goodreads CSV export...")
    goodreads_extractor = GoodreadsExtractor()
    csv_file = "goodreads_library_export_copy.csv" #Use a copy with a shorter list for testing
    books = goodreads_extractor.load_from_csv(csv_file)  #A list of all the books from a GoodReads CSV File
    # books = [
    #         Book(title="The Nightingale", author="Kristin Hannah"),
    #         Book(title="Where the Crawdads Sing", author="Delia Owens"),
    #         Book(title="The Seven Husbands of Evelyn Hugo", author="Taylor Jenkins Reid")
    #     ]
    print(f"Found {len(books)} books to check") 
    
     # Initialize scraper
    scraper = PBCLibraryScraper()
    
    # Check availability (optionally specify preferred branch)
    results = scraper.check_books(books)
    count_available = 0
    
    for result in results:
        print(f"\n--- {result['original_title']} by {result['original_author']} ---")
        if result['found_title']:
            print(f"Found: {result['found_title']} by {result['found_author']}")
            print(f"Format: {result['format']}")
            print(f"Availability: {result['availability']}")
            if result['availability'] == "Available":
                count_available += 1
            if result['detail_link']:
                print(f"Link: {result['detail_link']}")
            if result['branch_availability']:
                print("Branch availability:")
                for branch in result['branch_availability']:
                    print(f"{branch['branch']}")
        else:
            print("❌ Not found in library system")
    
    # Save results to JSON file
    with open('library_availability_tests.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to library_availability_tests.json")
    print(f"📚 Checked {len(books)} books, found {len([r for r in results if r['found_title']])} matches")
    
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Script execution time: {execution_time:.2f} seconds")
    print(f"Number of books available:  {count_available}")
    
