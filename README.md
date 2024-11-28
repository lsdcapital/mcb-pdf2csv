# MCB PDF to CSV Converter

A Python tool to convert MCB Bank statements from PDF to CSV format, with support for multiple accounts and currencies.

## Features

- Extracts transactions from MCB PDF bank statements
- Organizes CSVs by currency and account number
- Detects and prevents duplicate processing
- Combines transactions into date-ranged summary files
- Maintains Xero-compatible CSV format

## Directory Structure

```
.
├── pdf/                    # Place PDF statements here
├── csv/                    # Output directory
│   ├── zar/               # Currency-specific directory
│   │   └── 449933307/     # Account-specific directory
│   │       ├── mcb-449933307-zar-2023-09-29.csv
│   │       └── combined-2023-09-01-2023-10-31.csv
│   └── usd/
│       └── 449933307/
├── requirements.txt        # Python dependencies
└── processed_files.json    # Tracks processed files and metadata
```

## Installation

1. Clone the repository:
```bash
git clone git@github.com:lsdcapital/mcb-pdf2csv.git
cd mcb-pdf2csv
```

2. Create and activate virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate on macOS/Linux
source venv/bin/activate

# Activate on Windows
# venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Processing
```bash
python main.py
```
Processes any new PDF files found in the `pdf` directory.

### Command Line Options

- `--reprocess`: Process all PDFs, ignoring previous processing history
  ```bash
  python main.py --reprocess
  ```

- `--combine`: Create combined CSV files for each account/currency
  ```bash
  python main.py --combine
  ```

- `--debug`: Show detailed debugging information
  ```bash
  python main.py --debug
  ```

You can combine multiple flags:
```bash
python main.py --reprocess --combine
```

### Output Files

1. Individual Statement CSVs:
   - Named: `mcb-[account]-[currency]-[date].csv`
   - Located in: `csv/[currency]/[account]/`

2. Combined Statement CSVs:
   - Named: `combined-[firstdate]-[lastdate].csv`
   - Contains all transactions for an account/currency combination
   - Sorted by transaction date
   - Located in the same directory as individual CSVs

## Notes

- Place PDF statements in the `pdf` directory before running
- The script automatically creates necessary directories
- Duplicate detection prevents processing the same statement twice
- Combined CSVs maintain the original header format for Xero compatibility
- Always activate the virtual environment before running the script
