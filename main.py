import PyPDF2
import pandas as pd
import re

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
    return text

def parse_transactions(text):
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
    print("Parsed Transactions:\n", transactions)

    return transactions

def save_to_csv(transactions, csv_path):
    if transactions:  # Ensure transactions were found
        df = pd.DataFrame(transactions)
        df.to_csv(csv_path, index=False)
    else:
        print("No transactions found to save.")

# Main execution
pdf_path = 'pdf/mcb-usd-jul24.pdf'
csv_path = 'csv/mcb-usd-jul24.csv'

text = extract_text_from_pdf(pdf_path)
transactions = parse_transactions(text)
save_to_csv(transactions, csv_path)

print(f"Transactions have been successfully saved to {csv_path}")
