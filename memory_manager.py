import firebase_admin
from firebase_admin import credentials, firestore
from config import FIREBASE_CREDENTIALS_PATH

# Safe Firebase initialization
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Store a new chat message in Firestore
def store_message(user_id: str, personality: str, message: str, response: str):
    chat_ref = db.collection("chats").document(user_id)
    chat_data = chat_ref.get().to_dict()
    if chat_data is None:
        chat_data = {"messages": []}
    
    chat_data["messages"].append({
        "personality": personality,
        "user_message": message,
        "bot_response": response
    })
    chat_ref.set(chat_data)

# Get chat history
def get_chat_history(user_id: str):
    chat_ref = db.collection("chats").document(user_id)
    chat_data = chat_ref.get().to_dict()
    return chat_data["messages"] if chat_data else []
