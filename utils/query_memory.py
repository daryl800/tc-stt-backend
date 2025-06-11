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
        memory_query = Query('Memories')

        # 1. Filter: eventCreatedAt < current one
        memory_query.less_than('eventCreatedAt', llmExtraction.eventCreatedAt)

        # 2. Filter by matching any tag (logical OR)
        tags = llmExtraction.tags or []
        locations = llmExtraction.location or []

        # Combine all keywords for searching
        keywords = set(tags + locations)
        print(f"[INFO] keywords for search: {keywords}")

        # If no keywords, just return nothing
        if not keywords:
            print("[INFO] No tags or locations to compare for search.")
            return []

        # Filter memories that contain at least one matching tag
        tag_subqueries = []
        for keyword in keywords:
            q = Query('Memories')
            q.contains('tags', keyword)
            tag_subqueries.append(q)

        # Combine with OR
        if tag_subqueries:
            combined_query = tag_subqueries[0]
            for q in tag_subqueries[1:]:
                combined_query = combined_query.or_(q)

            # Only AND if memory_query has existing filters
            if memory_query._where:
                memory_query = memory_query.and_(combined_query)
            else:
                memory_query = combined_query


        # Sort by latest first
        memory_query.descending('eventCreatedAt')

        # Execute the query
        results = memory_query.find()
        print(f"[INFO] Found {len(results)} past events matching the criteria.")
        # If no results, return empty list
        return results or []

    except Exception as e:
        print(f"[ERROR] Error querying past events: {e}")
        return []
