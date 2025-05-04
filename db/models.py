from datetime import datetime
import firebase_admin
from firebase_admin import firestore
from typing import Dict, List, Optional, Any

# The firebase connector
from db.firebase import db

class Request:
    """Model for handling customer requests that need supervisor attention"""
    collection_name = 'requests'

    def __init__(self, id: Optional[str] = None, customer_phone: str = None,
                 query: str = None, call_id: str = None, status: str = "pending",
                 created_at: datetime = None, updated_at: datetime = None,
                 resolved_at: datetime = None, answer: str = None,
                 unresolved_reason: str = None, category: str = None):
        self.id = id
        self.customer_phone = customer_phone
        self.query = query
        self.call_id = call_id
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.resolved_at = resolved_at
        self.answer = answer
        self.unresolved_reason = unresolved_reason
        self.category = category

    @classmethod
    def create(cls, customer_phone: str, query: str, call_id: str, category: str) -> 'Request':
        """Create a new request in the database"""
        now = datetime.now()
        new_request = {
            'customer_phone': customer_phone,
            'query': query,
            'call_id': call_id,
            'status': 'pending',
            'category': category,
            'created_at': now,
            'updated_at': now
        }

        # Add to Firestore
        doc_ref = db.collection(cls.collection_name).document()
        doc_ref.set(new_request)

        # Create and return instance with the new ID
        new_request['id'] = doc_ref.id
        return cls(**new_request)

    @classmethod
    def get(cls, request_id: str) -> Optional['Request']:
        """Get a request by ID"""
        doc = db.collection(cls.collection_name).document(request_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return cls(**data)
        return None

    @classmethod
    def get_pending_requests(cls) -> List['Request']:
        """Get all pending requests"""
        requests = []
        query = db.collection(cls.collection_name).where('status', '==', 'pending').order_by('created_at')

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            requests.append(cls(**data))

        return requests

    @classmethod
    def get_request_history(cls, limit: int = 50) -> List['Request']:
        """Get request history"""
        requests = []
        query = db.collection(cls.collection_name).order_by(
            'created_at', direction=firestore.Query.DESCENDING
        ).limit(limit)

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            requests.append(cls(**data))

        return requests

    def resolve(self, answer: str) -> bool:
        """Resolve this request with an answer"""
        now = datetime.now()
        update_data = {
            'status': 'resolved',
            'answer': answer,
            'resolved_at': now,
            'updated_at': now
        }

        db.collection(self.collection_name).document(self.id).update(update_data)

        # Update instance
        self.status = 'resolved'
        self.answer = answer
        self.resolved_at = now
        self.updated_at = now

        return True

    def mark_unresolved(self, reason: str = "Timed out") -> bool:
        """Mark request as unresolved"""
        now = datetime.now()
        update_data = {
            'status': 'unresolved',
            'unresolved_reason': reason,
            'updated_at': now
        }

        db.collection(self.collection_name).document(self.id).update(update_data)

        # Update instance
        self.status = 'unresolved'
        self.unresolved_reason = reason
        self.updated_at = now

        return True

    @classmethod
    def has_pending_request_for_call(cls, call_id: str) -> bool:
        """Check if there is a pending request for a specific call ID."""
        query = db.collection(cls.collection_name).where('call_id', '==', call_id).where('status', '==', 'pending').get()
        query = query.stream()
        for i in query:
            return True, i.id
        return False, None

    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary"""
        return {
            'id': self.id,
            'customer_phone': self.customer_phone,
            'query': self.query,
            'call_id': self.call_id,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'resolved_at': self.resolved_at,
            'answer': self.answer,
            'unresolved_reason': self.unresolved_reason
        }


class KnowledgeBase:
    """Model for managing the AI's learned knowledge"""
    collection_name = 'knowledge_base'

    def __init__(self, id: str = None, key_phrase: str = None,
                 question: str = None, answer: str = None,
                 created_at: datetime = None, updated_at: datetime = None,
                 created_by: str = None):
        self.id = id
        self.key_phrase = key_phrase
        self.question = question
        self.answer = answer
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.created_by = created_by

    @classmethod
    def create(cls, key_phrase: str, question: str, answer: str,
               created_by: str = "system") -> 'KnowledgeBase':
        """Add new knowledge to the knowledge base"""
        now = datetime.now()
        new_knowledge = {
            'key_phrase': key_phrase,
            'question': question,
            'answer': answer,
            'created_at': now,
            'updated_at': now,
            'created_by': created_by
        }

        # Check if knowledge already exists
        existing = db.collection(cls.collection_name).where('key_phrase', '==', key_phrase).limit(1).get()

        if len(existing) > 0:
            # Update existing knowledge
            doc_id = existing[0].id
            db.collection(cls.collection_name).document(doc_id).update({
                'answer': answer,
                'updated_at': now
            })
            new_knowledge['id'] = doc_id
        else:
            # Add new knowledge
            doc_ref = db.collection(cls.collection_name).document()
            doc_ref.set(new_knowledge)
            new_knowledge['id'] = doc_ref.id

        return cls(**new_knowledge)

    @classmethod
    def search(cls, query: str) -> List['KnowledgeBase']:
        """Search knowledge base for relevant information"""
        results = []
        all_knowledge = db.collection(cls.collection_name).stream()

        # Simple search
        #(I was thinking we could have a db of key_phrases and we update the db with new key phrases)
        # (so searching for the key phrase would be fixed, defined and faster)
        query_terms = query.lower().split()

        for doc in all_knowledge:
            data = doc.to_dict()
            key_phrase = data.get('key_phrase', '').lower()

            # Check if any term is in the key phrase
            if any(term in key_phrase for term in query_terms):
                data['id'] = doc.id
                results.append(cls(**data))

        return results

    @classmethod
    def get_all(cls) -> List['KnowledgeBase']:
        """Get all knowledge base entries"""
        entries = []
        for doc in db.collection(cls.collection_name).stream():
            data = doc.to_dict()
            data['id'] = doc.id
            entries.append(cls(**data))
        return entries

    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary"""
        return {
            'id': self.id,
            'key_phrase': self.key_phrase,
            'question': self.question,
            'answer': self.answer,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'created_by': self.created_by
        }


class CallHistory:
    """Model for tracking call metrics and history (optional)"""
    collection_name = 'call_history'

    def __init__(self, id: Optional[str] = None, customer_phone: str = None,
                 start_time: datetime = None, end_time: datetime = None, duration_seconds: int = 0,
                 ai_handled: bool = True, request_id: Optional[str] = None, recording_url: Optional[str] = None):
        self.id = id
        self.customer_phone = customer_phone
        self.start_time = start_time or datetime.now()
        self.end_time = end_time
        self.duration_seconds = duration_seconds
        self.ai_handled = ai_handled
        self.request_id = request_id
        self.recording_url = recording_url  # we may need to store the conversation for reference

    @classmethod
    def create(cls, customer_phone: str) -> 'CallHistory':
        """Record a new call"""
        new_call = {
            'customer_phone': customer_phone,
            'start_time': datetime.now(),
            'ai_handled': True
        }

        doc_ref = db.collection(cls.collection_name).document()
        doc_ref.set(new_call)

        new_call['id'] = doc_ref.id
        return cls(**new_call)

    def set_ai_handled(self, handled: bool) -> None:
        """Set whether the AI handled the request"""
        new_data = {
            'ai_handled': handled,
            'updated_at': datetime.now()
        }
        db.collection(self.collection_name).document(self.id).update(new_data)
        self.ai_handled = handled
        self.updated_at = new_data['updated_at']

    def end_call(self, escalated: bool = False, request_id: Optional[str] = None) -> 'CallHistory':
        """End the call and calculate duration"""
        now = datetime.now()
        duration = int((now - self.start_time).total_seconds())

        update_data = {
            'end_time': now,
            'duration_seconds': duration,
            'ai_handled': not escalated   # set to true if the ai successfully handled the call
        }

        if request_id:
            update_data['request_id'] = request_id

        db.collection(self.collection_name).document(self.id).update(update_data)

        # Update instance
        self.end_time = now
        self.duration_seconds = duration
        self.ai_handled = not escalated
        self.request_id = request_id

        return self

    @classmethod
    def get_all(cls) -> List['CallHistory']:
        """Get all call history entries"""
        calls = []
        for doc in db.collection(cls.collection_name).stream():
            data = doc.to_dict()
            data['id'] = doc.id
            calls.append(cls(**data))
        return calls

    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary"""
        return {
            'id': self.id,
            'customer_phone': self.customer_phone,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_seconds': self.duration_seconds,
            'ai_handled': self.ai_handled,
            'request_id': self.request_id,
            'recording_url': self.recording_url
        }