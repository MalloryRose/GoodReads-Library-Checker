import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import json
import os
from datetime import datetime
import webbrowser
from library_scraper_threaded import GoodreadsExtractor, PBCLibraryScraper, Book

class LibraryScraperGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("📚 Library Availability Checker")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Configure style
        self.setup_styles()
        
        # Initialize variables
        self.csv_path = tk.StringVar()
        self.max_workers = tk.IntVar(value=3)
        self.min_delay = tk.DoubleVar(value=1.0)
        self.is_running = False
        self.results = []
        
        # Queue for thread communication
        self.queue = queue.Queue()
        
        # Create GUI elements
        self.create_widgets()
        
        # Start queue processing
        self.process_queue()
        
    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        
        # Configure colors and fonts
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 10, 'bold'))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Warning.TLabel', foreground='orange')
        style.configure('Custom.TButton', background='green', foreground='black', font=('Arial', 12, 'bold'))
        
    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="📚 Library Availability Checker", 
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # File Selection Section
        self.create_file_section(main_frame, row=1)
        
        # Settings Section
        self.create_settings_section(main_frame, row=2)
        
        # Control Buttons
        self.create_control_section(main_frame, row=3)
        
        # Progress Section
        self.create_progress_section(main_frame, row=4)
        
        # Results Section
        self.create_results_section(main_frame, row=5)
        
        # Status Bar
        self.create_status_bar(main_frame, row=6)
        
    def create_file_section(self, parent, row):
        """Create file selection section"""
        file_frame = ttk.LabelFrame(parent, text="📁 Goodreads CSV File", padding="10")
        file_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text="CSV File:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.file_entry = ttk.Entry(file_frame, textvariable=self.csv_path, width=50)
        self.file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.browse_button = ttk.Button(file_frame, text="Browse...", command=self.browse_file, style='Custom.TButton')
        self.browse_button.grid(row=0, column=2, sticky=tk.W)
        
        # Instructions
        instructions = "Export your library from Goodreads: Settings → Import/Export → Export Library"
        ttk.Label(file_frame, text=instructions, foreground='gray').grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
        
    def create_settings_section(self, parent, row):
        """Create settings section"""
        settings_frame = ttk.LabelFrame(parent, text="⚙️ Settings", padding="10")
        settings_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Max Workers
        ttk.Label(settings_frame, text="Concurrent Workers:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        workers_spin = ttk.Spinbox(settings_frame, from_=1, to=5, textvariable=self.max_workers, width=10)
        workers_spin.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Rate Limit Delay
        ttk.Label(settings_frame, text="Request Delay (sec):").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        delay_spin = ttk.Spinbox(settings_frame, from_=0.5, to=5.0, increment=0.5, textvariable=self.min_delay, width=10)
        delay_spin.grid(row=0, column=3, sticky=tk.W)
        
    def create_control_section(self, parent, row):
        """Create control buttons section"""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=row, column=0, columnspan=3, pady=(0, 10))
        
        self.start_button = ttk.Button(control_frame, text="▶️ Check Books", command=self.start_checking, style='Custom.TButton')
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = ttk.Button(control_frame, text="⏹️ Stop", command=self.stop_checking, state=tk.DISABLED, style='Custom.TButton')
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_button = ttk.Button(control_frame, text="🗑️ Clear Results", command=self.clear_results, style='Custom.TButton')
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.save_button = ttk.Button(control_frame, text="💾 Save Results", command=self.save_results, state=tk.DISABLED, style='Custom.TButton')
        self.save_button.pack(side=tk.LEFT)
        
    def create_progress_section(self, parent, row):
        """Create progress tracking section"""
        progress_frame = ttk.LabelFrame(parent, text="📊 Progress", padding="10")
        progress_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        self.progress_var = tk.StringVar(value="Ready to check books...")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var)
        self.progress_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
    def create_results_section(self, parent, row):
        """Create results display section"""
        results_frame = ttk.LabelFrame(parent, text="📋 Results", padding="10")
        results_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(1, weight=1)
        parent.rowconfigure(row, weight=1)
        
        # Results summary
        self.summary_var = tk.StringVar(value="No results yet")
        self.summary_label = ttk.Label(results_frame, textvariable=self.summary_var, style='Header.TLabel')
        self.summary_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        # Results text area with scrollbar
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, height=15, width=80)
        self.results_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure text tags for colored output
        self.results_text.tag_configure("available", foreground="green")
        self.results_text.tag_configure("unavailable", foreground="red")
        self.results_text.tag_configure("not_found", foreground="orange")
        self.results_text.tag_configure("header", font=("Arial", 10, "bold"))
        self.results_text.tag_configure("link", foreground="blue", underline=True)
        
    def create_status_bar(self, parent, row):
        """Create status bar"""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
    def browse_file(self):
        """Open file browser dialog"""
        filename = filedialog.askopenfilename(
            title="Select Goodreads CSV Export",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.csv_path.set(filename)
            self.status_var.set(f"Selected: {os.path.basename(filename)}")
            
    def validate_inputs(self):
        """Validate user inputs before starting"""
        if not self.csv_path.get():
            messagebox.showerror("Error", "Please select a Goodreads CSV file")
            return False
            
        if not os.path.exists(self.csv_path.get()):
            messagebox.showerror("Error", "Selected CSV file does not exist")
            return False
            
        return True
        
    def start_checking(self):
        """Start the book checking process"""
        if not self.validate_inputs():
            return
            
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.DISABLED)
        
        # Clear previous results
        self.results = []
        self.results_text.delete(1.0, tk.END)
        
        # Start processing thread
        thread = threading.Thread(target=self.check_books_thread, daemon=True)
        thread.start()
        
    def stop_checking(self):
        """Stop the book checking process"""
        self.is_running = False
        self.queue.put(("status", "Stopping... please wait"))
        
    def clear_results(self):
        """Clear all results"""
        self.results = []
        self.results_text.delete(1.0, tk.END)
        self.summary_var.set("No results yet")
        self.progress_var.set("Ready to check books...")
        self.progress_bar['value'] = 0
        self.save_button.config(state=tk.DISABLED)
        
    def check_books_thread(self):
        """Main processing thread"""
        try:
            # Load books from CSV
            self.queue.put(("progress", "Loading books from CSV...", 0))
            
            extractor = GoodreadsExtractor()
            books = extractor.load_from_csv(self.csv_path.get())
            
            if not books:
                self.queue.put(("error", "No books found in CSV file. Make sure it contains 'Want to Read' books."))
                return
                
            self.queue.put(("progress", f"Found {len(books)} books to check", 0))
            
            # Initialize scraper
            scraper = PBCLibraryScraper(max_workers=self.max_workers.get())
            scraper.min_delay = self.min_delay.get()
            
            # Process books with progress updates
            total_books = len(books)
            processed = 0
            
            for i, book in enumerate(books):
                if not self.is_running:
                    break
                    
                self.queue.put(("progress", f"Checking: {book.title} by {book.author}", 
                              int((i / total_books) * 100)))
                
                # Process single book
                result = scraper.process_single_book(book)
                if result:
                    self.results.extend(result)
                    self.queue.put(("result", result[0]))
                
                processed += 1
                
            # Cleanup
            scraper.driver_pool.cleanup()
            
            if self.is_running:
                self.queue.put(("complete", f"Completed! Checked {processed} books"))
            else:
                self.queue.put(("stopped", f"Stopped. Processed {processed}/{total_books} books"))
                
        except Exception as e:
            self.queue.put(("error", f"Error occurred: {str(e)}"))
            
    def process_queue(self):
        """Process messages from worker thread"""
        try:
            while True:
                msg_type, *args = self.queue.get_nowait()
                
                if msg_type == "progress":
                    message, progress = args
                    self.progress_var.set(message)
                    self.progress_bar['value'] = progress
                    self.status_var.set(message)
                    
                elif msg_type == "result":
                    self.display_result(args[0])
                    
                elif msg_type == "complete":
                    self.on_complete(args[0])
                    
                elif msg_type == "stopped":
                    self.on_stopped(args[0])
                    
                elif msg_type == "error":
                    self.on_error(args[0])
                    
                elif msg_type == "status":
                    self.status_var.set(args[0])
                    
        except queue.Empty:
            pass
            
        # Schedule next check
        self.root.after(100, self.process_queue)
        
    def display_result(self, result):
        """Display a single book result"""
        text = self.results_text
        
        # Book header
        header = f"\n--- {result['original_title']} by {result['original_author']} ---\n"
        text.insert(tk.END, header, "header")
        
        if result['found_title']:
            # Found book
            text.insert(tk.END, f"Found: {result['found_title']} by {result['found_author']}\n")
            text.insert(tk.END, f"Format: {result['format']}\n")
            
            # Availability with color coding
            availability = result['availability']
            if availability == "Available":
                text.insert(tk.END, f"Status: {availability}\n", "available")
            elif availability == "Unavailable":
                text.insert(tk.END, f"Status: {availability}\n", "unavailable")
            else:
                text.insert(tk.END, f"Status: {availability}\n", "not_found")
                
            # Branch availability
            if result['branch_availability']:
                text.insert(tk.END, "Available at:\n")
                for branch in result['branch_availability']:
                    text.insert(tk.END, f"  • {branch['branch']}\n")
                    
            # Link
            if result['detail_link']:
                text.insert(tk.END, f"Link: {result['detail_link']}\n", "link")
                
        else:
            text.insert(tk.END, "❌ Not found in library system\n", "not_found")
            
        # Scroll to bottom
        text.see(tk.END)
        
        # Update summary
        self.update_summary()
        
    def update_summary(self):
        """Update results summary"""
        if not self.results:
            return
            
        total = len(self.results)
        available = len([r for r in self.results if r['availability'] == 'Available'])
        unavailable = len([r for r in self.results if r['availability'] == 'Unavailable'])
        not_found = len([r for r in self.results if r['availability'] == 'Not found'])
        
        summary = f"📊 Summary: {total} books checked • {available} available • {unavailable} unavailable • {not_found} not found"
        self.summary_var.set(summary)
        
    def on_complete(self, message):
        """Handle completion"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.NORMAL)
        self.progress_var.set(message)
        self.progress_bar['value'] = 100
        self.status_var.set("Complete ✅")
        
        # Show completion message
        messagebox.showinfo("Complete", message)
        
    def on_stopped(self, message):
        """Handle stop"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        if self.results:
            self.save_button.config(state=tk.NORMAL)
        self.progress_var.set(message)
        self.status_var.set("Stopped ⏹️")
        
    def on_error(self, message):
        """Handle error"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set("Error occurred")
        self.status_var.set("Error ❌")
        
        messagebox.showerror("Error", message)
        
    def save_results(self):
        """Save results to JSON file"""
        if not self.results:
            messagebox.showwarning("Warning", "No results to save")
            return
            
        filename = filedialog.asksaveasfilename(
            title="Save Results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialname=f"library_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Success", f"Results saved to {os.path.basename(filename)}")
                self.status_var.set(f"Saved: {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {str(e)}")
                
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

def main():
    """Main entry point"""
    try:
        app = LibraryScraperGUI()
        app.run()
    except Exception as e:
        messagebox.showerror("Fatal Error", f"Application failed to start: {str(e)}")

if __name__ == "__main__":
    main()