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
    print("Loading books from Goodreads CSV export...")
    goodreads_extractor = GoodreadsExtractor()
    csv_file = "goodreads_library_export_copy.csv" #Use a copy with a shorter list for testing
    books = goodreads_extractor.load_from_csv(csv_file)  #A list of all the books from a GoodReads CSV File
    
    print(f"Found {len(books)} books to check") 
    
     # Initialize scraper
    scraper = PBCLibraryScraper()
    
    # Check availability (optionally specify preferred branch)
    results = scraper.check_books(books)
    
    
    