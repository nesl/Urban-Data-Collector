import argparse
import imaplib
import logging
import email
import csv
from email.header import decode_header
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv
from datetime import datetime
import os
import sys


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def connect_to_gmail_imap(user: str, password: str, inbox: str = "INBOX") -> imaplib.IMAP4_SSL:
    """Connect to Gmail IMAP server with error handling."""
    imap_url = 'imap.gmail.com'
    try:
        mail = imaplib.IMAP4_SSL(imap_url)
        mail.login(user, password)
        mail.select(inbox)
        return mail
    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP connection failed: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

def decode_header_value(header: str) -> str:
    """Safely decode email headers with proper encoding handling."""
    decoded_parts = []
    for part, encoding in decode_header(header):
        if isinstance(part, bytes):
            try:
                decoded_parts.append(part.decode(encoding or 'utf-8', 'replace'))
            except UnicodeDecodeError:
                decoded_parts.append(part.decode('latin-1', 'replace'))
        else:
            decoded_parts.append(str(part))
    return ' '.join(decoded_parts)

def parse_email_date(date_str: str) -> datetime:
    """Parse email date with fallback handling."""
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return datetime.now()

def extract_email_body(msg) -> str:
    """Extract text/plain body from multipart messages."""
    body = []
    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = str(part.get("Content-Disposition")).lower()

        if "attachment" in content_disposition:
            continue

        if content_type == "text/plain":
            try:
                charset = part.get_content_charset() or 'utf-8'
                payload = part.get_payload(decode=True)
                body.append(payload.decode(charset, 'replace'))
            except Exception as e:
                logging.warning(f"Error decoding part: {str(e)}")
                continue

    return '\n'.join(body) if body else ''

def fetch_emails(mail: imaplib.IMAP4_SSL, limit: int = None) -> list[dict]:
    """Fetch emails from server with improved error handling."""
    try:
        _, data = mail.search(None, "ALL")
        email_ids = data[0].split()[::-1] # Reverse to get most recent
        emails = []

        for idx, email_id in enumerate(email_ids):
            if limit and idx >= limit:
                break

            try:
                _, data = mail.fetch(email_id, "(RFC822)")
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = decode_header_value(msg.get("Subject", ""))
                sender = decode_header_value(msg.get("From", ""))
                date = parse_email_date(msg.get("Date", ""))
                body = extract_email_body(msg)

                emails.append({
                    "id": email_id.decode(),
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "date": date.isoformat()
                })

            except Exception as e:
                logging.error(f"Error processing email {email_id}: {str(e)}")
                continue

        return emails

    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP fetch error: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return []

def fetch_emails_by_uid(mail: imaplib.IMAP4_SSL, email_uids: list[int]) -> list[dict]:
    """Fetch stable IMAP UIDs without marking or deleting messages."""
    emails = []
    for email_uid in email_uids:
        try:
            status, data = mail.uid("fetch", str(email_uid), "(BODY.PEEK[])")
            if status != "OK" or not data or not isinstance(data[0], tuple):
                raise RuntimeError(f"Failed to fetch email UID {email_uid}")
            msg = email.message_from_bytes(data[0][1])
            parsed_date = parse_email_date(msg.get("Date", ""))
            emails.append({
                "id": str(email_uid),
                "message_id": decode_header_value(msg.get("Message-ID", "")),
                "subject": decode_header_value(msg.get("Subject", "")),
                "body": extract_email_body(msg),
                "sender": decode_header_value(msg.get("From", "")),
                "date": parsed_date.isoformat(),
            })
        except Exception as exc:
            logging.error(f"Error processing email UID {email_uid}: {exc}")
    return emails

def export_to_csv(emails: list[dict], filename: str, append: bool = False) -> None:
    """Export emails to CSV with proper file handling."""
    if not emails:
        logging.warning("No emails to export")
        return

    fieldnames = ["id", "subject", "sender", "date", "body"]
    mode = 'a' if append else 'w'
    write_header = not append or not os.path.exists(filename)

    try:
        with open(filename, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(emails)
        logging.info(f"Successfully exported {len(emails)} emails to {filename}")
    except IOError as e:
        logging.error(f"File error: {str(e)}")
    except Exception as e:
        logging.error(f"Export failed: {str(e)}")





def main():
    load_dotenv()
    username = os.getenv("GMAIL")
    password = os.getenv("PASSWORD")

    if not username or not password:
        logging.error("Missing GMAIL or PASSWORD in environment variables")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Gmail Email Client")
    parser.add_argument("-f", "--fields", nargs='+', 
                        choices=['subject', 'body', 'sender', 'date'], 
                        default=['subject'],
                        help="Fields to display")
    parser.add_argument("-c", "--csv", help="Export to CSV file")
    parser.add_argument("-a", "--append", action="store_true",
                        help="Append to CSV file")
    parser.add_argument("-d", "--delete", action="store_true",
                        help="Deprecated; fetched emails are always preserved")
    parser.add_argument("-l", "--limit", type=int,
                        help="Limit number of emails processed")
    args = parser.parse_args()

    try:
        with connect_to_gmail_imap(username, password) as mail:
            emails = fetch_emails(mail, args.limit)

            if args.csv:
                export_to_csv(emails, args.csv, args.append)
            else:
                for email_info in emails:
                    output = [str(email_info[field]) for field in args.fields]
                    print("\n".join(output))
                    print("-" * 50)

            if args.delete:
                logging.warning("--delete is deprecated and ignored; emails remain in the inbox")

    except KeyboardInterrupt:
        logging.info("Operation cancelled by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
