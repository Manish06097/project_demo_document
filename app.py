import streamlit as st
import requests
import os
import shutil
import time
import pandas as pd
import logging
from dotenv import load_dotenv
import mimetypes
import base64

# Load environment variables
load_dotenv()

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    filename='logs/app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger()

def get_mime_type(filename):
    """
    Determines the MIME type based on the file extension.
    Defaults to 'application/octet-stream' if the type is unknown.
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"

def upload_document(file_path, filename):
    """
    Uploads a document to Docupanda's API with dynamic MIME type handling.
    
    Parameters:
        file_path (str): The path to the file to be uploaded.
        filename (str): The name of the file.
    
    Returns:
        dict: The JSON response from the API.
    
    Raises:
        requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        Exception: For any other exceptions that occur.
    """
    url = "https://app.docupanda.io/document"
    mime_type = get_mime_type(filename)
    
    try:
        with open(file_path, "rb") as file:
            content = file.read()
        
        # Encode file contents to base64
        encoded_content = base64.b64encode(content).decode('utf-8')
        
        # Construct the contents field with the correct MIME type
        contents_field = f"data:{mime_type};name={filename};base64,{encoded_content}"
        
        payload = {
            "document": {
                "file": {
                    "filename": filename,
                    "contents": contents_field
                }
            }
        }
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-Key": os.getenv("API_KEY")
        }
        
        # Ensure the API_KEY is present
        if not headers["X-API-Key"]:
            logger.error("API_KEY is not set in environment variables.")
            raise ValueError("API_KEY is missing.")
        
        # Make the POST request
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        # Log the successful upload with the Document ID
        document_id = response.json().get("documentId")
        logger.info(f"Uploaded document '{filename}' to Docupanda with Document ID: {document_id}")
        return response.json()
    
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred while uploading '{filename}': {http_err} - Response Content: {response.text}")
        raise
    except Exception as err:
        logger.error(f"An unexpected error occurred while uploading '{filename}': {err}")
        raise

def standardize_document(schema_id, document_ids):
    """
    Initiates the standardization process for uploaded documents.
    
    Parameters:
        schema_id (str): The fixed schema ID for standardization.
        document_ids (list): A list of document IDs to be standardized.
    
    Returns:
        dict: The JSON response from the API.
    
    Raises:
        requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        Exception: For any other exceptions that occur.
    """
    url = "https://app.docupanda.io/standardize/batch"  # Update this if the correct endpoint differs
    
    payload = {
        "schemaId": schema_id,
        "documentIds": document_ids
    }
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-API-Key": os.getenv("API_KEY")
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Standardization initiated for documents: {document_ids}")
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred during standardization: {http_err} - Response Content: {response.text}")
        raise
    except Exception as err:
        logger.error(f"An unexpected error occurred during standardization: {err}")
        raise

def retrieve_extracted_data(standardization_id):
    """
    Retrieves the extracted data from the standardization process.
    
    Parameters:
        standardization_id (str): The ID of the standardization job.
    
    Returns:
        dict or None: The JSON response containing the extracted data, or None if binary data is saved.
    
    Raises:
        requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        Exception: For any other exceptions that occur.
    """
    url = f"https://app.docupanda.io/standardization/{standardization_id}"
    headers = {
        "accept": "application/json",
        "X-API-Key": os.getenv("API_KEY")
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logger.info(f"Retrieved data for Standardization ID: {standardization_id}")
        
        # Attempt to parse JSON
        data = response.json()
        return data
    except ValueError:
        # If response is not JSON, handle as binary
        logger.warning(f"Response for Standardization ID '{standardization_id}' is not JSON. Attempting to handle as binary file.")
        # Save the binary content to a file
        extracted_dir = 'extracted_data'
        if not os.path.exists(extracted_dir):
            os.makedirs(extracted_dir)
        
        file_path = os.path.join(extracted_dir, f"{standardization_id}.zip")
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Extracted data saved as '{file_path}'.")
        st.info(f"Extracted data saved as '{file_path}'. Please check the 'extracted_data' folder.")
        return None  # Or return the file path if needed
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred while retrieving data for Standardization ID '{standardization_id}': {http_err} - Response Content: {response.text}")
        raise
    except Exception as err:
        logger.error(f"An unexpected error occurred while retrieving data for Standardization ID '{standardization_id}': {err}")
        raise

def save_uploaded_file(uploaded_file):
    """
    Saves the uploaded file to the Input Folder.
    
    Parameters:
        uploaded_file (UploadedFile): The file uploaded via Streamlit.
    
    Returns:
        str: The path to the saved file.
    """
    input_dir = 'input_folder'
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
    file_path = os.path.join(input_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    logger.info(f"File '{uploaded_file.name}' uploaded and saved to Input Folder.")
    return file_path

def archive_file(file_path):
    """
    Moves the processed file to the Archive Folder.
    If a file with the same name exists, it replaces the existing file.
    
    Parameters:
        file_path (str): The path to the file to be archived.
    """
    archive_dir = 'archive_folder'
    
    # Create the archive directory if it doesn't exist
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
        logger.info(f"Archive directory '{archive_dir}' created.")
    
    # Define the destination path
    destination = os.path.join(archive_dir, os.path.basename(file_path))
    
    try:
        # Check if the file already exists in the archive
        if os.path.exists(destination):
            os.remove(destination)
            logger.info(f"Existing file '{destination}' removed to replace with the new file.")
        
        # Move the file to the archive directory
        shutil.move(file_path, destination)
        logger.info(f"File '{os.path.basename(file_path)}' moved to Archive Folder at '{destination}'.")
    
    except Exception as e:
        logger.error(f"Failed to archive file '{file_path}': {e}")
        st.error(f"An error occurred while archiving the file: {e}")
        raise


def save_data_to_excel(data, output_file='to_be_processed/existing_data.xlsx'):
    """
    Saves the extracted data to an existing Excel file.
    Adds new rows and columns as necessary without replacing existing data.
    
    Parameters:
        data (dict): The extracted data in JSON format.
        output_file (str): The path to the existing Excel file.
    """
    # Normalize the JSON data into a pandas DataFrame
    new_df = pd.json_normalize(data)
    
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"Output directory '{output_dir}' created.")
    
    try:
        if not os.path.isfile(output_file):
            # File doesn't exist; create it with headers
            new_df.to_excel(output_file, index=False)
            logger.info(f"Created new Excel file '{output_file}' and saved data.")
        else:
            # File exists; read existing data
            existing_df = pd.read_excel(output_file)
            logger.info(f"Existing Excel file '{output_file}' read successfully.")
            
            # Combine existing and new dataframes
            combined_df = pd.concat([existing_df, new_df], ignore_index=True, sort=False)
            logger.info("Dataframes concatenated successfully.")
            
            # Save the combined dataframe back to Excel
            combined_df.to_excel(output_file, index=False)
            logger.info(f"Appended new data to Excel file '{output_file}'.")
    
    except Exception as e:
        logger.error(f"Error saving data to Excel: {e}. Attempting to recreate the Excel file.")
        try:
            # Attempt to recreate the Excel file
            new_df.to_excel(output_file, index=False)
            logger.info(f"Recreated and saved data to '{output_file}'.")
        except Exception as recreate_err:
            logger.critical(f"Failed to recreate Excel file '{output_file}': {recreate_err}")
            st.error(f"Failed to save extracted data to Excel: {recreate_err}")
            raise

def save_data_to_csv(data, output_file='to_be_processed/existing_data.csv'):
    """
    Saves the extracted data to an existing CSV file.
    
    Parameters:
        data (dict): The extracted data in JSON format.
        output_file (str): The path to the existing CSV file.
    """
    df = pd.json_normalize(data)
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # If file doesn't exist, create it with headers
    if not os.path.isfile(output_file):
        df.to_csv(output_file, index=False)
    else:
        df.to_csv(output_file, mode='a', index=False, header=False)
    logger.info(f"Extracted data saved to '{output_file}'.")
def main():
    st.set_page_config(page_title="Docupanda Processor", layout="centered")
    st.title("📄 Docupanda Document Processor")
    st.write("Upload your documents, and we'll process them automatically.")

    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "jpg", "png", "webp"])

    if st.button("Process File"):
        if uploaded_file is not None:
            try:
                with st.spinner('Uploading and processing...'):
                    # Save uploaded file
                    file_path = save_uploaded_file(uploaded_file)
                    
                    # Upload to Docupanda
                    upload_response = upload_document(file_path, uploaded_file.name)
                    document_id = upload_response.get("documentId")
                    logger.info(f"Uploaded '{uploaded_file.name}' to Docupanda with Document ID: {document_id}")
                    
                    st.success(f"File uploaded to Docupanda. Document ID: {document_id}")
                    
                    # Standardize Document
                    schema_id = os.getenv("SCHEMA_ID")
                    if not schema_id:
                        st.error("SCHEMA_ID is not set in environment variables.")
                        logger.error("SCHEMA_ID is missing.")
                        raise ValueError("SCHEMA_ID is missing.")
                    
                    st.info("Initiating standardization process...")
                    time.sleep(20)
                    standardize_response = standardize_document(schema_id, [document_id])
                    standardization_ids = standardize_response.get("standardizationIds")
                    
                    if not standardization_ids:
                        st.error("No Standardization ID returned from Docupanda.")
                        logger.error("No Standardization ID returned from Docupanda.")
                        raise ValueError("No Standardization ID returned.")
                    
                    standardization_id = standardization_ids[0]
                    logger.info(f"Standardization initiated with Standardization ID: {standardization_id}")
                    
                    st.success(f"Document standardization initiated. Standardization ID: {standardization_id}")
                    
                    # Polling mechanism to check for extracted data
                    st.info("Processing document. Please wait...")
                    
                    # Define polling parameters
                    max_attempts = 12  # e.g., 12 attempts * 10 seconds = 120 seconds
                    poll_interval = 20  # seconds
                    attempt = 0
                    extracted = False

                    # Placeholder for messages
                    message_placeholder = st.empty()
                    
                    while attempt < max_attempts:
                        message_placeholder.info(f"Attempt {attempt + 1} of {max_attempts}: Checking for extracted data...")
                        try:
                            time.sleep(poll_interval)
                            data_response = retrieve_extracted_data(standardization_id)
                            
                            if data_response and 'data' in data_response:
                                extracted_data = data_response['data']
                                logger.info(f"Extracted data retrieved for Standardization ID: {standardization_id}")
                                
                                # Save extracted data
                                save_data_to_excel(extracted_data)
                                # save_data_to_csv(extracted_data)
                                
                                # Archive the file
                                archive_file(file_path)
                                
                                st.success("Document processed and data saved successfully.")
                                
                                # Provide a download link for the Excel file
                                excel_file_path = 'to_be_processed/existing_data.xlsx'
                                if os.path.exists(excel_file_path):
                                    with open(excel_file_path, "rb") as f:
                                        excel_data = f.read()
                                    st.download_button(
                                        label="📥 Download Extracted Data as Excel",
                                        data=excel_data,
                                        file_name=os.path.basename(excel_file_path),
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                                
                                # Optionally, provide a download link for the archived file
                                archive_file_path = os.path.join('archive_folder', os.path.basename(file_path))
                                if os.path.exists(archive_file_path):
                                    with open(archive_file_path, "rb") as f:
                                        archive_data = f.read()
                                    st.download_button(
                                        label="📥 Download Archived File",
                                        data=archive_data,
                                        file_name=os.path.basename(archive_file_path),
                                        mime="application/octet-stream"
                                    )
                                
                                extracted = True
                                break
                            else:
                                message_placeholder.info(f"Attempt {attempt + 1}: No data retrieved yet. Retrying in {poll_interval} seconds...")
                        except Exception as e:
                            message_placeholder.error(f"Attempt {attempt + 1}: Error retrieving data - {e}. Retrying in {poll_interval} seconds...")
                        
                        attempt += 1
                        # time.sleep(poll_interval)
                    
                    if not extracted:
                        st.error("Document processing is taking longer than expected. Please try retrieving the data later.")
                        logger.error(f"Standardization ID '{standardization_id}' timed out after {max_attempts * poll_interval} seconds.")
            
            except requests.exceptions.HTTPError as http_err:
                st.error(f"HTTP error occurred: {http_err}. Please check your API configuration.")
            except ValueError as val_err:
                st.error(f"Configuration error: {val_err}.")
            except Exception as e:
                st.error(f"An error occurred: {e}")
                logger.error(f"Error processing file '{uploaded_file.name}': {str(e)}")
        else:
            st.warning("Please upload a file to process.")

    # Optionally, display logs
    if st.checkbox("Show Logs"):
        log_file_path = "logs/app.log"
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as log_file:
                logs = log_file.read()
                st.text_area("Application Logs", logs, height=300)
        else:
            st.warning("Log file does not exist.")

if __name__ == "__main__":
    main()
