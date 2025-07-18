
import unittest
from library_scraper import Book, GoodreadsExtractor, PBCLibraryScraper

class TestGoodreadsExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = GoodreadsExtractor()

    def test_book_creation(self):
        book = Book(title="Test Book", author="Author Name", isbn="1234567890", goodreads_id="9999")
        self.assertEqual(book.title, "Test Book")
        self.assertEqual(book.author, "Author Name")
        self.assertEqual(str(book), "Test Book by Author Name")

    def test_clean_csv_title(self):
        books = self.extractor.load_from_csv("test_goodreads.csv")
        self.assertIsInstance(books, list)
        if books:
            self.assertIsInstance(books[0], Book)
            self.assertTrue(books[0].title)

class TestPBCLibraryScraper(unittest.TestCase):

    def setUp(self):
        self.scraper = PBCLibraryScraper()

    def test_clean_title(self):
        raw_title = "The Book Title (Special Edition)"
        cleaned = self.scraper.clean_title(raw_title)
        self.assertEqual(cleaned, "The Book Title")

    def test_build_search_query(self):
        title = "Educated"
        author = "Tara Westover"
        expected = "(title:(Educated) AND contributor:(Tara Westover))"
        self.assertEqual(self.scraper.build_search_query(title, author), expected)

    def test_extract_branch_names(self):
        tbody_text = """
        WEST BOCA BRANCH - Available
        WEST BOYNTON BRANCH - On shelf
        TEQUESTA BRANCH - On hold
        """
        branches = self.scraper.extract_branch_names(tbody_text)
        self.assertIn("WEST BOCA BRANCH", branches)
        self.assertIn("WEST BOYNTON BRANCH", branches)
        self.assertIn("TEQUESTA BRANCH", branches)

if __name__ == '__main__':
    unittest.main()
