from leancloud import Object, Query
from datetime import datetime
from models.memory_item import MemoryItem

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
    


def search_past_events(llmExtraction: MemoryItem):
    """
    Search for past memory events that match the current query by comparing tags and location.
    Only returns events created before the current one.
    """
    try:
        # 1. Filter: eventCreatedAt < current one
        date_query = Query('Memories')
        date_query.less_than('eventCreatedAt', llmExtraction.eventCreatedAt)

        # 2. Filter by matching any tag (logical OR)
        tags = llmExtraction.tags or []
        locations = llmExtraction.location or []

        # Combine all keywords for searching
        keywords = set(tags + locations)
        print(f"[INFO] keywords for search: {keywords}")

        if not keywords:
            print("[INFO] No tags or locations to compare for search.")
            return []

        # Create OR subqueries for tag matches
        tag_subqueries = []
        for keyword in keywords:
            q = Query('Memories')
            q.contains('tags', keyword)
            tag_subqueries.append(q)

        print(f"[INFO] Created {len(tag_subqueries)} tag subqueries for search.")

        # Combine tag subqueries with OR
        if len(tag_subqueries) > 1:
            combined_query = tag_subqueries[0]
            for q in tag_subqueries[1:]:
                combined_query = combined_query.or_(q)  
            final_query = Query.and_(date_query, combined_query)
        elif len(tag_subqueries) == 1:
            print(f"[INFO] date_query: {date_query._where} tag subqueries for search.")
            print(f"[INFO] tag_subqueries: {tag_subqueries[0]._where}")  
            final_query = Query.and_(date_query, tag_subqueries[0])

        else:
            final_query = date_query


        # Sort by latest first
        final_query.descending('eventCreatedAt')

        # Execute
        results = final_query.find()
        print(f"[INFO] Found {len(results)} past events matching the criteria.")
        for (result) in results:
            print(f"[INFO] Past event: {result.get('transcription')} at {result.get('eventCreatedAt')}")
        return results or []

    except Exception as e:
        print(f"[ERROR] Error querying past events: {e}")
        return []
