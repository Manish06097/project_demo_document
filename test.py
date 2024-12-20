import streamlit as st
import logging
import sys
import boto3
from watchtower import CloudWatchLogHandler

# Configure logging
log_group_name = 'Option1_streamlit_log'  # Replace with your log group name
log_stream_name = 'streamlit-logs'  # You can customize this name
retention_days = 5  # Retention policy: 5 days

# Set up CloudWatch logging
cloudwatch_handler = CloudWatchLogHandler(log_group=log_group_name, stream_name=log_stream_name)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(cloudwatch_handler)

# Custom print function to log to CloudWatch
def print_to_cloudwatch(*args, **kwargs):
    message = " ".join(str(arg) for arg in args)
    logger.info(message)  # Log the message to CloudWatch
    sys.__stdout__.write(message + "\n")  # Output to console

# Replace the built-in print function
sys.modules['builtins'].print = print_to_cloudwatch

# Set log retention policy to 5 days
def set_log_retention():
    client = boto3.client('logs')
    client.put_retention_policy(
        logGroupName=log_group_name,
        retentionInDays=retention_days
    )
    print(f"Log retention policy set to {retention_days} days for log group {log_group_name}")

# Example Streamlit application
def main():
    st.title("My Streamlit App")
    
    # Example usage of print
    print("Streamlit app started.")
    
    # Set log retention when the app starts
    set_log_retention()
    
    # Text input box
    user_input = st.text_input("Enter something:")
    
    if user_input:
        print(f"User input received: {user_input}")
        st.write(f"You entered: {user_input}")
    else:
        print("Waiting for user input...")

if __name__ == "__main__":
    main()