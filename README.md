# 📚 Palm Beach County Library Availability Checker

A Python tool that automatically checks the availability of books from your Goodreads "Want to Read" list in the Palm Beach County Library system. Features multithreaded processing for fast, efficient book checking.

## ✨ Features

- **Goodreads Integration**: Import books directly from your Goodreads CSV export
- **Multithreaded Processing**: Check multiple books simultaneously for faster results
- **Detailed Availability**: Shows not just availability, but which library branches have copies
- **Multiple Formats**: Supports books, audiobooks, eBooks, and other formats
- **Rate Limiting**: Built-in protection against overwhelming the library's servers
- **JSON Export**: Save results for later analysis or integration with other tools
- **Thread-Safe**: Robust error handling and resource management

## 🚀 Quick Start

### Prerequisites

```bash
pip install requests beautifulsoup4 selenium concurrent.futures
```

You'll also need to install ChromeDriver for Selenium:
- Download from [ChromeDriver](https://chromedriver.chromium.org/)
- Ensure it's in your PATH or in the same directory as the script

### Basic Usage

1. **Export your Goodreads library**:
   - Go to Goodreads → Settings → Import/Export
   - Export your library as CSV
   - Save as `goodreads_library_export.csv`

2. **Run the script**:
   ```bash
   python library_scraper.py
   ```

3. **View results**:
   - Check console output for real-time results
   - Open `library_availability.json` for detailed data

## 📖 Detailed Usage

### Using Your Goodreads CSV Export

```python
from library_scraper import GoodreadsExtractor, PBCLibraryScraper

# Load books from your Goodreads export
extractor = GoodreadsExtractor()
books = extractor.load_from_csv("goodreads_library_export.csv")

# Check availability with 3 concurrent workers
scraper = PBCLibraryScraper(max_workers=3)
results = scraper.check_books(books)
```

### Manual Book List

```python
from library_scraper import Book, PBCLibraryScraper

# Create book list manually
books = [
    Book(title="The Nightingale", author="Kristin Hannah"),
    Book(title="Where the Crawdads Sing", author="Delia Owens"),
    Book(title="Educated", author="Tara Westover")
]

# Check availability
scraper = PBCLibraryScraper(max_workers=2)
results = scraper.check_books(books)
```

## ⚙️ Configuration

### Adjusting Performance

```python
# Conservative (slower but safer)
scraper = PBCLibraryScraper(max_workers=2)

# Balanced (recommended)
scraper = PBCLibraryScraper(max_workers=3)

# Aggressive (faster but may trigger rate limits)
scraper = PBCLibraryScraper(max_workers=5)
```

### Rate Limiting

The scraper includes built-in rate limiting with a 1-second minimum delay between requests per thread. You can adjust this:

```python
scraper = PBCLibraryScraper(max_workers=3)
scraper.min_delay = 2.0  # 2 seconds between requests
```

## 📊 Output Format

### Console Output
```
Processing: The Nightingale by Kristin Hannah
Processing: Where the Crawdads Sing by Delia Owens

--- The Nightingale by Kristin Hannah ---
Found: The Nightingale by Kristin Hannah
Format: Book
Availability: Available
Link: https://pbclibrary.bibliocommons.com/item/show/...
Branch availability:
  - WEST PALM BEACH BRANCH
  - BOCA RATON BRANCH
```

### JSON Output Structure
```json
[
  {
    "original_title": "The Nightingale",
    "original_author": "Kristin Hannah",
    "original_isbn": "9781250080400",
    "original_goodreads_id": "21853621",
    "found_title": "The Nightingale",
    "found_author": "Kristin Hannah",
    "format": "Book",
    "availability": "Available",
    "detail_link": "https://pbclibrary.bibliocommons.com/item/show/...",
    "branch_availability": [
      {"branch": "WEST PALM BEACH BRANCH"},
      {"branch": "BOCA RATON BRANCH"}
    ]
  }
]
```

## 🔧 Advanced Features

### Custom Search Queries

The scraper automatically builds optimized search queries, but you can customize the search logic:

```python
# Modify the build_search_query method for custom search logic
def build_search_query(self, title, author):
    # Custom implementation
    return f"(title:({title}) AND contributor:({author}))"
```

### Branch Filtering

While not implemented in the current version, you can filter results by preferred branches:

```python
# Future feature
results = scraper.check_books(books, preferred_branch="West Palm Beach")
```

## 🛠️ Technical Details

### Architecture

- **GoodreadsExtractor**: Handles CSV import and data parsing
- **PBCLibraryScraper**: Main scraping logic with multithreading
- **ThreadSafeSeleniumPool**: Manages WebDriver instances safely
- **Book/LibraryResult**: Data classes for type safety

### Multithreading Safety

- **Driver Pool**: Each thread gets its own WebDriver instance
- **Rate Limiting**: Thread-safe request timing
- **Error Handling**: Individual thread failures don't crash the entire process
- **Resource Management**: Automatic cleanup of WebDriver instances

### Performance Considerations

- **Memory Usage**: Each WebDriver instance uses ~50-100MB RAM
- **Network Load**: Respects server limits with built-in rate limiting
- **Timeout Management**: All operations have timeouts to prevent hanging
- **Connection Pooling**: Reuses HTTP connections for efficiency

## 🚨 Troubleshooting

### Common Issues

**ChromeDriver not found**:
```bash
# Install ChromeDriver
brew install chromedriver  # macOS
# Or download from https://chromedriver.chromium.org/
```

**Rate limiting errors**:
```python
# Reduce worker count
scraper = PBCLibraryScraper(max_workers=2)
# Increase delay
scraper.min_delay = 2.0
```

**Memory issues**:
```python
# Reduce WebDriver pool size
scraper = PBCLibraryScraper(max_workers=2)
```

**CSV parsing errors**:
- Ensure CSV is from Goodreads export
- Check file encoding (should be UTF-8)
- Verify file path is correct

### Debug Mode

Enable verbose logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📋 Requirements

### Python Packages
```
requests>=2.25.0
beautifulsoup4>=4.9.0
selenium>=4.0.0
```

### System Requirements
- Python 3.7+
- Google Chrome browser
- ChromeDriver (matching your Chrome version)
- 4GB+ RAM recommended for multithreading

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/library-scraper.git
cd library-scraper

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for personal use only. Please respect the library's terms of service and avoid overwhelming their servers with excessive requests. The scraper includes rate limiting to be respectful of the library's resources.

## 🔮 Future Enhancements

- [ ] Support for multiple library systems
- [ ] GUI interface
- [ ] Email notifications for available books
- [ ] Integration with library hold systems
- [ ] Book recommendation based on availability
- [ ] Export to other formats (Excel, PDF)
- [ ] Scheduling for regular checks

## 📞 Support

- **Issues**: Report bugs via GitHub Issues
- **Questions**: Check the FAQ or create a discussion
- **Feature Requests**: Submit via GitHub Issues with the enhancement label

---

**Happy reading! 📚✨**