import PyPDF2
import pandas as pd
import re
import json
import os
import glob
from datetime import datetime
import argparse

def debug_print(message, args):
    if args.debug:
        print(message)

def extract_text_from_pdf(pdf_path, args):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
    
    debug_print(f"\nFirst 5000 characters of PDF text:", args)
    debug_print("-" * 50, args)
    debug_print(text[:5000], args)
    debug_print("-" * 50, args)
    return text

def parse_transactions(text, args):
    # Regular expressions to capture opening and closing balances
    opening_balance_pattern = re.compile(r'Opening Balance\s+(-?\d{1,3}(?:,\d{3})*\.\d{2})')
    closing_balance_pattern = re.compile(r'Closing Balance\s+(-?\d{1,3}(?:,\d{3})*\.\d{2})')

    # Extract opening and closing balances
    opening_balance_match = opening_balance_pattern.search(text)
    closing_balance_match = closing_balance_pattern.search(text)

    if not opening_balance_match or not closing_balance_match:
        print("Could not find opening or closing balances.")
        return []

    opening_balance = float(opening_balance_match.group(1).replace(',', ''))
    closing_balance = float(closing_balance_match.group(1).replace(',', ''))

    # Regular expression to match transaction lines and capture multi-line descriptions
    transaction_pattern = re.compile(
        r'(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(-?\d{1,3}(?:,\d{3})*\.\d{2})\s+(-?\d{1,3}(?:,\d{3})*\.\d{2})\s+(.+)'
    )

    transactions = []

    # Split the text into lines for easier processing
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if the line matches the transaction pattern
        match = transaction_pattern.match(line)
        if match:
            trans_date, value_date, transaction_value, unadjusted_balance, description = match.groups()

            # Append the next lines to the description until the next transaction is detected
            while i + 1 < len(lines) and not transaction_pattern.match(lines[i + 1]):
                i += 1
                description += " " + lines[i].strip()

            # Convert values to float, handling commas
            transaction_value = float(transaction_value.replace(',', ''))
            unadjusted_balance = float(unadjusted_balance.replace(',', ''))

            if not transactions:
                # This is the first transaction
                if unadjusted_balance == opening_balance + transaction_value:
                    transaction_value = abs(transaction_value)  # Credit
                else:
                    transaction_value = -abs(transaction_value)  # Debit
            else:
                last_balance = transactions[-1]['Unadjusted Balance']
                if unadjusted_balance < last_balance:
                    transaction_value = -abs(transaction_value)  # Debit
                else:
                    transaction_value = abs(transaction_value)  # Credit

            transactions.append({
                'Transaction Date': trans_date,
                'Value Date': value_date,
                'Description': description.strip(),
                'Transaction Value': transaction_value,
                'Unadjusted Balance': unadjusted_balance
            })

        i += 1

    # Validate the final balance
    if transactions and transactions[-1]['Unadjusted Balance'] != closing_balance:
        print("Warning: The calculated closing balance does not match the provided closing balance.")

    # Print transactions for debugging
    debug_print("Parsed Transactions:\n", args)
    debug_print(transactions, args)

    return transactions

def save_to_csv(transactions, csv_path, args):
    if transactions:  # Ensure transactions were found
        # Create currency directory if needed
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        df = pd.DataFrame(transactions)
        df.to_csv(csv_path, index=False)
        print(f"Successfully saved transactions to {csv_path}")
    else:
        print("No transactions found to save.")

def load_processed_files():
    tracker_file = 'processed_files.json'
    if os.path.exists(tracker_file):
        with open(tracker_file, 'r') as f:
            return json.load(f)
    return {}

def extract_statement_date(text):
    # Regular expression to find statement date range
    date_pattern = re.compile(r'From (\d{2}/\d{2}/\d{4}) to (\d{2}/\d{2}/\d{4})')
    match = date_pattern.search(text)
    
    if match:
        end_date_str = match.group(2)  # We'll use the end date as the statement date
        try:
            # Convert to datetime object for consistent formatting
            date_obj = datetime.strptime(end_date_str, '%d/%m/%Y')
            return date_obj.strftime('%Y-%m-%d')  # Return in ISO format
        except ValueError as e:
            print(f"Could not parse statement date: {end_date_str}")
            return None
    
    print("Could not find statement date in PDF")
    return None

def extract_account_info(text, args):
    # Regular expressions for account number and currency
    # Look for 12-digit number that's part of the IBAN
    account_pattern = re.compile(r'(\d{12})')
    # Look for 3-letter currency code on its own line
    currency_pattern = re.compile(r'\n([A-Z]{3})\n')
    
    # Try to find account number
    account_match = account_pattern.search(text)
    if not account_match:
        print("Could not find account number in PDF")
        account_number = None
    else:
        account_number = account_match.group(1)
        debug_print(f"Found account number: {account_number}", args)
    
    # Try to find currency
    currency_match = currency_pattern.search(text)
    if not currency_match:
        print("Could not find currency in PDF")
        currency = None
    else:
        currency = currency_match.group(1)
        debug_print(f"Found currency: {currency}", args)
    
    return account_number, currency

def is_duplicate_statement(statement_date, account_number, processed_files):
    if not statement_date or not account_number:
        return False
        
    for path, info in processed_files.items():
        if (info.get('statement_date') == statement_date and 
            info.get('account_number') == account_number):
            print(f"Found duplicate statement (date: {statement_date}, account: {account_number}) in {path}")
            return True
    return False

def is_duplicate_pdf(pdf_path, text, processed_files):
    """Check if this exact PDF has been processed before (even under a different name)"""
    # Take first 1000 characters as a fingerprint of the PDF
    text_fingerprint = text[:1000]
    
    for processed_path, info in processed_files.items():
        if processed_path == pdf_path:  # Skip self
            continue
        # If we find the same text fingerprint in a different file, it's a duplicate
        if info.get('text_fingerprint') == text_fingerprint:
            print(f"This appears to be the same PDF as {processed_path}")
            return True
    return False

def update_processed_files(pdf_path, csv_path, text, args):
    tracker_file = 'processed_files.json'
    processed = load_processed_files()
    
    statement_date = extract_statement_date(text)
    account_number, currency = extract_account_info(text, args)
    
    processed[pdf_path] = {
        'csv_path': csv_path,
        'processed_at': datetime.now().isoformat(),
        'statement_date': statement_date,
        'account_number': account_number,
        'currency': currency,
        'text_fingerprint': text[:1000]  # Store fingerprint for duplicate detection
    }
    
    with open(tracker_file, 'w') as f:
        json.dump(processed, f, indent=2)

def generate_csv_path(account_number, currency, statement_date):
    if not all([account_number, currency, statement_date]):
        return None
    # Remove any leading zeros from account number
    account = account_number.lstrip('0')
    # Generate filename
    filename = f"mcb-{account}-{currency.lower()}-{statement_date}.csv"
    # Create path with currency and account directories
    return os.path.join('csv', currency.lower(), account, filename)

def process_pdf(pdf_path, args):
    try:
        text = extract_text_from_pdf(pdf_path, args)
        
        # Extract metadata first
        statement_date = extract_statement_date(text)
        if not statement_date:
            return "Could not extract statement date"
            
        account_number, currency = extract_account_info(text, args)
        if not account_number or not currency:
            return "Could not extract account number or currency"
        
        # Check if this exact PDF was processed before (even under a different name)
        processed_files = load_processed_files()
        if is_duplicate_pdf(pdf_path, text, processed_files):
            return "Duplicate PDF content found under different name"
        
        # Check if already processed, unless reprocess flag is set
        if not args.reprocess and pdf_path in processed_files:
            return "Already processed"
        
        # Only check for duplicate statements if not reprocessing
        if not args.reprocess and is_duplicate_statement(statement_date, account_number, processed_files):
            return "Duplicate statement date for this account"
        
        # Generate CSV path
        csv_path = generate_csv_path(account_number, currency, statement_date)
        if not csv_path:
            return "Could not generate CSV path - missing required metadata"
            
        transactions = parse_transactions(text, args)
        if not transactions:
            return "No transactions found in PDF"
            
        save_to_csv(transactions, csv_path, args)
        
        # Update tracking file
        update_processed_files(pdf_path, csv_path, text, args)
        
        if statement_date:
            print(f"Statement date: {statement_date}")
        if account_number:
            print(f"Account: {account_number}")
        if currency:
            print(f"Currency: {currency}")
        print(f"Successfully processed {pdf_path} to {csv_path}")
        return True
    except Exception as e:
        return f"Error: {str(e)}"

def combine_account_csvs(processed_files):
    """Combine CSVs by account and currency"""
    # Group files by account and currency
    account_currency_files = {}
    for info in processed_files.values():
        csv_path = info.get('csv_path')
        if not csv_path or not os.path.exists(csv_path):
            continue
            
        # Extract account and currency from path
        parts = csv_path.split(os.sep)
        if len(parts) >= 4:  # csv/currency/account/file.csv
            currency = parts[-3]
            account = parts[-2]
            key = (currency, account)
            if key not in account_currency_files:
                account_currency_files[key] = []
            account_currency_files[key].append(csv_path)
    
    # Process each account/currency combination
    for (currency, account), csv_files in account_currency_files.items():
        if not csv_files:
            continue
            
        # Read the first file to get the header
        first_df = pd.read_csv(csv_files[0])
        header = list(first_df.columns)
        
        # Collect all transactions
        all_transactions = []
        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            all_transactions.append(df)
        
        if not all_transactions:
            continue
        
        # Combine all transactions
        combined_df = pd.concat(all_transactions, ignore_index=True)
        
        # Sort by transaction date
        combined_df['Transaction Date'] = pd.to_datetime(combined_df['Transaction Date'], format='%d/%m/%Y')
        combined_df = combined_df.sort_values('Transaction Date')
        
        # Get first and last dates for filename
        first_date = combined_df['Transaction Date'].min().strftime('%Y-%m-%d')
        last_date = combined_df['Transaction Date'].max().strftime('%Y-%m-%d')
        
        # Convert date back to original format for CSV
        combined_df['Transaction Date'] = combined_df['Transaction Date'].dt.strftime('%d/%m/%Y')
        
        # Ensure original column order
        combined_df = combined_df[header]
        
        # Save combined file with date range
        output_dir = os.path.join('csv', currency, account)
        combined_path = os.path.join(output_dir, f'combined-{first_date}-{last_date}.csv')
        combined_df.to_csv(combined_path, index=False)
        print(f"\nCreated combined statement for {currency}/{account} at {combined_path}")
        print(f"Total transactions: {len(combined_df)}")
        print(f"Date range: {first_date} to {last_date}")

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Convert MCB PDF statements to CSV')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--reprocess', action='store_true', help='Reprocess all files, ignoring processing history')
    parser.add_argument('--combine', action='store_true', help='Create combined CSVs for each account/currency')
    args = parser.parse_args()
    
    # Create base pdf and csv directories
    os.makedirs('pdf', exist_ok=True)
    os.makedirs('csv', exist_ok=True)
    
    # Check for previously processed files
    processed_files = load_processed_files()
    if processed_files and not args.reprocess:
        print("\nNote: Some files have been previously processed. Use --reprocess flag to reprocess all files.")
    
    # Process all PDFs in the pdf directory
    pdf_files = glob.glob('pdf/*.pdf')
    if not pdf_files:
        print("\nNo PDF files found in pdf directory")
        return
        
    print(f"\nFound {len(pdf_files)} PDF files")
    successful = 0
    skipped = {}  # Track reasons for skipped files
    
    for pdf_path in pdf_files:
        result = process_pdf(pdf_path, args)
        if isinstance(result, str):
            reason = result
            if reason not in skipped:
                skipped[reason] = []
            skipped[reason].append(pdf_path)
        elif result:
            successful += 1
    
    print(f"\nProcessed {successful} out of {len(pdf_files)} files successfully")
    if skipped:
        print("\nSkipped files by reason:")
        for reason, files in skipped.items():
            print(f"\n{reason}:")
            for file in files:
                print(f"  - {file}")
                
    # Create combined CSVs if requested
    if args.combine:
        combine_account_csvs(load_processed_files())

if __name__ == "__main__":
    main()
