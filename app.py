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

@dataclass
class Book:
    """Represents a book with its metadata"""
    title: str
    author: str
    isbn: Optional[str] = None
    goodreads_id: Optional[str] = None
    
    def __str__(self):
        return f"{self.title} by {self.author}"

@dataclass
class LibraryResult:
    """Represents library availability result"""
    book: Book
    available: bool
    location: Optional[str] = None
    call_number: Optional[str] = None
    status: Optional[str] = None
    url: Optional[str] = None
    
class GoodreadsExtractor:
    """Handles extraction of books from Goodreads"""
    
    def __init__(self):
        self.session = requests.Session()
        # Add headers to appear more like a regular browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def load_from_csv(self, csv_file_path: str) -> List[Book]:
        """
        Load books from Goodreads CSV export
        You can export your library from Goodreads settings > Import/Export
        """
        books = []
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Filter for "Want to Read" shelf
                    if row.get('Exclusive Shelf', '').lower() == 'to-read':
                        book = Book(
                            title=row.get('Title', ''),
                            author=row.get('Author', ''),
                            isbn=row.get('ISBN13', '') or row.get('ISBN', ''),
                            goodreads_id=row.get('Book Id', '')
                        )
                        books.append(book)
        except FileNotFoundError:
            print(f"CSV file not found: {csv_file_path}")
            print("Export your Goodreads library from: Settings > Import/Export")
        except Exception as e:
            print(f"Error reading CSV: {e}")
        
        return books
    
class PBCLibraryScraper:
    def __init__(self):
        self.base_url = "https://pbclibrary.bibliocommons.com/v2/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.driver = None #Selenium driver
        self.setup_selenium()
        
    
    def build_search_query(self, title, author):
        """Build the BiblioCommons search query string"""
        # Clean up title and author - remove extra spaces and special characters
        title = title.strip().replace('"', '')
        author = author.strip().replace('"', '')
        
        # Build the query in BiblioCommons format
        query = f"(title:({title}) AND contributor:({author}))"
        return query
    
    def search_book(self, book: Book):
        """Search for a book using Selenium and return availability information"""
        query = self.build_search_query(book.title, book.author)
        
        # Build the full URL
        params = {
            'custom_edit': 'false',
            'query': query,
            'searchType': 'bl',
            'suppress': 'true'
        }
        
        # Convert params to URL string
        from urllib.parse import urlencode
        search_url = f"{self.base_url}?{urlencode(params)}"
        
        try:
            # Use Selenium to get the page
            self.driver.get(search_url)
            
            # Wait for search results to load
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cp-search-result-item-content")))
            
            # Get the current page source from Selenium
            html_content = self.driver.page_source
            
            return self.parse_search_results(html_content, book)
            
        except Exception as e:
            print(f"Error searching for '{book.title}' by {book.author}: {e}")
            return None
    
    def parse_search_results(self, html_content, original_book: Book):
        """Parse the search results HTML to extract availability info"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        results = []
      #  print(self.driver.page_source)
        # Look for book items in the search results
        # The exact selectors may need adjustment based on the actual HTML structure
        book_items = soup.find_all('div', class_='cp-search-result-item-content')
        for item in book_items:
            try:
                # Extract book title
                title_elem = item.find('span', class_='title-content')
                book_title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                
                # Extract author
                author_elem = item.find('span', class_='cp-author-link')
                book_author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                if book_author != "Unknown" and ', ' in book_author:
                    # Change to First Last format
                        last_name, first_name = book_author.split(', ', 1)
                        book_author =  f"{first_name} {last_name}"
             
                
                # Extract availability information
                availability_elem = item.find('span', class_='cp-availability-status')
                availability = "Unknown"  # Default value

                if availability_elem:
                    availability_text = availability_elem.get_text(strip=True)
                    element_classes = availability_elem.get('class', [])
                    
                    print("Availability text:", availability_text)
                    print("Element classes:", element_classes)
                    
                    # Check the classes to determine availability
                    if 'unavailable' in element_classes:
                        availability = availability_text  # "All copies in use"
                    elif 'available' in element_classes:
                        availability = "Available"
                    else:
                        # Fallback to text content
                        availability = availability_text if availability_text else "Available"
                                
                # Extract format information
                format_elem = item.find('li', class_='bib-field-value')
                book_format = format_elem.get_text(strip=True) if format_elem else "Unknown"
                
                # Extract link to detailed view
                link_elem = item.find('a', href=True)
                detail_link = link_elem['href'] if link_elem else None
                if detail_link and not detail_link.startswith('http'):
                    detail_link = f"https://pbclibrary.bibliocommons.com{detail_link}"
                    
                
                
                results.append({
                    'title': book_title,
                    'author': book_author,
                    'format': book_format,
                    'availability': availability,
                    'detail_link': detail_link
                })
                
            except Exception as e:
                print(f"Error parsing book item: {e}")
                continue
        
        return results
    
    def setup_selenium(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-images')  # Don't load images
            chrome_options.add_argument('--disable-javascript')  # Disable JS if not needed
            chrome_options.add_argument('--disable-css')  # Disable CSS loading
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-agent={self.headers["User-Agent"]}')
            
            # Page load strategy - don't wait for all resources
            chrome_options.add_argument('--page-load-strategy=eager')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(5)  # Reduce implicit wait
            print("Selenium WebDriver initialized")
        except Exception as e:
            print(f"Error setting up Selenium: {e}")

    def get_branch_availability(self, detail_link):
        """Optimized branch availability check"""
        if not detail_link:
            return None
            
        try:
            self.driver.get(detail_link)
            
            # Use WebDriverWait instead of sleep
            wait = WebDriverWait(self.driver, 10)
            
            # Wait for availability button and click
            availability_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/main/div/div/section[1]/div/div[3]/div/div/div[2]/div[1]/div/button"))
            )
            availability_button.click()
            
            # Wait for tbody to be present
            tbody = wait.until(EC.presence_of_element_located((By.TAG_NAME, "tbody")))
            text = tbody.text

            branch_names = self.extract_available_locations(text)
            
            # Fix the redundant loop
            branch_info = []
            for branch in branch_names:
                branch_info.append({'branch': branch})
                
                
            #Click back out
            
            # Wait for availability button and click
            availability_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[24]/div/button"))
            )
            availability_button.click()
            
            wait = WebDriverWait(self.driver, 10)
            
           
            
            return branch_info
            
        except Exception as e:
            print(f"Error with Selenium availability: {e}")
            return None
        
            
    def __del__(self):
        """Clean up Selenium driver"""
        if self.driver:
            self.driver.quit()
    
    def extract_available_locations(self, tbody_text):
        lines = tbody_text.strip().split('\n')
        available_locations = []
        
        # Find the "Available" section
        in_available_section = False
        
        for line in lines:
            line = line.strip()
            
            # Check if we're entering the Available section
            if line.startswith('Available ('):
                in_available_section = True
                continue
            
            # Check if we're leaving the Available section
            if line.startswith('On order (') or line.startswith('Not available at this time ('):
                in_available_section = False
                continue
            
            # If we're in the Available section, look for location names
            if in_available_section and line:
                # Skip collection and call number lines
                if ('Collection' not in line and 
                    'FIC' not in line and 
                    line != 'Available' and
                    not line.startswith('**')):
                    
                    # Check if it's a location (contains BRANCH, LIBRARY, BOOKMOBILE, etc.)
                    if re.search(r'(BRANCH|LIBRARY|BOOKMOBILE|BOOKS BY MAIL)', line, re.IGNORECASE):
                        available_locations.append(line)
        
        return available_locations
    
    
          
    
    def check_books(self, books: List[Book], preferred_branch=None):
        """Check availability for a list of books from Goodreads"""
        results = []
        
        for i, book in enumerate(books):
            print(f"Checking book {i+1}/{len(books)}: {book.title}")
            
            # Search for the book
            search_results = self.search_book(book)
            
            if search_results:
                for result in search_results:
                    # Get detailed branch availability if needed
                    branch_availability = None
                    if preferred_branch and result['detail_link']:
                        branch_availability = self.get_branch_availability(result['detail_link'])
                    
                    result_data = {
                        'original_title': book.title,
                        'original_author': book.author,
                        'original_isbn': book.isbn,
                        'original_goodreads_id': book.goodreads_id,
                        'found_title': result['title'],
                        'found_author': result['author'],
                        'format': result['format'],
                        'availability': result['availability'],
                        'detail_link': result['detail_link'],
                        'branch_availability': branch_availability
                    }
                    
                    results.append(result_data)
            else:
                results.append({
                    'original_title': book.title,
                    'original_author': book.author,
                    'original_isbn': book.isbn,
                    'original_goodreads_id': book.goodreads_id,
                    'found_title': None,
                    'found_author': None,
                    'format': None,
                    'availability': 'Not found',
                    'detail_link': None,
                    'branch_availability': None
                })
            
            # Be respectful with rate limiting
            time.sleep(1)
        
        return results

# Example usage
if __name__ == "__main__":
    # Option 1: Load from Goodreads CSV export
    print("Loading books from Goodreads CSV export...")
    goodreads_extractor = GoodreadsExtractor()
    csv_file = "goodreads_library_export.csv"
    books = goodreads_extractor.load_from_csv(csv_file)
    

    
    if not books:
        print("No books found in CSV. Using example books instead.")
        # Option 2: Manual book list for testing
        books = [
            Book(title="The Nightingale", author="Kristin Hannah"),
            Book(title="Where the Crawdads Sing", author="Delia Owens"),
            Book(title="The Seven Husbands of Evelyn Hugo", author="Taylor Jenkins Reid")
        ]
    
    print(f"Found {len(books)} books to check")
    
    # Initialize scraper
    scraper = PBCLibraryScraper()
    
    # Check availability (optionally specify preferred branch)
    results = scraper.check_books(books, preferred_branch="West Palm Beach")
    
    # Display results
    print("\n" + "="*50)
    print("LIBRARY AVAILABILITY RESULTS")
    print("="*50)
    
    for result in results:
        print(f"\n--- {result['original_title']} by {result['original_author']} ---")
        if result['found_title']:
            print(f"Found: {result['found_title']} by {result['found_author']}")
            print(f"Format: {result['format']}")
            print(f"Availability: {result['availability']}")
            if result['detail_link']:
                print(f"Link: {result['detail_link']}")
            if result['branch_availability']:
                print("Branch availability:")
                for branch in result['branch_availability']:
                    print(f"  - Branch:: {branch['branch']}")
        else:
            print("❌ Not found in library system")
    
    # Save results to JSON file
    with open('library_availability.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to library_availability.json")
    print(f"📚 Checked {len(books)} books, found {len([r for r in results if r['found_title']])} matches")