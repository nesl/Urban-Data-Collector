from extractor_modules.email.get_emails import connect_to_gmail_imap, fetch_emails, delete_emails
from extractor_modules.email.parse_twitter_emails import TwitterEmailParser

import logging
import argparse
import os
import csv
import sys
from dotenv import load_dotenv
from datetime import date, datetime
from dateutil.parser import isoparse
from time import time


from utilities.util import get_config
from extractor_modules.llm_client import LLMClient, OpenAIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def format_data(emails, twitter_parser):

    print(emails)

    formatted_emails = []
    for email in emails:
        body = email["body"]
        valid_email = True

        if "twitter" in email["subject"].lower():

            parsed_data = twitter_parser.process_twitter_email_body(body)
            if parsed_data:
                author, body, event, location, start_time, end_time = parsed_data
            else:
                continue

        else:
            valid_email = False
        
        if valid_email:
            formatted_emails.append({
                "author": author,
                "email_time": email["date"],
                "event": event,
                "location": location,
                "start_time": start_time,
                "end_time" : end_time,
                "body": body
            })
    
    return formatted_emails

def export_to_csv(emails: list[dict], filename: str, is_directory, append: bool = False) -> None:
    """Export emails to CSV with proper file handling."""

    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y%m%d%H%M%S")
    current_day = current_time.strftime("%Y%m%d")

    curr_time = str(int(time()*1000))
    
    filepath = os.path.join(filename, current_day)
    
    if not emails:
        logging.warning("No emails to export")
        return

    if is_directory:
        if not os.path.exists(filepath):
            os.mkdir(filepath)
        filename = os.path.join(filepath, f"{curr_time}.csv")

    fieldnames = ["author", "email_time", "event", "location", "start_time", "end_time", "body"]
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


def pull_data(chosen_sensors=[], exclude_sensors=[]):

    config_data = get_config()
    username = config_data["email_acc_info"]["email"]
    password = config_data["email_acc_info"]["password"]

    # dap is default args
    # Set up our twitter parser
    llm_client = OpenAIClient()
    twitter_parser = TwitterEmailParser(llm_client)

    print("Parser and llm client set up!")

    # try:
    with connect_to_gmail_imap(username, password) as mail:
        print("fetching emails")
        emails = fetch_emails(mail, 100) # by default, limit to 100 emails
        # print(emails)
        # asdf
        # Filter out dates which are not today
        matching_emails = []
        for email in emails:
            email_date = isoparse(email["date"]).date()
            if date.today() == email_date:
                matching_emails.append(email)
        emails = matching_emails

        print("formatting emails")
        emails = format_data(emails, twitter_parser)

        output_dir = os.path.join(config_data["save_folder"], "twitter_data")
        os.makedirs(output_dir, exist_ok=True)
        export_to_csv(emails, output_dir, is_directory=True, append=True)

        # Delete emails that we have processed
        delete_emails(mail, [e["id"] for e in emails])
    # except Exception as e:
    #     logging.error(f"Data pull failed: {str(e)}")
   


def main():
    # load_dotenv()
    # username = os.getenv("GMAIL")
    # password = os.getenv("PASSWORD")

    email_acc = get_config()["email_acc_info"]
    username = email_acc["email"]
    password = email_acc["password"]


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
                        help="Delete fetched emails")
    parser.add_argument("-l", "--limit", type=int, default=100,
                        help="Limit number of emails processed")
    
    parser.add_argument("-p", "--production", help="Takes in a directory and dumps dated data there")
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Write to <config save_folder>/twitter_data",
    )
    args = parser.parse_args()

    # Set up our twitter parser
    llm_client = OpenAIClient()
    twitter_parser = TwitterEmailParser(llm_client)

    print("Parser and llm client set up!")

    try:
        with connect_to_gmail_imap(username, password) as mail:
            print("fetching emails")
            emails = fetch_emails(mail, args.limit)

            # Filter out dates which are not today
            matching_emails = []
            for email in emails:
                email_date = isoparse(email["date"]).date()
                if date.today() == email_date:
                    matching_emails.append(email)
            emails = matching_emails


            print("formatting emails")
            emails = format_data(emails, twitter_parser)
            
            if args.scheduled:
                output_dir = os.path.join(get_config()["save_folder"], "twitter_data")
                os.makedirs(output_dir, exist_ok=True)
                export_to_csv(emails, output_dir, is_directory=True, append=True)
            elif args.production:
                export_to_csv(emails, args.production, is_directory=True, append=True)
            elif args.csv:
                export_to_csv(emails, args.csv, is_directory=False, append=args.append)
            else:
                for email_info in emails:
                    output = [str(email_info[field]) for field in args.fields]
                    print("\n".join(output))
                    print("-" * 50)

            if args.delete:
                delete_emails(mail, [e["id"] for e in emails])

    except KeyboardInterrupt:
        logging.info("Operation cancelled by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
