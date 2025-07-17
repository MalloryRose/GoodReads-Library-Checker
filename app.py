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
    
    def scrape_want_to_read_shelf(self, user_id: str) -> List[Book]:
        """
        Scrape books from Goodreads "Want to Read" shelf
        Note: This is a placeholder - you'll need to implement based on Goodreads' current structure
        """
        # This would require web scraping with BeautifulSoup or Selenium
        # Implementation depends on current Goodreads HTML structure
        print("Web scraping not implemented - use CSV export method instead")
        return []

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
    
    def clean_title(self, title):
        return re.sub(r"\s*\(.*?\)", "", title)
    
    def search_book(self, book: Book):
        """Search for a book and return availability information"""
        
        title = self.clean_title(book.title)
        
        query = self.build_search_query(title, book.author)
        
        params = {
            'custom_edit': 'false',
            'query': query,
            'searchType': 'bl',
            'suppress': 'true'
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers)
            response.raise_for_status()
            
            return self.parse_search_results(response.text, book)
            
        except requests.RequestException as e:
            print(f"Error searching for '{book.title}' by {book.author}: {e}")
            return None
    
    def parse_search_results(self, html_content, original_book: Book):
        """Parse the search results HTML to extract availability info"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        results = []
        
        # Look for book items in the search results
        # The exact selectors may need adjustment based on the actual HTML structure
        book_items = soup.find('div', class_='cp-search-result-item-content')
        if book_items:
            try:
                    # Extract book title
                title_elem = book_items.find('span', class_='title-content')
                book_title = title_elem.get_text(strip=True) if title_elem else "Unknown"

             
                # Extract author
                author_elem = book_items.find('span', class_='cp-author-link')
                book_author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                if book_author != "Unknown" and ', ' in book_author:
                    # Change to First Last format
                        last_name, first_name = book_author.split(', ', 1)
                        book_author =  f"{first_name} {last_name}"
                
                # Extract availability information
                availability_elem = book_items.find('span', class_='cp-availability-status')
                availability = "Available"
                if availability_elem:
                    text = availability_elem.get_text().strip()
                    if text == "Available":
                        availability = "Available"
                    elif text == "All copies in use":
                        availability = "Unavailable"
                    else:
                        availability = "Unknown"  # Handle other cases
                    
                # Extract format information
                format_elem = book_items.find('li', class_='bib-field-value')
                book_format = format_elem.get_text(strip=True) if format_elem else "Unknown"
                    
                # Extract link to detailed view
                link_elem = book_items.find('a', href=True)
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
            
        
        return results
    
    def setup_selenium(self):
        # Setup driver
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # Run in background
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-agent={self.headers["User-Agent"]}')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--disable-javascript')  # if not needed
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--no-default-browser-check')
            self.driver = webdriver.Chrome(options=chrome_options)
            print("Selenium WebDriver initialized")
        except Exception as e:
            print(f"Error setting up Selenium: {e}")
            
    def __del__(self):
        """Clean up Selenium driver"""
        if self.driver:
            self.driver.quit()
    
    def extract_branch_names(self, tbody_text):
        # Pattern to match branch names (words ending with "BRANCH" or specific library names)
        pattern = r'^([A-Z][A-Z\s\-\.]+(?:BRANCH|LIBRARY))(?:\s*-\s*[A-Za-z\s]+)?$'
        
        lines = tbody_text.strip().split('\n')
        branch_names = []
        
        for line in lines:
            line = line.strip()
            match = re.match(pattern, line)
            if match:
                branch_names.append(match.group(1).strip())
        
        return list(set(branch_names))  # Remove duplicates
    

    def get_branch_availability(self, detail_link):
        """Selenium-based availability check with optimizations"""
        if not self.driver:
            self.setup_selenium()
            
        try:
            self.driver.get(detail_link)

            
            # Use WebDriverWait instead of time.sleep
            wait = WebDriverWait(self.driver, 5)

            # Wait for availability button to be clickable
            availability_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/main/div/div/section[1]/div/div[3]/div/div/div[2]/div[1]/div/button"))
            )
            
            availability_button.click()

            availability_elem = WebDriverWait(self.driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".cp-heading.heading-medium.availability-group-heading.heading--linked"))
    )
            if "Not available" in availability_elem.text:
                availability = "Unavailable"
            else:
                availability = "Available"
            
            # Wait for tbody to be present after click

            if availability == "Available":
                tbody = wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "tbody"))
                )
                
                text = tbody.text
                branch_names = self.extract_branch_names(text)
            else:
                branch_names = []

          

           
            results = []
            branch_info = []
            for branch in branch_names:
                branch_info.append({'branch': branch})
            
            results.append(availability) #first index is availibility
            results.append(branch_info) #second index is available branches
            return results
            
        except Exception as e:
            print(f"Selenium availability check failed: {e}")
            return None
    
    
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
                    if result['availability'] == 'Available' and result['detail_link']:
                        branch_availability = self.get_branch_availability(result['detail_link'])
                    #******


                    if branch_availability:
                        availability = branch_availability[0]
                        branches = branch_availability[1]
                    else:
                        availability = None
                        branches = None

                    #***
                    result_data = {
                        'original_title': book.title,
                        'original_author': book.author,
                        'original_isbn': book.isbn,
                        'original_goodreads_id': book.goodreads_id,
                        'found_title': result['title'],
                        'found_author': result['author'],
                        'format': result['format'],
                        'availability': availability,
                        'detail_link': result['detail_link'],
                        'branch_availability': branches
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
        
        if self.driver:
            self.driver.quit()
            self.driver = None
           
        
        return results

# Example usage
if __name__ == "__main__":
    start_time = time.time()
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
                    print(f"Branch: {branch['branch']}")
        else:
            print("❌ Not found in library system")
    
    # Save results to JSON file
    with open('library_availability.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to library_availability.json")
    print(f"📚 Checked {len(books)} books, found {len([r for r in results if r['found_title']])} matches")
    
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Script execution time: {execution_time:.2f} seconds")
    
    