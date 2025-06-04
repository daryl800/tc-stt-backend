from __future__ import print_function
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from calendar_auth import get_calendar_service


def add_reminder_to_calendar(summary, description, start_time, end_time):
    """
    Adds a reminder event to the user's primary Google Calendar.
    
    Parameters:
    - summary: Event title (e.g., "Hospital Appointment")
    - description: More details (e.g., from transcription)
    - start_time: ISO 8601 datetime string (e.g., "2025-06-11T15:00:00+08:00")
    - end_time: ISO 8601 datetime string (e.g., "2025-06-11T16:00:00+08:00")
    """
    try:
        service = get_calendar_service()

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Asia/Hong_Kong',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Asia/Hong_Kong',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"✅ Event created: {event.get('htmlLink')}")
        return event.get('htmlLink')

    except HttpError as error:
        print(f"❌ An error occurred: {error}")
        return None
