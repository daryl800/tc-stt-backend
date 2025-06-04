import os
import datetime
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    service = build("calendar", "v3", credentials=creds)
    return service

def create_calendar_event(summary, start_time, end_time=None):
    service = get_calendar_service()
    if end_time is None:
        end_time = start_time + datetime.timedelta(hours=1)

    event = {
        'summary': summary,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Hong_Kong'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Hong_Kong'},
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"[📅] Event created: {event.get('htmlLink')}")
    return event.get('htmlLink')
