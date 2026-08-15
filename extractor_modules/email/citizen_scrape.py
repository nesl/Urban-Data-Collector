import os
import re
import time
import logging
import random
from datetime import datetime, timedelta

import imaplib
import email
from email.header import decode_header
import pandas as pd
from tqdm import tqdm
import openai

from utilities.util import get_config
from extractor_modules.email.get_emails import delete_emails

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- CONNECT TO GMAIL ---
def connect_to_gmail_imap(user: str, password: str, inbox: str = "INBOX") -> imaplib.IMAP4_SSL:
    """
    Connect to Gmail's IMAP server and select the specified inbox.
    """
    imap_url = 'imap.gmail.com'
    try:
        mail = imaplib.IMAP4_SSL(imap_url)
        mail.login(user, password)
        mail.select(inbox)
        logging.info(f"Connected to IMAP inbox: {inbox}")
        return mail
    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP login failed: {e}")
        raise

# --- FETCH EMAILS ---
def fetch_emails(mail: imaplib.IMAP4_SSL, since_days: int = 7, max_results: int = 500, subject_filter: str = None):
    """
    Fetch up to `max_results` emails received since `since_days` ago,
    optionally filtering by subject text.
    Returns a list of tuples: (raw_date_str, full_email_text).
    """
    since_date = (datetime.utcnow() - timedelta(days=since_days)).strftime("%d-%b-%Y")
    criterion = f'(SINCE {since_date})'
    if subject_filter:
        criterion = f'(SINCE {since_date} SUBJECT "{subject_filter}")'

    status, data = mail.search(None, criterion)
    if status != 'OK':
        logging.error("Error searching emails: %s", status)
        return []

    email_ids = data[0].split()[-max_results:]
    logging.info(f"Found {len(email_ids)} emails since {since_date}")
    emails = []

    ids_to_delete = []
    for email_id in tqdm(email_ids, desc="Fetching emails"):
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        if status != 'OK':
            logging.warning(f"Failed to fetch email ID {email_id}")
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        ids_to_delete.append(email_id)

        # Decode subject
        subj, encoding = decode_header(msg.get("Subject", ""))[0]
        subject = subj.decode(encoding or 'utf-8', errors='ignore') if isinstance(subj, bytes) else subj

        # Date header
        date_str = msg.get("Date", "")

        # Extract body (prefer plain text)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get('Content-Disposition'))
                if ctype == 'text/plain' and 'attachment' not in disp:
                    payload = part.get_payload(decode=True)
                    try:
                        body = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                    except Exception:
                        body = payload.decode('latin-1', errors='ignore')
                    break
        else:
            payload = msg.get_payload(decode=True)
            body = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore') if payload else ''

        full_text = f"Subject: {subject}\nBody: {body}"
        emails.append((date_str, full_text))

    return emails, ids_to_delete

# --- OPENAI CALL WITH RETRIES ---
def extract_structured_data(email_text: str, retries: int = 3, backoff_factor: float = 2.0):
    """
    Send email text to OpenAI and extract structured data, retrying on errors.
    """
    system_prompt = (
        "Extract the following details from the provided email content and output them in the exact format below:\n"
        "Timestamp: <timestamp IN ISO 8601 format>\n"
        "Location: <location>\n"
        "Event Name: <event name>\n"
        "Event Type: <event type>\n"
        "Description: <description>\n\n"
        "Ensure that each line starts with the label exactly as shown."
    )

    # Add instructions for emergency types
    with open('./extractor_modules/email/emergency_types.txt', 'r') as file:
        emergency_types = file.read()
    
    system_prompt += " For the Event Type, please use the following list of types in order to classify the given information: \n" + emergency_types + "\n\n"

    # print("EMAIL TEXT: ", email_text)

    for attempt in range(1, retries + 1):
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": email_text}
                ],
                temperature=0
            )
            return response.choices[0].message.content
        except Exception as e:
            wait = backoff_factor ** (attempt - 1) + random.uniform(0, 1)
            logging.warning(f"OpenAI API error on attempt {attempt}: {e}. Retrying in {wait:.1f}s...")
            time.sleep(wait)
    logging.error("Failed to extract structured data after %d attempts", retries)
    return "ERROR: Extraction failed"

# --- PARSE STRUCTURED RESPONSE ---
def parse_response(text: str):
    """
    Parse labeled output into a dict.
    """
    fields = ["Timestamp", "Location", "Event Name", "Event Type", "Description"]
    result = {}
    for field in fields:
        match = re.search(rf"^{field}:\s*(.*)$", text, re.MULTILINE)
        result[field] = match.group(1).strip() if match else ''
    return result

# --- MAIN PROCESSOR ---
def process_emails_to_csv(username: str,
                          password: str,
                          output_dir: str = '.',
                          since_days: int = 7,
                          max_results: int = 500,
                          delete_read_emails: bool = False,
                          subject_filter: str = None):
    """
    Connect to Gmail, fetch recent emails, extract structured data via OpenAI, and save to CSV.
    Returns the DataFrame of structured data.
    """
    mail = connect_to_gmail_imap(username, password)
    raw_emails, ids_to_delete = fetch_emails(mail, since_days=since_days,
                              max_results=max_results,
                              subject_filter=subject_filter)

    # Optional backup of raw emails
    df_raw = pd.DataFrame(raw_emails, columns=["Original Date", "Raw Content"])
    raw_path = os.path.join(output_dir, "raw_emails.csv")
    df_raw.to_csv(raw_path, index=False)
    logging.info(f"Saved raw emails to {raw_path}")

    processed = []
    for date_str, content in tqdm(raw_emails, desc="Processing emails"):
        ai_output = extract_structured_data(content)
        structured = parse_response(ai_output)
        structured["Original Date"] = date_str
        processed.append(structured)
        time.sleep(1.5)

    df = pd.DataFrame(processed)

    # Save filename
    filename = str(int(time.time()*1000))

    if processed:  # Only save if we have data
        out_path = os.path.join(output_dir, f"{filename}.csv")
        df.to_csv(out_path, index=False)
        logging.info(f"Saved structured data to {out_path}")

    # Don't forget to delete emails
    if delete_read_emails:
        delete_emails(mail, ids_to_delete)

    # Also delete the raw emails
    if os.path.exists(raw_path):
        os.remove(raw_path)

    return df


def pull_data(chosen_sensors=[], exclude_sensors=[]):

    # Load config information
    email_acc = get_config()["email_acc_info"]
    username = email_acc["email"]
    password = email_acc["password"]
    openai_api_key = get_config()["openai"]["api"]

    # Saved data folder
    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y%m%d%H%M%S")
    current_day = current_time.strftime("%Y%m%d")

    
    # Get folder for saving data into
    data_folder = get_config()["save_folder"]

    save_folder = os.path.join(data_folder, "citizen_data")
    os.makedirs(save_folder, exist_ok=True)

    save_folder = os.path.join(save_folder, current_day)
    os.makedirs(save_folder, exist_ok=True)

    # Load openai key
    openai.api_key = openai_api_key

    # --- EXECUTION ENTRYPOINT ---
    df = process_emails_to_csv(
        username=username,
        password=password,
        output_dir=save_folder,
        since_days=1,
        max_results=100,
        delete_read_emails=True
    )



if __name__ == "__main__":

    # Load config information
    email_acc = get_config()["email_acc_info"]
    username = email_acc["email"]
    password = email_acc["password"]
    openai_api_key = get_config()["openai"]["api"]

    # Saved data folder
    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y%m%d%H%M%S")
    current_day = current_time.strftime("%Y%m%d")

    
    # Get folder for saving data into
    data_folder = get_config()["save_folder"]

    

    save_folder = os.path.join(data_folder, "citizen_data")
    os.makedirs(save_folder, exist_ok=True)

    save_folder = os.path.join(save_folder, current_day)
    os.makedirs(save_folder, exist_ok=True)

    # Load openai key
    openai.api_key = openai_api_key

    # --- EXECUTION ENTRYPOINT ---
    df = process_emails_to_csv(
        username=username,
        password=password,
        output_dir=save_folder,
        since_days=1,
        max_results=100,
        delete_read_emails=True
    )