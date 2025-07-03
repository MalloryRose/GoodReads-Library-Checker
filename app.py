import requests
import time
import csv
from urllib.parse import quote
from bs4 import BeautifulSoup
import json
from dataclasses import dataclass
from typing import List, Optional

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
        query = self.build_search_query(book.title, book.author)
        
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
        book_items = soup.find_all('div', class_='cp-search-result-item-content')
        
        for item in book_items:
            try:
                # Extract book title
                title_elem = item.find('span', class_='title-content')
                book_title = title_elem.get_text(strip=True) if title_elem else "Unknown"
                
                # Extract author
                author_elem = item.find('span', class_='cp-author-link')
                book_author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                
                # Extract availability information
                availability_elem = item.find('span', class_='cp-availability-status')
                availability = "Available"
                if availability_elem:
                    availability_text = availability_elem.get_text(strip=True)
                    if 'unavailable' in availability_elem.get('class', []):
                        availability = availability_text
                
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
    
    def get_branch_availability(self, detail_link):
        """Get detailed branch availability from the book's detail page"""
        if not detail_link:
            return None
            
        try:
            response = requests.get(detail_link, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for branch availability information
            # This selector may need adjustment based on actual HTML structure
            branch_info = []
            branches = soup.find_all('div', class_='cp-availability-branch')
            
            for branch in branches:
                branch_name = branch.find('span', class_='branch-name')
                branch_status = branch.find('span', class_='availability-status')
                
                if branch_name and branch_status:
                    branch_info.append({
                        'branch': branch_name.get_text(strip=True),
                        'status': branch_status.get_text(strip=True)
                    })
            
            return branch_info
            
        except requests.RequestException as e:
            print(f"Error getting branch availability: {e}")
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
                    print(f"  - {branch['branch']}: {branch['status']}")
        else:
            print("❌ Not found in library system")
    
    # Save results to JSON file
    with open('library_availability.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to library_availability.json")
    print(f"📚 Checked {len(books)} books, found {len([r for r in results if r['found_title']])} matches")