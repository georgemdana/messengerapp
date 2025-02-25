import streamlit as st
import pandas as pd
import subprocess
import os
import time
import json
import uuid
import urllib.parse
from datetime import datetime
import base64
import sys
from io import StringIO

def create_tracking_link(base_url, recipient_id):
    tracking_id = str(uuid.uuid4())
    tracking_url = f"{base_url}?id={tracking_id}&recipient={recipient_id}"
    return tracking_url, tracking_id

def save_tracking_info(tracking_data):
    with open('tracking_info.json', 'w') as f:
        json.dump(tracking_data, f)

def load_tracking_info():
    try:
        with open('tracking_info.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Add the test_sms function here
def test_sms(phone, name, message):
    # Normalize phone number
    if not phone.startswith("+1") and len(phone) == 10:
        phone = f"+1{phone}"

    sms_applescript = f'''
    tell application "Messages"
        set targetBuddy to "{phone}"
        set textMessage to "Hello {name},\n\n{message}"
        send textMessage to buddy targetBuddy
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", sms_applescript],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Success: {result.stdout}")
        return f"SMS sent to {name} at {phone}", None
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")
        return f"Failed to send SMS to {name} ({phone}): {e.stderr}", e.stderr

def send_imessage(phone, name, message, tracking_link, image_path=None):
    # Normalize phone number
    if not phone.startswith("+1") and len(phone) == 10:
        phone = f"+1{phone}"

    # AppleScript for iMessage
    imessage_applescript = f'''
    tell application "Messages"
        set targetBuddy to "{phone}"
        set targetService to id of 1st service whose service type = iMessage
        set textMessage to "Hello {name},\n\n{message}{tracking_link}"
        set theBuddy to participant targetBuddy of account id targetService
        send textMessage to theBuddy
    end tell
    '''

    # AppleScript for SMS
    sms_applescript = f'''
    tell application "Messages"
        set targetBuddy to "{phone}"
        set textMessage to "Hello {name},\n\n{message}{tracking_link}"
        send textMessage to buddy targetBuddy
    end tell
    '''

    # Try iMessage first
    try:
        imessage_result = subprocess.run(
            ["osascript", "-e", imessage_applescript],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"iMessage attempt: {imessage_result.stdout}")
        time.sleep(2)

        # Check delivery
        check_applescript = f'''
        tell application "Messages"
            set targetBuddy to "{phone}"
            set theBuddy to buddy targetBuddy
            set theChat to chat of theBuddy
            set theMessages to messages of theChat
            if (count of theMessages) > 0 then
                set latestMessage to item -1 of theMessages
                return (delivered of latestMessage)
            else
                return false
            end if
        end tell
        '''
        check_result = subprocess.run(
            ["osascript", "-e", check_applescript],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        print(f"Delivery check: {check_result}")

        if check_result == "true":
            result = f"Text message sent to {name} at {phone} via iMessage"
            if image_path:
                image_applescript = f'''
                tell application "Messages"
                    set targetBuddy to "{phone}"
                    set targetService to id of 1st service whose service type = iMessage
                    set theBuddy to participant targetBuddy of account id targetService
                    send POSIX file "{image_path}" to theBuddy
                end tell
                '''
                subprocess.run(["osascript", "-e", image_applescript], check=True)
                result += f" and image sent from {image_path}"
            return result, None

    except subprocess.CalledProcessError as e:
        print(f"iMessage failed: {e.stderr}")

    # Fallback to SMS
    try:
        sms_result = subprocess.run(
            ["osascript", "-e", sms_applescript],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"SMS attempt: {sms_result.stdout}")
        return f"Text message sent to {name} at {phone} via SMS", None
    except subprocess.CalledProcessError as e:
        print(f"SMS failed: {e.stderr}")
        return (
            f"Failed to send to {name} ({phone}) via iMessage and SMS: {e.stderr}",
            f"SMS error: {e.stderr}"
        )
    except Exception as e:
        return f"Unexpected error sending to {name}: {str(e)}", str(e)
    
def get_imessage_responses(phone):
    applescript = f'''
    tell application "Messages"
        set targetBuddy to "{phone}"
        set targetService to id of 1st service whose service type = iMessage
        set theBuddy to participant targetBuddy of account id targetService
        set theChat to chat of theBuddy
        set theMessages to messages of theChat
        set latestMessage to item -1 of theMessages
        return {{content of latestMessage, date received of latestMessage}}
    end tell
    '''

    try:
        # Ensure /usr/bin is in the PATH
        os.environ['PATH'] = '/usr/bin:' + os.environ.get('PATH', '')
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            check=True
        )

        response, date = eval(result.stdout.strip())
        print(f"Raw response from AppleScript for {phone}: {response}, {date}")  # Debugging
        return response, date
    except subprocess.CalledProcessError as e:
        error_message = f"AppleScript Error for phone {phone}: {str(e)}"
        print(error_message)
        return f"Error getting response: {error_message}", None
    except Exception as e:
        error_message = f"General Error for phone {phone}: {str(e)}"
        print(error_message)
        return f"Error getting response: {error_message}", None

def save_campaign_data(campaign_name, results, tracking_info, message_text, image_data, base_url):
    campaign_data = {
        'name': campaign_name,
        'date': datetime.now().isoformat(),
        'results': results,
        'tracking_info': tracking_info,
        'message_text': message_text,
        'image_data': image_data,
        'base_url': base_url
    }

    campaigns = load_campaigns()
    campaigns.append(campaign_data)
    with open('campaigns.json', 'w') as f:
        json.dump(campaigns, f)

def load_campaigns():
    try:
        with open('campaigns.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def delete_campaign(campaign_name):
    campaigns = load_campaigns()
    campaigns = [c for c in campaigns if c['name'] != campaign_name]
    with open('campaigns.json', 'w') as f:
        json.dump(campaigns, f)

def main():
    # Use the full_page parameter to maximize the app's width
    st.set_page_config(layout="wide")

    st.title("iMessage Sender App")

    with st.sidebar:
        # CSS to make the sidebar full height and justify content
        st.markdown(
            """
            <style>
            .sidebar .sidebar-content {
                height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }
            .disclaimer {
                font-size: 10px;
                position: fixed; /* Fixed positioning */
                bottom: 0;       /* Stick to the bottom */
                width: 19vw;      /* Cover the sidebar width - was 16 */
                background-color: white; /* Ensure it's visible */
                padding: 5px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        selected_tab = st.radio(
            "Select View",
            ["Create Campaign", "Send Messages", "Send Manual Message", "Campaign Statistics"]
        )

        # Place the disclaimer at the very end
        st.markdown(
            """
            <div class="disclaimer">
            <strong>Note:</strong> This application sends only <em>one</em> iMessage at a time.
            Attempting to send multiple messages simultaneously is not supported
            and may lead to unexpected behavior or errors. Please ensure you
            click the 'Send' button for each recipient individually and wait
            for confirmation before proceeding to the next recipient.
            <strong>Important:</strong> iMessages may not be delivered to non-Apple (Android) devices.
            If a message fails to send, try sending a standard text message manually.
            </div>
            """,
            unsafe_allow_html=True
        )

    if selected_tab == "Create Campaign":
        create_campaign_tab()
    elif selected_tab == "Send Messages":
        send_messages_tab()
    elif selected_tab == "Send Manual Message":
        send_manual_message_tab()  # Added the new tab function
    elif selected_tab == "Campaign Statistics":
        campaign_statistics_tab()

def create_campaign_tab():
    st.header("Create Campaign")
    campaign_name = st.text_input("Enter campaign name:")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded_file is not None:
        # Define expected column names
        expected_columns = ["Phone", "Name", "Age", "Sex", "Party Last Primary", "Precinct Name", "Zip Code"]  # Correct column name
        # Read the file content as bytes
        csv_bytes = uploaded_file.read()
        df = None  # Initialize df outside the loop

        # Try to decode the bytes with different encodings
        for encoding in ['utf-16', 'utf-8-sig', 'utf-16-le', 'utf-16-be', 'latin1']:  # prioritize utf-16
            try:
                # Decode the bytes into a string
                csv_data = csv_bytes.decode(encoding)

                # Try to parse the CSV with the appropriate delimiter
                try:
                    df = pd.read_csv(StringIO(csv_data), delimiter='\t')

                    # Check for the expected columns
                    missing_columns = [col for col in expected_columns if col not in df.columns]
                    if missing_columns:
                        st.error(
                            f"The following columns are missing from the CSV file: {', '.join(missing_columns)}. Please ensure the CSV file contains all the required columns.")
                        df = None
                    else:
                        st.write(f"Successfully read CSV!")
                    break  # If successful, exit the loop

                except Exception as e:
                    st.write(f"Failed to read CSV with encoding: {encoding}, delimiter: '\\t'. Error: {e}")
                    continue  # If reading fails, continue to next encoding

            except UnicodeDecodeError:
                st.write(f"Failed to decode with encoding: {encoding}")
                continue  # If decoding fails, continue to next encoding

        if df is None:
            st.error("Failed to read CSV with all attempted encodings and delimiters. Please check the file format.")
            return

        # Check if DataFrame is empty after parsing
        if df.empty:
            st.error("DataFrame is empty after parsing. Please check the file format and try again.")
            return

        row_count = len(df)  # Get the number of rows
        st.write(f"Number of rows in uploaded from CSV: {row_count}")  # Display row count

        st.write("Preview of uploaded data:")
        st.dataframe(df.head())

        message = st.text_area("Enter the message to send:")
        image_file = st.file_uploader("Choose an image to send (optional)", type=["png", "jpg", "jpeg"])
        base_url = st.text_input("Enter the base URL for link tracking:")

        st.subheader("Message Preview")
        col1, col2 = st.columns(2)
        with col1:
            st.text_area("Message", value=f"Hello [Name],\n{message}\n[Tracking Link]", height=100, disabled=True)
        with col2:
            if image_file:
                st.image(image_file, caption="Campaign Image", use_column_width=True)
            else:
                st.write("No image selected")

        if st.button("Create Campaign", key="create_button") and message and base_url and campaign_name:
            image_data = None
            if image_file:
                image_data = base64.b64encode(image_file.getvalue()).decode()

            tracking_info = {}
            results = []

            # store the data without sending the messages
            try:
                results = [{"Phone": row['Phone'], "Name": row['Name'], "Age": row['Age'], "Sex": row['Sex'],
                            "Party Last Primary": row['Party Last Primary'], "Precinct Name": row['Precinct Name'],
                            "Zip Code": row['Zip Code'], "result": "Not Sent", "tracking_id": None} for index, row in
                           df.iterrows()]
            except KeyError as e:
                st.error(
                    f"KeyError: {e}. This indicates that a required column is missing from your DataFrame. Please double-check the CSV file and ensure all required columns are present and named correctly.")
                return

            save_campaign_data(campaign_name, results, tracking_info, message, image_data, base_url)
            st.success(f"Campaign '{campaign_name}' created successfully!")

def send_messages_tab():
    st.header("Send Messages")

    campaigns = load_campaigns()
    if not campaigns:
        st.warning("No campaigns available. Please create a campaign in the 'Create Campaign' tab first.")
        return

    selected_campaign = st.selectbox("Select Campaign", options=[c['name'] for c in campaigns])
    campaign_data = next(c for c in campaigns if c['name'] == selected_campaign)

    # Campaign Details in one row
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 2])  # Added a fourth column
    with col1:
        st.write(f"**Campaign Name:** {campaign_data['name']}")
    with col2:
        st.write(f"**Date Created:** {campaign_data['date'][:10]}")
    with col3:
        st.write(f"**Time Created:** {campaign_data['date'][11:16]}")  # Extract time
    with col4:  # Added the row count to the new column
        st.write(f"**Row Count:** {len(campaign_data['results'])}")

    # Message Preview (Same as Create Campaign)
    st.subheader("Message Preview")
    col1, col2 = st.columns(2)
    with col1:
        st.text_area("Message", value=f"Hello [Name],\n{campaign_data['message_text']}\n[Tracking Link]", height=100,
                     disabled=True)
    with col2:
        if campaign_data['image_data']:
            image_bytes = base64.b64decode(campaign_data['image_data'])
            st.image(image_bytes, caption="Campaign Image", use_column_width=True)
        else:
            st.write("No image selected")

    st.subheader("Send Individual Messages")

    # Column Titles
    column_titles = ["Name (Phone)", "Age", "Sex", "Party", "Last Primary", "Precinct", "Zip", "Action"]
    column_widths = [3, 1, 1, 1.5, 2, 2.5, 1.5, 1.5]  # Same widths as data columns
    title_cols = st.columns(column_widths)
    for i, title in enumerate(column_titles):
        title_cols[i].write(f"**{title}**")

    # Pagination
    if 'start_index' not in st.session_state:
        st.session_state.start_index = 0
    if 'end_index' not in st.session_state:
        st.session_state.end_index = min(100, len(campaign_data['results']))

    def load_more():
        st.session_state.start_index = st.session_state.end_index
        st.session_state.end_index = min(st.session_state.end_index + 100, len(campaign_data['results']))

    # Display messages for the current page
    for i in range(st.session_state.start_index, st.session_state.end_index):
        result = campaign_data['results'][i]

        # Create columns for each piece of information
        cols = st.columns(column_widths)  # Use the same widths as titles

        cols[0].write(f"**{result['Name']}** ({result['Phone']})")
        cols[1].write(f"{result['Age']}")
        cols[2].write(f"{result['Sex']}")
        cols[3].write(f"{result['Party Last Primary']}")
        cols[4].write(f"{result.get('Party Last Primary', 'N/A')}")
        cols[5].write(f"{result['Precinct Name']}")
        cols[6].write(f"{result['Zip Code']}")

        # Button column
        with cols[7]:
            key = f"send_button_{i}"
            if key not in st.session_state:
                st.session_state[key] = False

            if not st.session_state[key]:
                if st.button("Send", key=f"button_{i}", help=f"Send to {result['Name']}",
                             use_container_width=True):
                    tracking_link, tracking_id = create_tracking_link(campaign_data['base_url'], result['Phone'])
                    personalized_message = campaign_data['message_text'].replace("[Name]", result['Name'])
                    result_message, error_message = send_imessage(result['Phone'], result['Name'], personalized_message,
                                                     tracking_link, None)
                    if error_message:
                        st.warning(f"Message to {result['Name']} may not have been delivered (potential non-Apple device). Error: {error_message}")
                    else:
                        st.success(f"Message sent to {result['Name']}", icon="✅")

                    result['result'] = result_message
                    save_campaign_data(campaign_data['name'], campaign_data['results'],
                                        campaign_data['tracking_info'],
                                        campaign_data['message_text'], campaign_data['image_data'],
                                        campaign_data['base_url'])
                    st.session_state[key] = True
                    st.experimental_rerun()
            else:
                st.success("Sent", icon="✅")

    # Load More button
    if st.session_state.end_index < len(campaign_data['results']):
        st.button("Load 100 More", on_click=load_more)

def send_manual_message_tab():
    st.header("Send Manual Message")

    name = st.text_input("Recipient Name:")
    phone = st.text_input("Recipient Phone Number:")

    campaigns = load_campaigns()
    if not campaigns:
        st.warning("No campaigns available. Please create a campaign in the 'Create Campaign' tab first.")
        return

    selected_campaign = st.selectbox("Select Campaign", options=[c['name'] for c in campaigns])
    campaign_data = next(c for c in campaigns if c['name'] == selected_campaign)
    base_url = campaign_data['base_url']
    message_text = campaign_data['message_text']

    # Message Preview
    st.subheader("Message Preview")
    preview_message = message_text.replace("[Name]", name) if name else message_text
    st.text_area("Preview", value=f"Hello {name},\n{preview_message}\n[Tracking Link]", height=100, disabled=True)

    # Add a test SMS button
    if st.button("Test SMS Send"):
        result, error = test_sms(phone, name, "Test SMS from Streamlit")
        if error:
            st.error(result)
        else:
            st.success(result)

    # Existing send button
    if st.button("Send Message", disabled=not (name and phone and base_url and message_text)):
        tracking_link, tracking_id = create_tracking_link(base_url, phone)
        personalized_message = message_text.replace("[Name]", name)
        result_message, error_message = send_imessage(phone, name, personalized_message, tracking_link, None)
        if error_message:
            st.warning(f"Message to {name} may not have been delivered. Error: {error_message}")
        else:
            st.success(f"Message sent to {name}", icon="✅")


def campaign_statistics_tab():
    st.header("Campaign Statistics")

    campaigns = load_campaigns()
    if not campaigns:
        st.warning("No campaigns available. Please create a campaign in the 'Create Campaign' tab first.")
        return

    selected_campaign = st.selectbox("Select Campaign", options=[c['name'] for c in campaigns])
    campaign_data = next(c for c in campaigns if c['name'] == selected_campaign)

    # Review Messages
    st.subheader("Message Review")
    st.write(f"Campaign Name: {campaign_data['name']}")
    st.write(f"Campaign Date: {campaign_data['date'][:10]}")
    st.text_area("Sent Message", value=campaign_data['message_text'], height=100, disabled=True)

    if campaign_data['image_data']:
        st.image(base64.b64decode(campaign_data['image_data']), caption="Sent Image", use_column_width=True)
    else:
        st.write("No image selected")

    successful_sends = sum(1 for msg in campaign_data['results'] if not msg['result'].startswith("Error"))
    failed_sends = len(campaign_data['results']) - successful_sends

    col1, col2 = st.columns(2)
    col1.metric("Successfully Sent", successful_sends)
    col2.metric("Failed to Send", failed_sends)

    if failed_sends > 0:
        st.subheader("Failed Messages")
        failed_messages = [msg for msg in campaign_data['results'] if msg['result'].startswith("Error")]
        for msg in failed_messages:
            st.write(f"Name: {msg['Name']}, Phone: {msg['Phone']}")
            st.write(f"Error: {msg['result']}")
            st.write("---")

    # Click Statistics
    st.subheader("Link Click Statistics")
    tracking_info = campaign_data['tracking_info']
    clicked = sum(1 for info in tracking_info.values() if info['clicked'])
    not_clicked = len(tracking_info) - clicked

    col1, col2 = st.columns(2)
    col1.metric("Clicked", clicked)
    col2.metric("Not Clicked", not_clicked)

    st.subheader("Detailed Statistics")
    for tracking_id, info in tracking_info.items():
        st.write(f"Name: {info['Name']}, Phone: {info['Phone']}, Clicked: {'Yes' if info['clicked'] else 'No'}")

    # Delete Campaign
    st.subheader("Delete Campaign")
    if st.button("Delete Campaign"):
        delete_campaign(selected_campaign)
        st.success(f"Campaign '{selected_campaign}' has been deleted.")
        st.experimental_rerun()

if __name__ == "__main__":
    # Initialize session state for storing responses (if not already initialized)
    if 'responses' not in st.session_state:
        st.session_state.responses = {}

    # Initialize session state to track button clicks
    if "button_states" not in st.session_state:
        st.session_state.button_states = {}
    main()
