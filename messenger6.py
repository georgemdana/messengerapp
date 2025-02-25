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

def send_imessage(phone, name, message, tracking_link, image_path=None):
    text_applescript = f'''
    tell application "Messages"
        set targetBuddy to "{phone}"
        set targetService to id of 1st service whose service type = iMessage
        set textMessage to "Hello {name},\n\n{message}{tracking_link}"
        set theBuddy to participant targetBuddy of account id targetService
        send textMessage to theBuddy
    end tell
    '''

    try:
        subprocess.run(["osascript", "-e", text_applescript], check=True)
        result = f"Text message sent to {name} at {phone}"
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
        return result
    except subprocess.CalledProcessError as e:
        return f"Error sending to {name}: {str(e)}"

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
            ["Create Campaign", "Send Messages", "Campaign Statistics"]
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
            </div>
            """,
            unsafe_allow_html=True
        )

    if selected_tab == "Create Campaign":
        create_campaign_tab()
    elif selected_tab == "Send Messages":
        send_messages_tab()
    elif selected_tab == "Campaign Statistics":
        campaign_statistics_tab()

def create_campaign_tab():
    st.header("Create Campaign")
    campaign_name = st.text_input("Enter campaign name:")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
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
                st.image(image_file, caption="Image to be sent", use_column_width=True)
            else:
                st.write("No image selected")

        if st.button("Create Campaign", key="create_button") and message and base_url and campaign_name:
            image_data = None
            if image_file:
                image_data = base64.b64encode(image_file.getvalue()).decode()

            tracking_info = {}
            results = []

            # store the data without sending the messages
            results = [{"name": row['Name'], "phone": row['Phone'], "result": "Not Sent", "tracking_id": None} for index, row in df.iterrows()]
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
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Campaign Name:** {campaign_data['name']}")
    with col2:
        st.write(f"**Date Created:** {campaign_data['date'][:10]}")
    with col3:
        st.write(f"**Time Created:** {campaign_data['date'][11:16]}")  # Extract time

    # Message Preview (Same as Create Campaign)
    st.subheader("Message Preview")
    col1, col2 = st.columns(2)
    with col1:
        st.text_area("Message", value=f"Hello [Name],\n{campaign_data['message_text']}\n[Tracking Link]", height=100, disabled=True)
    with col2:
        if campaign_data['image_data']:
            image_bytes = base64.b64decode(campaign_data['image_data'])
            st.image(image_bytes, caption="Campaign Image", use_column_width=True)
        else:
            st.write("No image selected")

    st.subheader("Send Individual Messages")
    for i, result in enumerate(campaign_data['results']):
        name = result['name']
        phone = result['phone']
        key = f"send_button_{i}"  # Unique key for each button/message pair

        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{name}** ({phone})")
        with col2:
            if key not in st.session_state:
                st.session_state[key] = False  # Initialize state to False (not sent)

            if not st.session_state[key]:
                if st.button(f"Send to {name}", key=f"button_{i}"):
                    tracking_link, tracking_id = create_tracking_link(campaign_data['base_url'], phone)
                    personalized_message = campaign_data['message_text'].replace("[Name]", name)
                    result_message = send_imessage(phone, name, personalized_message, tracking_link, None)
                    result['result'] = result_message
                    save_campaign_data(campaign_data['name'], campaign_data['results'], campaign_data['tracking_info'], campaign_data['message_text'], campaign_data['image_data'], campaign_data['base_url'])
                    st.session_state[key] = True  # Update state to True (sent)
                    st.experimental_rerun()  # Refresh to reflect the change
            else:
                st.success(f"Sent!")

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
        st.write("No image was sent with this campaign.")

    successful_sends = sum(1 for msg in campaign_data['results'] if not msg['result'].startswith("Error"))
    failed_sends = len(campaign_data['results']) - successful_sends

    col1, col2 = st.columns(2)
    col1.metric("Successfully Sent", successful_sends)
    col2.metric("Failed to Send", failed_sends)

    if failed_sends > 0:
        st.subheader("Failed Messages")
        failed_messages = [msg for msg in campaign_data['results'] if msg['result'].startswith("Error")]
        for msg in failed_messages:
            st.write(f"Name: {msg['name']}, Phone: {msg['phone']}")
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
        st.write(f"Name: {info['name']}, Phone: {info['phone']}, Clicked: {'Yes' if info['clicked'] else 'No'}")

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
