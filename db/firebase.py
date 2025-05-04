import firebase_admin
from firebase_admin import credentials, firestore

# Path to the downloaded JSON key
cred = credentials.Certificate("/home/oladev/ai-agent/db/engine/firebase.json")
firebase_admin.initialize_app(cred)

# Initialize Firestore DB
db = firestore.client()
