# Project Brief: GoodReads Library Checker

## Project Overview
A Python-based tool that automatically checks the availability of books from a user's Goodreads "Want to Read" list across multiple library systems. The tool provides a comprehensive solution for book lovers to discover which books from their reading list are available at their local libraries.

## Core Requirements

### Primary Goals
1. **Automated Book Availability Checking**: Check availability of books from Goodreads "Want to Read" list in multiple library systems
2. **Multi-Library Support**: Support for Palm Beach County Library (BiblioCommons) and Alachua County Library (Polaris)
3. **High Performance**: Multithreaded processing for efficient, fast book checking
4. **User-Friendly Interface**: Both command-line and GUI interfaces
5. **Detailed Results**: Show availability status and branch-specific information

### Functional Requirements
- Import books from Goodreads CSV export
- Search multiple library catalogs simultaneously
- Display availability status (Available/Unavailable)
- Show branch-specific availability where supported
- Export results in JSON format
- Rate limiting to respect library servers
- Error handling and recovery
- Thread-safe operations

### Technical Requirements
- Python 3.x compatibility
- Selenium WebDriver for web scraping
- BeautifulSoup for HTML parsing
- Multithreading for concurrent processing
- JSON output format
- GUI using tkinter
- Rate limiting and error handling

## Success Criteria
1. Successfully check availability across multiple library systems
2. Process books efficiently with multithreading
3. Provide accurate availability information
4. Handle errors gracefully without crashing
5. Respect library server limits
6. Provide both CLI and GUI interfaces

## Project Scope
- **In Scope**: Goodreads integration, multi-library checking, GUI interface, JSON export
- **Out of Scope**: Direct library hold placement, email notifications, book recommendations
- **Future Enhancements**: Email notifications, scheduling, more library systems

## Key Constraints
- Must respect library server rate limits
- Must handle network timeouts gracefully
- Must work with existing library catalog systems
- Must maintain thread safety for concurrent operations 