import html
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
from abc import ABC, abstractmethod
import webbrowser


'''
Multithreaded version of app.py
Much faster execution time 

'''
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

class ThreadSafeSeleniumPool:
    """Thread-safe pool of Selenium WebDriver instances"""
    
    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self.drivers = Queue()
        self.lock = threading.Lock()
        self._initialize_drivers()
    
    def _initialize_drivers(self):
        """Initialize the driver pool"""
        for _ in range(self.pool_size):
            driver = self._create_driver()
            if driver:
                self.drivers.put(driver)
    
    def _create_driver(self):
        """Create a new WebDriver instance"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            chrome_options.add_argument('--disable-images')
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
            
            return webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"Error creating WebDriver: {e}")
            return None
    
    def get_driver(self):
        """Get a driver from the pool"""
        try:
            return self.drivers.get(timeout=30)  # Wait up to 30 seconds
        except:
            # If no driver available, create a new one
            return self._create_driver()
    
    def return_driver(self, driver):
        """Return a driver to the pool"""
        if driver:
            self.drivers.put(driver)
    
    def cleanup(self):
        """Clean up all drivers in the pool"""
        while not self.drivers.empty():
            try:
                driver = self.drivers.get_nowait()
                driver.quit()
            except:
                pass

class LibraryScraperBase(ABC):
    @abstractmethod
    def search_book(self, book: Book):
        pass

    @abstractmethod
    def check_books(self, books: List[Book], preferred_branch=None):
        pass

class PBCLibraryScraper(LibraryScraperBase):
    def __init__(self, max_workers: int = 3):
        self.base_url = "https://pbclibrary.bibliocommons.com/v2/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.max_workers = max_workers
        self.driver_pool = ThreadSafeSeleniumPool(max_workers)
        
        # Thread-safe session for requests
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Rate limiting
        self.last_request_time = {}
        self.request_lock = threading.Lock()
        self.min_delay = 1.0  # Minimum delay between requests in seconds
    
    def _rate_limit(self, thread_id):
        """Implement rate limiting per thread"""
        with self.request_lock:
            current_time = time.time()
            if thread_id in self.last_request_time:
                time_since_last = current_time - self.last_request_time[thread_id]
                if time_since_last < self.min_delay:
                    time.sleep(self.min_delay - time_since_last)
            self.last_request_time[thread_id] = time.time()
    
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
        thread_id = threading.current_thread().ident
        self._rate_limit(thread_id)
        
        title = self.clean_title(book.title)
        query = self.build_search_query(title, book.author)
        
        params = {
            'custom_edit': 'false',
            'query': query,
            'searchType': 'bl',
            'suppress': 'true'
        }
        
        try:
            response = self.session.get(self.base_url, params=params, timeout=10)
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
                    book_author = f"{first_name} {last_name}"
                
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
                        availability = "Unknown"
                    
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
        """Selenium-based availability check with thread-safe driver pool"""
        driver = self.driver_pool.get_driver()
        if not driver:
            return None
            
        try:
            driver.get(detail_link)
            
            # Use WebDriverWait instead of time.sleep
            wait = WebDriverWait(driver, 10)

            # Wait for availability button to be clickable
            availability_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/main/div/div/section[1]/div/div[3]/div/div/div[2]/div[1]/div/button"))
            )
            
            availability_button.click()

            availability_elem = wait.until(
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
            
            results.append(availability)  # first index is availability
            results.append(branch_info)  # second index is available branches
            return results
            
        except Exception as e:
            print(f"Selenium availability check failed for {detail_link}: {e}")
            return None
        finally:
            # Always return driver to pool
            self.driver_pool.return_driver(driver)
    
    def process_single_book(self, book: Book):
        """Process a single book - thread-safe function"""
        try:
            print(f"Processing: {book.title} by {book.author}")
            
            # Search for the book
            search_results = self.search_book(book)
            
            if search_results:
                results = []
                for result in search_results:
                    # Get detailed branch availability if needed
                    branch_availability = None
                    if result['availability'] == 'Available' and result['detail_link']:
                        branch_availability = self.get_branch_availability(result['detail_link'])

                    if branch_availability:
                        availability = branch_availability[0]
                        branches = branch_availability[1]
                    else:
                        availability = result['availability']
                        branches = None

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
                
                return results
            else:
                return [{
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
                }]
                
        except Exception as e:
            print(f"Error processing book '{book.title}': {e}")
            return [{
                'original_title': book.title,
                'original_author': book.author,
                'original_isbn': book.isbn,
                'original_goodreads_id': book.goodreads_id,
                'found_title': None,
                'found_author': None,
                'format': None,
                'availability': 'Error',
                'detail_link': None,
                'branch_availability': None
            }]
    
    def check_books(self, books: List[Book], preferred_branch=None):
        """Check availability for a list of books using multithreading"""
        all_results = []
        
        print(f"Processing {len(books)} books with {self.max_workers} workers...")
        
        # Use ThreadPoolExecutor for thread-safe multithreading
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_book = {executor.submit(self.process_single_book, book): book for book in books}
            
            # Process completed tasks
            for future in as_completed(future_to_book):
                book = future_to_book[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    print(f"Error processing book {book.title}: {e}")
                    # Add error result
                    all_results.append({
                        'original_title': book.title,
                        'original_author': book.author,
                        'original_isbn': book.isbn,
                        'original_goodreads_id': book.goodreads_id,
                        'found_title': None,
                        'found_author': None,
                        'format': None,
                        'availability': 'Error',
                        'detail_link': None,
                        'branch_availability': None
                    })

                   
        
        return all_results
    
    def __del__(self):
        """Clean up driver pool"""
        if hasattr(self, 'driver_pool'):
            self.driver_pool.cleanup()

# --- New AlachuaCountyLibraryScraper ---
class AlachuaCountyLibraryScraper(LibraryScraperBase):
    def __init__(self, max_workers: int = 3):
        self.base_url = "https://catalog.aclib.us/search/searchresults.aspx"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.max_workers = max_workers
        self.last_request_time = {}
        self.request_lock = threading.Lock()
        self.min_delay = 1.0
        self.driver_pool = ThreadSafeSeleniumPool(max_workers)

    def _rate_limit(self, thread_id):
        with self.request_lock:
            current_time = time.time()
            if thread_id in self.last_request_time:
                time_since_last = current_time - self.last_request_time[thread_id]
                if time_since_last < self.min_delay:
                    time.sleep(self.min_delay - time_since_last)
            self.last_request_time[thread_id] = time.time()

    def build_search_query(self, title, author):
        # Return a dict of advanced search parameters for title and author
        return {
            'ctx': '1.1033.0.0.6',
            'type': 'Advanced',
            'term': title,
            'relation': 'ALL',
            'by': 'TI',
            'term2': author,
            'relation2': 'ALL',
            'by2': 'AU',
            'bool1': 'AND',
            'bool4': 'AND',
            'limit': 'TOM=*',
            'sort': 'RELEVANCE',
            'page': '0'
        }

    def search_book(self, book: Book):
        from urllib.parse import urlencode
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        thread_id = threading.current_thread().ident
        self._rate_limit(thread_id)
        title = book.title.strip().replace('"', '')
        author = book.author.strip().replace('"', '')
        params = self.build_search_query(title, author)
        url = f"{self.base_url}?{urlencode(params)}"
        driver = self.driver_pool.get_driver()
        if not driver:
            print("Could not get Selenium driver for ACLD search.")
            return None
        try:
            driver.get(url)
            # Wait for results to load (adjust selector as needed)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".content-module--search-result"))
                )
            except Exception as e:
                print(f"Timeout or error waiting for ACLD search results: {e}")
            html_content = driver.page_source
            return self.parse_search_results(html_content, book)
        finally:
            self.driver_pool.return_driver(driver)

    def parse_search_results(self, html_content, original_book: Book):
        # Save the HTML content to a file
        # with open("acld_search_debug.html", "w", encoding="utf-8") as f:
        #     f.write(html_content)
        # print("Saved HTML content to acld_search_debug.html and opening in browser...")
        # webbrowser.open("acld_search_debug.html")
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []
        # Polaris catalog: look for result rows
        # Rows is a list of all of the possible results
        rows = soup.find_all('div', class_='content-module content-module--search-result')
        for row in rows:
            try:
                # Find all the title parts
                title_div = row.find('div', class_="nsm-brief-primary-title-group")
                if title_div:
                    title_spans = title_div.find_all('span', class_="nsm-hit-text")
                    book_title = " ".join([span.get_text(strip=True) for span in title_spans]) if title_spans else "Unknown"
                else:
                    book_title = "Unknown"
                print(book_title)
                # Find the parent <a> tag for the detail link (adjust selector as needed)
                link_elem = row.find('a', href=True)
                detail_link = link_elem['href'] if link_elem else None
                if detail_link and not detail_link.startswith('http'):
                    detail_link = f"https://catalog.aclib.us{detail_link}"
                    
                # Author is not always present in the same div, so fallback to original
                book_author_div = row.find('div', class_="nsm-brief-secondary-title-group")
                if book_author_div:
                    book_author_spans = book_author_div.find_all('span', class_="nsm-hit-text")
                    book_author = " ".join([span.get_text(strip=True) for span in book_author_spans]) if book_author_spans else original_book.author
                else:
                    book_author = original_book.author
                print(book_author)
                # Format and availability are not always present in brief view
                book_format = None
                availability = "Unknown"
                results.append({
                    'title': book_title,
                    'author': book_author,
                    'format': book_format,
                    'availability': availability,
                    'detail_link': detail_link,
                    'branch_availability': None
                })
            except Exception as e:
                print(f"Error parsing ACLD result: {e}")
        return results

    def check_books(self, books: List[Book], preferred_branch=None):
        all_results = []
        print(f"Processing {len(books)} books with {self.max_workers} workers (Alachua County Library)...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_book = {executor.submit(self.process_single_book, book): book for book in books}
            for future in as_completed(future_to_book):
                book = future_to_book[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    print(f"Error processing book {book.title}: {e}")
                    all_results.append({
                        'original_title': book.title,
                        'original_author': book.author,
                        'original_isbn': book.isbn,
                        'original_goodreads_id': book.goodreads_id,
                        'found_title': None,
                        'found_author': None,
                        'format': None,
                        'availability': 'Error',
                        'detail_link': None,
                        'branch_availability': None
                    })
        return all_results

    def process_single_book(self, book: Book):
        try:
            print(f"Processing: {book.title} by {book.author} (ACLD)")
            search_results = self.search_book(book)
            if search_results:
                results = []
                for result in search_results:
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
                        'branch_availability': result['branch_availability']
                    }
                    results.append(result_data)
                return results
            else:
                return [{
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
                }]
        except Exception as e:
            print(f"Error processing book '{book.title}' (ACLD): {e}")
            return [{
                'original_title': book.title,
                'original_author': book.author,
                'original_isbn': book.isbn,
                'original_goodreads_id': book.goodreads_id,
                'found_title': None,
                'found_author': None,
                'format': None,
                'availability': 'Error',
                'detail_link': None,
                'branch_availability': None
            }]

    def __del__(self):
        if hasattr(self, 'driver_pool'):
            self.driver_pool.cleanup()

# Example usage
if __name__ == "__main__":
    start_time = time.time()
    
    # Load books from Goodreads CSV export
    print("Loading books from Goodreads CSV export...")
    goodreads_extractor = GoodreadsExtractor()
    csv_file = "goodreads_library_export.csv"
    books = goodreads_extractor.load_from_csv(csv_file)
    
    if not books:
        print("No books found in CSV. Using example books instead.")
        # Example books for testing
        books = [
            Book(title="The Nightingale", author="Kristin Hannah"),
            Book(title="Where the Crawdads Sing", author="Delia Owens"),
            Book(title="The Seven Husbands of Evelyn Hugo", author="Taylor Jenkins Reid"),
            Book(title="Educated", author="Tara Westover"),
            Book(title="The Silent Patient", author="Alex Michaelides")
        ]
    
    print(f"Found {len(books)} books to check")
    
    # --- Library system selection ---
    print("Select library system:")
    print("1. Palm Beach County Library (PBCLibrary)")
    print("2. Alachua County Library (ACLD)")
    choice = input("Enter 1 or 2: ").strip()
    if choice == "2":
        scraper = AlachuaCountyLibraryScraper(max_workers=3)
    else:
        scraper = PBCLibraryScraper(max_workers=3)
    
    try:
        # Check availability
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
                        print(f"  - {branch['branch']}")
            else:
                print("❌ Not found in library system")
        
        # Save results to JSON file
        with open('library_availability.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Results saved to library_availability.json")
        print(f"📚 Checked {len(books)} books, found {len([r for r in results if r['found_title']])} matches")
        
    except KeyboardInterrupt:
        print("\n⚠️  Script interrupted by user")
    finally:
        # Ensure cleanup
        if hasattr(scraper, 'driver_pool'):
            scraper.driver_pool.cleanup()
    
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Script execution time: {execution_time:.2f} seconds")