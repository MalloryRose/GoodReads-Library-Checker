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
        pass
        

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
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--log-level=3')
            chrome_options.add_argument('--silent')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
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
    def __init__(self, max_workers: int = 3):
        """Initialize common attributes for all library scrapers"""
        self.max_workers = max_workers
        self.driver_pool = ThreadSafeSeleniumPool(max_workers)
        
        # Thread-safe session for requests
        self.session = requests.Session()
        self.session.headers.update(self.get_default_headers())
        
        # Rate limiting
        self.last_request_time = {}
        self.request_lock = threading.Lock()
        self.min_delay = 1.5  # Minimum delay between requests in seconds
    
    def get_default_headers(self):
        """Return default headers for HTTP requests"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def _rate_limit(self, thread_id):
        """Implement rate limiting per thread"""
        with self.request_lock:
            current_time = time.time()
            if thread_id in self.last_request_time:
                time_since_last = current_time - self.last_request_time[thread_id]
                if time_since_last < self.min_delay:
                    time.sleep(self.min_delay - time_since_last)
            self.last_request_time[thread_id] = time.time()
    
    def clean_title(self, title):
        """Clean book title by removing parentheses content"""
        return re.sub(r"\s*\(.*?\)", "", title)
    
    def create_error_result(self, book: Book, error_type: str = 'Error'):
        """Create a standardized error result for a book"""
        return {
            'original_title': book.title,
            'original_author': book.author,
            'original_isbn': book.isbn,
            'original_goodreads_id': book.goodreads_id,
            'found_title': None,
            'found_author': None,
            'format': None,
            'availability': error_type,
            'detail_link': None,
            'branch_availability': None
        }
    
    def create_not_found_result(self, book: Book):
        """Create a standardized 'not found' result for a book"""
        return self.create_error_result(book, 'Not found')
    
    def create_success_result(self, book: Book, result: dict, availability: str = None, branches: list = None):
        """Create a standardized success result for a book"""
        return {
            'original_title': book.title,
            'original_author': book.author,
            'original_isbn': book.isbn,
            'original_goodreads_id': book.goodreads_id,
            'found_title': result['title'],
            'found_author': result['author'],
            'format': result['format'],
            'availability': availability or result['availability'],
            'detail_link': result['detail_link'],
            'branch_availability': branches
        }
    
    def process_single_book(self, book: Book):
        """Process a single book - shared implementation"""
        try:
            print(f"Processing: {book.title} by {book.author}")
            
            # Search for the book
            search_results = self.search_book(book)
            
            if search_results:
               # print(f"✅ Found {len(search_results)} result(s) for '{book.title}'")
                results = []
                for result in search_results:
                    # Handle loading availability - retry if needed
                    if result['availability'] == 'Loading':
                        print(f"Availability still loading for {book.title}, retrying...")
                        # Retry the search with additional wait time
                        retry_results = self.search_book_with_retry(book)
                        if retry_results:
                            result = retry_results[0]  # Use the retry result
                    
                    # Get detailed branch availability if needed
                    branch_availability = None
                    if result['availability'] == 'Available' and result['detail_link']:
                        branch_availability = self.get_branch_availability(result['detail_link'])

                    if branch_availability:
                      #  availability = branch_availability[0]
                        branches = branch_availability[1]
                    else:
                        
                        branches = None

                    availability = result['availability']
                    result_data = self.create_success_result(book, result, availability, branches)
                    results.append(result_data)
                
                return results
            else:
                print(f"❌ No results found for '{book.title}' by {book.author}")
                return [self.create_not_found_result(book)]
                
        except Exception as e:
            print(f"Error processing book '{book.title}': {e}")
            return [self.create_error_result(book)]
    
    def check_books(self, books: List[Book], preferred_branch=None):
        """Check availability for a list of books using multithreading - shared implementation"""
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
                    all_results.append(self.create_error_result(book))
        
        return all_results
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'driver_pool'):
            self.driver_pool.cleanup()
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()
    
    @abstractmethod
    def search_book(self, book: Book):
        """Search for a book - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def parse_search_results(self, html_content, original_book: Book):
        """Parse search results - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def build_search_query(self, title, author):
        """Build search query - must be implemented by subclasses"""
        pass
    
    def get_branch_availability(self, detail_link):
        """Get branch availability - optional override for subclasses"""
        return None

class PBCLibraryScraper(LibraryScraperBase):
    def __init__(self, max_workers: int = 3):
        super().__init__(max_workers)
        self.base_url = "https://pbclibrary.bibliocommons.com/v2/search"
        
        # Initialize session with better settings for reliability
        self.session.mount('https://', requests.adapters.HTTPAdapter(
            max_retries=3,
            pool_connections=10,
            pool_maxsize=10
        ))
        
    def build_search_query(self, title, author):
        """Build the BiblioCommons search query string"""
        # Clean up title and author - remove extra spaces and special characters
        title = title.strip().replace('"', '')
        author = author.strip().replace('"', '')
        
        # Build the query in BiblioCommons format
        query = f"(title:({title}) AND contributor:({author}))"
        return query
    
    
    def search_book(self, book: Book):
        """Search for a book and return availability information"""
        thread_id = threading.current_thread().ident
        super()._rate_limit(thread_id)
        
        title = super().clean_title(book.title)
        query = self.build_search_query(title, book.author)
        
        params = {
            'custom_edit': 'false',
            'query': query,
            'searchType': 'bl',
            'suppress': 'true'
        }
        
        # Add retry logic for better reliability
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(self.base_url, params=params, timeout=15)
                response.raise_for_status()
                
                return self.parse_search_results(response.text, book)
                
            except requests.RequestException as e:
                print(f"Error searching for '{book.title}' by {book.author} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
                else:
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
        # flexible approach to extract branch names
      
        lines = tbody_text.strip().split('\n')
        branch_names = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for common branch patterns
            # Pattern 1: Standard branch/library names (ends with BRANCH or LIBRARY)
            branch_match = re.match(r'^([A-Z][A-Z\s\-\.]+(?:BRANCH|LIBRARY))(?:\s*-\s*[A-Za-z\s]+)?$', line)
            if branch_match:
                branch_names.append(branch_match.group(1).strip())
                continue
            
            # Pattern 2: Special services like BOOKS BY MAIL, BOOKMOBILE
            service_match = re.match(r'^([A-Z][A-Z\s\-\.]+(?:BOOKS BY MAIL|BOOKMOBILE|MAIL|MOBILE))(?:\s*-\s*[A-Za-z\s]+)?$', line)
            if service_match:
                branch_names.append(service_match.group(1).strip())
                continue
            
            # Pattern 3: Any line that starts with capital letters and contains library-related keywords
            if re.match(r'^[A-Z][A-Z\s\-\.]+$', line) and any(keyword in line.upper() for keyword in ['BRANCH', 'LIBRARY', 'BOOKS', 'MAIL', 'MOBILE']):
                branch_names.append(line)
                continue
        
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

# --- New AlachuaCountyLibraryScraper ---
class AlachuaCountyLibraryScraper(LibraryScraperBase):
    def __init__(self, max_workers: int = 3):
        super().__init__(max_workers)
        self.base_url = "https://catalog.aclib.us/search/searchresults.aspx"
        
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
    
    def clean_title_text(self, title):
        """Clean and format title text by adding proper spacing"""
        if not title:
            return title
        
        # Remove extra whitespace
        title = ' '.join(title.split())
        
        # Common patterns to fix
        replacements = [
            # Fix common word boundaries
            (r'([a-z])([A-Z])', r'\1 \2'),  # Add space between camelCase
            (r'([a-z])(\d)', r'\1 \2'),     # Add space between letter and number
            (r'(\d)([A-Za-z])', r'\1 \2'),  # Add space between number and letter
            
            # Fix specific common patterns
            (r'Beforethe', 'Before the'),
            (r'Beforewe', 'Before we'),
            (r'Beforecoffee', 'Before coffee'),
            (r'Beforeforget', 'Before forget'),
            (r'Beforegoodbye', 'Before goodbye'),
            (r'Beforekindness', 'Before kindness'),
            (r'Beforethecoffeegetscold', 'Before the coffee gets cold'),
            (r'Beforewesaygoodbye', 'Before we say goodbye'),
            (r'Beforeweforgetkindness', 'Before we forget kindness'),
            
            # Fix other common patterns
            (r'([a-z])([A-Z][a-z])', r'\1 \2'),  # More camelCase fixes
            (r'([a-z])([A-Z]{2,})', r'\1 \2'),   # Fix ALL CAPS words
            
            # Clean up multiple spaces
            (r'\s+', ' '),
        ]
        
        for pattern, replacement in replacements:
            title = re.sub(pattern, replacement, title)
        
        # Capitalize first letter of each word (title case)
        title = title.title()
        
        # Fix common words that should be lowercase
        lowercase_words = ['a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'up', 'with']
        words = title.split()
        for i, word in enumerate(words):
            if word.lower() in lowercase_words and i > 0:  # Don't lowercase the first word
                words[i] = word.lower()
        
        return ' '.join(words)

    def search_book(self, book: Book):
        from urllib.parse import urlencode
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        thread_id = threading.current_thread().ident
        super()._rate_limit(thread_id)
        title = super().clean_title(book.title)
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
                
                # Wait for AJAX availability data to load
                # Look for loading images and wait for them to disappear
                wait = WebDriverWait(driver, 15)
                try:
                    # Wait for any loading images to disappear
                    wait.until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='ajax-loader']"))
                    )
                except:
                    # If no loading images found or timeout, continue anyway
                    pass
                
                # Additional wait to ensure availability data is loaded
                time.sleep(2)
                
            except Exception as e:
                print(f"Timeout or error waiting for ACLD search results: {e}")
            html_content = driver.page_source
            return self.parse_search_results(html_content, book)
        finally:
            self.driver_pool.return_driver(driver)
    
    def search_book_with_retry(self, book: Book):
        """Retry search with additional wait time for AJAX content"""
        from urllib.parse import urlencode
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        thread_id = threading.current_thread().ident
        super()._rate_limit(thread_id)
        title = super().clean_title(book.title)
        author = book.author.strip().replace('"', '')
        params = self.build_search_query(title, author)
        url = f"{self.base_url}?{urlencode(params)}"
        driver = self.driver_pool.get_driver()
        if not driver:
            print("Could not get Selenium driver for ACLD retry search.")
            return None
        try:
            driver.get(url)
            # Wait for results to load with extended timeout
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".content-module--search-result"))
                )
                
                # Extended wait for AJAX availability data to load
                wait = WebDriverWait(driver, 20)
                try:
                    # Wait for any loading images to disappear with longer timeout
                    wait.until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='ajax-loader']"))
                    )
                except:
                    # If still loading after extended wait, continue anyway
                    pass
                
                # Additional wait to ensure availability data is loaded
                time.sleep(5)
                
            except Exception as e:
                print(f"Timeout or error waiting for ACLD retry search results: {e}")
            html_content = driver.page_source
            return self.parse_search_results(html_content, book)
        finally:
            self.driver_pool.return_driver(driver)

    def parse_search_results(self, html_content, original_book: Book):
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []
        # Polaris catalog: look for result rows
        # Rows is a list of all of the possible results
        rows = soup.find_all('div', class_='content-module content-module--search-result')
        
        #Look at only first 3 results
        num_to_search = rows[:3] if len(rows) >= 3 else rows
        for row in num_to_search:
            try:    
                # Find all the title parts - try multiple selectors

                
                book_title = "Unknown"
                title_div = row.find('div', class_="nsm-brief-primary-title-group")
                if title_div:
                    test =  title_div.find('span', class_="nsm-short-item nsm-e135")
                    if test:
                        # Extract text from all nsm-hit-text spans within the nsm-short-item
                        hit_text_spans = test.find_all('span', class_="nsm-hit-text")
                        if hit_text_spans:
                            raw_title = " ".join([span.get_text(strip=True) for span in hit_text_spans])
                        else:
                            # Fallback to direct text if no hit-text spans found
                            raw_title = test.get_text(strip=True)
                        
                        # Clean up the title by adding proper spacing
                        cleaned_title = self.clean_title_text(raw_title)
                        print(f"Test title: {raw_title} -> {cleaned_title}")
                        book_title = cleaned_title
                    else:
                        title_spans = title_div.find_all('span', class_="nsm-hit-text")
                        if title_spans:
                            raw_title = " ".join([span.get_text(strip=True) for span in title_spans])
                            book_title = self.clean_title_text(raw_title)
                        else:
                            # Try alternative title selectors
                            title_link = title_div.find('a')
                            if title_link:
                                raw_title = title_link.get_text(strip=True)
                                book_title = self.clean_title_text(raw_title)
                
               
                # If still unknown, try the nsm-short-item nsm-e135 selector which seems to work
                if book_title == "Unknown":
                    # Try the specific selector that seems to work
                    test_elem = row.find('span', class_="nsm-short-item nsm-e135")
                    if test_elem:
                        # Extract text from all nsm-hit-text spans within the nsm-short-item
                        hit_text_spans = test_elem.find_all('span', class_="nsm-hit-text")
                        if hit_text_spans:
                            raw_title = " ".join([span.get_text(strip=True) for span in hit_text_spans])
                        else:
                            # Fallback to direct text if no hit-text spans found
                            raw_title = test_elem.get_text(strip=True)
                        
                        book_title = self.clean_title_text(raw_title)
                        print(f"Found title using nsm-short-item: {raw_title} -> {book_title}")
                    else:
                        book_title = original_book.title
                        print(f"Using original title for {original_book.title}: {book_title}")
                # Find the parent <a> tag for the detail link (adjust selector as needed)
                link_elem = row.find('a', class_="nsm-brief-action-link", href=True)
                detail_link = link_elem['href'] if link_elem else None
                if detail_link and not detail_link.startswith('http'):
                    print(detail_link)
                    detail_link = f"https://catalog.aclib.us{detail_link}"
                    
                # Author is not always present in the same div, so fallback to original
                book_author_div = row.find('div', class_="nsm-brief-secondary-title-group")
                if book_author_div:
                    book_author_spans = book_author_div.find_all('span', class_="nsm-hit-text")
                    book_author = " ".join([span.get_text(strip=True) for span in book_author_spans]) if book_author_spans else original_book.author
                else:
                    book_author = original_book.author
            
                # Format and availability are not always present in brief view
                
             # Extract availability information
                availability = "Unknown"
                
                availability_text = row.find_all('div', class_="nsm-brief-standard-group")
             #   print(f"len: {len(availability_text)}")
             

                for i in availability_text:
                    label_elem = i.find('span', class_='nsm-brief-label')
                    if not label_elem:
                        continue
                        
                    num_available = label_elem.get_text().strip()
                   
                    if num_available:
           
                        #print(test)
                        if "Availability" in num_available or "Available" in num_available:
                            availability_elem = i.find('span', class_='nsm-short-item')
                            
                            if not availability_elem:
                                # Check if there's still a loading image
                                loading_img = i.find('img', src=lambda x: x and 'ajax-loader' in x)
                                if loading_img:
                                    print(f"Availability still loading for {book_title}: {i}")
                                    availability = "Loading"  # Mark as loading instead of Unknown
                                else:
                                    print(f"Availability element not found for {book_title}: {i}")
                                break

                            # print(f"num available test: {num_available}")
                            # print(f"available test: {availability_elem}")
                            if availability_elem:
                                availability_text = availability_elem.get_text().strip()
                                # Handle different availability formats
                                if availability_text.isdigit():
                                    amount_available = availability_text[0]
                                    availability = "Unavailable" if amount_available == "0" else "Available"
                                elif "available" in availability_text.lower():
                                    availability = "Available"
                                elif "unavailable" in availability_text.lower() or "checked out" in availability_text.lower():
                                    availability = "Unavailable"
                                else:
                                    # Try to extract number from text like "2 of 5 available"
                                  
                                    match = re.search(r'(\d+)', availability_text)
                                    if match:
                                        amount = int(match.group(1))
                                        availability = "Available" if amount > 0 else "Unavailable"
                                    else:
                                        availability = "Unknown"
                                
                            break
                     
                
                book_format = "Unknown"

                # branches = row.find_all('tr', class_="location")
                # print(f"len: {len(branches)}")
                # for i in branches:
                #     print(i.get_text().strip())

               
                results.append({
                    'title': book_title,
                    'author': book_author,
                    'format': book_format,
                    'availability': availability,
                    'detail_link': detail_link,
                    'branch_availability': []
                })
            except Exception as e:
                print(f"Error parsing ACLD result: {e}")
        
        # If no results found, return a not found result
        if not results:
            results.append({
                'title': original_book.title,
                'author': original_book.author,
                'format': 'Unknown',
                'availability': 'Not found',
                'detail_link': None,
                'branch_availability': None
            })
        
        return results

    def get_branch_availability(self, detail_link):
        """Get branch availability for Alachua County Library using the detail link"""
        driver = self.driver_pool.get_driver()
        if not driver:
            return None
            
        try:
            driver.get(detail_link)
            
            wait = WebDriverWait(driver, 10)
            
            # Wait for the page content to load
            wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait for availability information to load
            try:
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".location, .branch, .library-location"))
                )
            except:
                # If no specific location elements found, continue anyway
                pass
            
            # Additional wait for AJAX content
            time.sleep(2)
            
            # Get the HTML content
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')
            
            branch_names = []
                 
            location_elems = soup.select('tr.location')
            if location_elems:
                for elem in location_elems:
                    branch_name = elem.get_text().strip()
                    if branch_name and len(branch_name) > 2:  # Filter out very short text
                        # Extract availability information from branch name
                        # Format: "Branch Name (X of Y available)"
                        match = re.search(r'\((\d+) of \d+ available\)', branch_name)
                        if match:
                    
                            available_count = int(match.group(1))
                            # Only add branches that have available books
                            if available_count > 0:
                                # Clean the branch name by removing the availability part
                                clean_branch_name = re.sub(r'\s*\(\d+ of \d+ available\)', '', branch_name).strip()
                                if clean_branch_name and clean_branch_name not in branch_names:
                                    branch_names.append(clean_branch_name)
                        else:
                            # If no availability pattern found, check if it contains library keywords
                            if any(keyword in branch_name.lower() for keyword in ['library', 'branch', 'center']):
                                if branch_name not in branch_names:
                                    branch_names.append(branch_name)
              
            
            # If no branches found with specific selectors, try a broader search
            if not branch_names:
                # Look for any text that might be a branch name
                all_text = soup.get_text()
                # Common Alachua County library branch names
                alachua_branches = [
                    'Headquarters Library',
                    'Millhopper Branch Library',
                    'Tower Road Branch Library',
                    'High Springs Branch Library',
                    'Newberry Branch Library',
                    'Hawthorne Branch Library',
                    'Cone Park Branch Library',
                    'Alachua Branch Library'
                ]
                
                for branch in alachua_branches:
                    if branch.lower() in all_text.lower():
                        branch_names.append(branch)
            
            results = []
            branch_info = []
            for branch in branch_names:
                branch_info.append({'branch': branch})

            if branch_info:
                results.append("Available")  # first index is availability
                print(f"Found {len(branch_info)} branches for availability check")
            else:
                results.append("Unavailable")
                print("No branches found for availability check")
            results.append(branch_info)  # second index is available branches
            return results
            
        except Exception as e:
            print(f"Availability check failed for {detail_link}: {e}")
            return None
        finally:
            # Always return driver to pool
            self.driver_pool.return_driver(driver)
       

    

# Example usage
if __name__ == "__main__":
    start_time = time.time()

      
    print("Default file or enter a CSV?")
    print("1. Default")
    print("2. Enter own CSV")
    choice = input("Enter 1 or 2: ").strip()
    csv_file = "data/goodreads_library_export.csv" if choice == "1" else input("Enter a CSV file: ").strip()


    
    # Load books from Goodreads CSV export
    print("Loading books from Goodreads CSV export...")
    goodreads_extractor = GoodreadsExtractor()
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
    max_workers = input("Enter number of workers: ").strip()
    if choice == "2":
        scraper = AlachuaCountyLibraryScraper(int(max_workers))
    else:
        scraper = PBCLibraryScraper(int(max_workers))
  


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
         
        file = "PBSC" if choice == "1" else "Alachua"
      

        with open(f'data/{file}_availability.json', 'w') as f:
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