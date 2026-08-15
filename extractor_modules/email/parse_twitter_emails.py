import sys
import logging
import re
import json
from datetime import date
import datetime
# from ollama import Client

class TwitterEmailParser:

    def __init__(self, client):

        self.client = client

        # # Initialize LLM client
        # # llm_uri = config_data["llm_host"]["uri"]
        # # client = LLMClient(llm_uri)
        # client = OpenAIClient()

        # Define the JSON schema for the output
        # json_schema = {
        #     "type": "object",
        #     "properties": {
        #         "event": {"type": "string"},
        #         "location": {"type": "string"},
        #         "start_time": {"type": "string"},
        #         "end_time": {"type": "string"}
        #     },
        #     "required": ["event", "location", "start_time", "end_time"]
        # }


        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )


    def query_llm(self, email_body: str) -> tuple[str, str, str, str, str]:
        # get the event, location, and time from the email body
        with open('./extractor_modules/email/ds_email_template.txt', 'r') as file:
            prompt = file.read()

        with open('./extractor_modules/email/emergency_types.txt', 'r') as file:
            emergency_types = file.read()

        current_date = date.today()

        # Prepare the messages with instructions for JSON output
        # messages = [
        #     {
        #         'role': 'system',
        #         'content': 'You are an AI assistant that extracts information from text and outputs it in JSON format. Follow the instructions carefully.'
        #     },
        #     {
        #         'role': 'user',
        #         'content': (
        #             f"{prompt}\n\nThe current date is: {current_date} \n" 
        #             f"The weekday is: {datetime.datetime.now().strftime('%A')}"
        #             f"\nThe types of events are: \n{emergency_types} \n\n" 
        #             f"The text is:\n{email_body}"
        #         )
        #     }
        # ]

        messages = 'You are an AI assistant that extracts information from text and outputs it in JSON format. Follow the instructions carefully and output your ' + (f"{prompt}\n\nThe current date is: {current_date} \n" 
        f"The weekday is: {datetime.datetime.now().strftime('%A')}"
        f"\nThe types of events are: \n{emergency_types} \n\n" 
        f"The text is:\n{email_body}")

        response, thoughts = self.client.send_message_to_llm_single(str(messages))

        # # Make the API call with JSON format specified
        # response = client.chat(
        #     model='deepseek-r1:70b',
        #     messages=messages,
        #     format=json_schema,
        # )

        # data = json.loads(response['message']['content'])
        try:
            json_data = response.split("{")[1].split("}")[0]
            data = json.loads("{"+json_data+"}")

            return data["event"], data["location"], data["start_time"], data["end_time"]
        except Exception as e:
            print("ERROR: " + e)
            return None

        


    def process_twitter_email_body(self, text):
        # Extract original author from retweets (case-insensitive)
        rt_match = re.search(r'RT\s*@(\w+):', text, re.IGNORECASE)
        if rt_match is not None:
            author = rt_match.group(1)
            # Remove RT prefix while preserving original content
            cleaned = re.sub(r'RT\s*@\w+:\s*', '', text, flags=re.IGNORECASE)
        else:
            # Fallback to quoted tweet author extraction
            author_match = re.search(r"@([a-zA-Z]+):", text)
            author = author_match.group(1).strip() if author_match else None
            cleaned = text

        # Content cleaning pipeline
        cleaned = re.sub(r'@\w+\s*', '', cleaned)  # Remove remaining mentions
        cleaned = re.sub(r'—.*?https://\S+', '', cleaned, flags=re.DOTALL)  # Strip metadata
        cleaned = re.sub(r'\s*Manage\s+Unsubscribe.*?IFTTT.*', '', cleaned, flags=re.DOTALL)
        
        # Structural cleanup
        cleaned = '\n'.join([
            line.strip() for line in cleaned.split('\n')
            if line.strip() and not line.startswith(('Manage on IFTTT', 'Twitter via IFTTT'))
        ])
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()  # Normalize excessive newlines

        query_response = self.query_llm(cleaned)
        if query_response:
            event, location, start_time, end_time = query_response

            return author, cleaned, event, location, start_time, end_time
        else:
            return None


# testing script
if __name__ == "__main__":
    test_string = """
    @NotifyLA: A strong storm coming Sun-Tues may trigger life threatening debris flows. 
    EVACUATION WARNING: La Tuna Canyon starting at Martindale to the E, Primrose to the S, Ledge to the W, 
    Horse Haven to the N should prepare to evacuate. 
    """

    print(process_twitter_email_body(test_string))