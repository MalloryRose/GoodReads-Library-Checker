# System Patterns: GoodReads Library Checker

## Architecture Overview

The system follows a modular, object-oriented architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GUI Layer     │    │  Scraper Layer  │    │  Data Layer     │
│   (tkinter)     │◄──►│  (Selenium)     │◄──►│  (CSV/JSON)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Thread Pool    │    │  Rate Limiting  │    │  Error Handling │
│  Management     │    │  & Safety       │    │  & Recovery     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Key Design Patterns

### 1. Abstract Factory Pattern
- `LibraryScraperBase` serves as the abstract base class
- `PBCLibraryScraper` and `AlachuaCountyLibraryScraper` are concrete implementations
- Allows easy addition of new library systems

### 2. Thread Pool Pattern
- `ThreadSafeSeleniumPool` manages WebDriver instances
- Each thread gets its own WebDriver for isolation
- Automatic cleanup and resource management

### 3. Strategy Pattern
- Different search strategies for different library systems
- `build_search_query()` method varies by implementation
- `parse_search_results()` handles different HTML structures

### 4. Observer Pattern (GUI)
- Queue-based communication between worker threads and GUI
- Real-time updates without blocking the UI
- Event-driven result display

## Component Relationships

### Core Components

#### 1. Data Classes
```python
@dataclass
class Book:
    title: str
    author: str
    isbn: Optional[str] = None
    goodreads_id: Optional[str] = None
```

#### 2. Extractor Layer
- `GoodreadsExtractor`: Handles CSV import and parsing
- Filters for "Want to Read" shelf
- Converts CSV rows to Book objects

#### 3. Scraper Layer
- `LibraryScraperBase`: Abstract base class
- `PBCLibraryScraper`: Palm Beach County implementation
- `AlachuaCountyLibraryScraper`: Alachua County implementation

#### 4. Thread Management
- `ThreadSafeSeleniumPool`: Manages WebDriver instances
- Thread-safe operations with proper locking
- Automatic resource cleanup

#### 5. GUI Layer
- `LibraryScraperGUI`: Main GUI class
- Thread-safe communication via Queue
- Real-time progress updates

## Critical Implementation Paths

### 1. Book Processing Flow
```
CSV Import → Book Objects → Thread Pool → Library Search → Parse Results → JSON Output
```

### 2. Thread Safety Flow
```
Thread Request → Get Driver → Process Book → Return Driver → Update Results
```

### 3. Error Handling Flow
```
Exception → Log Error → Create Error Result → Continue Processing → Report Status
```

## Technical Decisions

### 1. Selenium vs Requests
- **Chosen**: Selenium for complex JavaScript-heavy library catalogs
- **Reason**: Library catalogs often require JavaScript execution
- **Trade-off**: Higher resource usage but better compatibility

### 2. Multithreading vs Multiprocessing
- **Chosen**: Multithreading with ThreadPoolExecutor
- **Reason**: I/O-bound operations benefit from threading
- **Trade-off**: GIL limitations but simpler resource management

### 3. Rate Limiting Strategy
- **Chosen**: Per-thread rate limiting with minimum delays
- **Reason**: Prevents overwhelming library servers
- **Implementation**: `_rate_limit()` method with thread-specific timing

### 4. Error Recovery
- **Chosen**: Graceful degradation with error results
- **Reason**: Individual failures shouldn't crash entire process
- **Implementation**: `create_error_result()` method

## Data Flow Patterns

### 1. Input Processing
```
CSV File → GoodreadsExtractor → List[Book] → Scraper
```

### 2. Search Processing
```
Book → build_search_query() → Selenium Search → HTML Response → parse_search_results()
```

### 3. Result Processing
```
Search Results → Branch Availability Check → JSON Result → GUI Update
```

## Safety Patterns

### 1. Resource Management
- WebDriver pool with automatic cleanup
- Thread-safe driver allocation
- Proper exception handling in cleanup

### 2. Rate Limiting
- Per-thread minimum delays
- Configurable delay settings
- Thread-safe timing mechanisms

### 3. Error Isolation
- Individual book failures don't affect others
- Comprehensive error logging
- Graceful degradation with error results

## Performance Patterns

### 1. Concurrent Processing
- Configurable thread pool size
- Parallel book checking
- Shared resource management

### 2. Memory Management
- Reusable WebDriver instances
- Automatic cleanup of resources
- Efficient data structures

### 3. Network Optimization
- Session reuse for HTTP requests
- Rate limiting to prevent server overload
- Timeout handling for network issues 