from leancloud import Object, Query
from datetime import datetime

MemoryItemDB = Object.extend('Memories')

def search_for_answer(query: str):
    """
    Search for memories in the database that contain keywords from the user's question.
    """
    # Create a query to search within the 'MemoryItem' collection
    memory_query = Query(MemoryItemDB)

    # Search for memories containing the keywords from the query in their mainEvent field
    memory_query.contains('mainEvent', query)  # Searching by main event description or keywords

    try:
        results = memory_query.find()
        if results:
            # Return the most relevant result (or top N results) based on your logic
            return results[0]  # Return the first result for simplicity
        else:
            return None  # No matching result found
    except Exception as e:
        print(f"[ERROR] Error querying memories: {e}")
        return None
    

def search_past_events(query_text: str):
    memory_query = Query('Memories')
    
    # Filter for mainEvent containing keywords
    memory_query.contains('mainEvent', query_text)
    
    # Add filter to only get events in the past (eventCreatedAt < now)
    memory_query.less_than('eventCreatedAt', datetime.now())
    
    # Optional: sort by eventCreatedAt descending (latest past first)
    memory_query.descending('eventCreatedAt')
    
    try:
        results = memory_query.find()
        if results:
            return results
        else:
            return []
    except Exception as e:
        print(f"[ERROR] Error querying past events: {e}")
        return []
