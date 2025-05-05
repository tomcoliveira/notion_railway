# src/main.py
import os
import requests
from flask import Flask, request, jsonify, redirect, session
from notion_client import Client

app = Flask(__name__)
# Secret key for session management (replace with a strong secret in production)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key")

# --- Notion OAuth Configuration ---
NOTION_CLIENT_ID = os.environ.get("NOTION_CLIENT_ID")
NOTION_CLIENT_SECRET = os.environ.get("NOTION_CLIENT_SECRET")
# Use the Railway variable if available, otherwise default to localhost
NOTION_REDIRECT_URI = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "http://localhost:8080") + "/notion/oauth-callback"

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

# Global variable to store the access token (temporary solution for v1)
# In production, this should be stored securely per user (e.g., database)
notion_access_token = None
notion_workspace_id = None
notion_workspace_name = None
notion_workspace_icon = None
notion_bot_id = None

# --- Helper Function to get Notion Client ---
def get_notion_client():
    """Returns an initialized Notion client if token exists."""
    global notion_access_token
    if not notion_access_token:
        # In v1, we might need to redirect to auth or return an error
        # For now, let's assume the token is obtained before calling endpoints
        # raise Exception("Notion token not available. Please authorize first.")
        print("Warning: Notion token not available.")
        return None
    return Client(auth=notion_access_token)

# --- OAuth Routes ---
@app.route("/notion/authorize")
def notion_authorize():
    """Redirects the user to Notion's authorization page."""
    if not NOTION_CLIENT_ID or not NOTION_REDIRECT_URI:
        return "OAuth Client ID or Redirect URI not configured.", 500

    auth_url = f"{NOTION_AUTH_URL}?client_id={NOTION_CLIENT_ID}&response_type=code&owner=user&redirect_uri={NOTION_REDIRECT_URI}"
    print(f"DEBUG: Redirecting to Notion Auth URL: {auth_url}")
    return redirect(auth_url)

@app.route("/notion/oauth-callback")
def notion_oauth_callback():
    """Handles the callback from Notion after authorization."""
    global notion_access_token, notion_workspace_id, notion_workspace_name, notion_workspace_icon, notion_bot_id

    error = request.args.get("error")
    if error:
        return f"Error during Notion authorization: {error}", 400

    code = request.args.get("code")
    if not code:
        return "Authorization code not found in callback.", 400

    if not NOTION_CLIENT_ID or not NOTION_CLIENT_SECRET or not NOTION_REDIRECT_URI:
        return "OAuth credentials or Redirect URI not configured.", 500

    # Exchange code for access token
    try:
        print(f"DEBUG: Requesting access token from: {NOTION_TOKEN_URL}")
        response = requests.post(
            NOTION_TOKEN_URL,
            auth=(NOTION_CLIENT_ID, NOTION_CLIENT_SECRET),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": NOTION_REDIRECT_URI,
            },
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        token_data = response.json()
        print(f"DEBUG: Token data received: {token_data}")

        notion_access_token = token_data.get("access_token")
        notion_workspace_id = token_data.get("workspace_id")
        notion_workspace_name = token_data.get("workspace_name")
        notion_workspace_icon = token_data.get("workspace_icon")
        notion_bot_id = token_data.get("bot_id")

        if not notion_access_token:
             return "Access token not found in Notion response.", 500

        print(f"Access Token received and stored (globally): {notion_access_token[:10]}...")
        # Store token in session as well, maybe useful later
        session['notion_access_token'] = notion_access_token

        return jsonify({
            "message": "Notion authorization successful! Token obtained.",
            "workspace_id": notion_workspace_id,
            "workspace_name": notion_workspace_name,
            "workspace_icon": notion_workspace_icon,
            "bot_id": notion_bot_id
        })

    except requests.exceptions.RequestException as e:
        print(f"ERROR: RequestException during token exchange: {e}")
        if e.response is not None:
            print(f"ERROR: Response status: {e.response.status_code}")
            print(f"ERROR: Response body: {e.response.text}")
        return f"Error exchanging code for token: {e}", 500
    except Exception as e:
        print(f"ERROR: Unexpected error during token exchange: {e}")
        return f"An unexpected error occurred: {e}", 500

# --- Basic Home Route ---
@app.route("/")
def home():
    return jsonify({"message": "Welcome to Alcides Notion API v1"})

# --- Cycle 1 Endpoints (Placeholder - To be implemented) ---

@app.route("/notion/databases/<string:database_id>/items", methods=["POST"])
def create_database_item(database_id):
    """Creates an item in a Notion database."""
    client = get_notion_client()
    if not client:
        return jsonify({"error": "Not authorized. Please go to /notion/authorize"}), 401

    data = request.json
    if not data or 'properties' not in data:
        return jsonify({"error": "Missing 'properties' in request body"}), 400

    try:
        # Ensure parent is correctly formatted if not provided
        if 'parent' not in data:
             data['parent'] = {'database_id': database_id}
        elif data['parent'].get('database_id') != database_id:
             # Prevent creating in a different DB than the URL specifies
             return jsonify({"error": "Parent database ID mismatch"}), 400

        print(f"DEBUG: Creating item in DB {database_id} with properties: {data['properties']}")
        new_item = client.pages.create(**data)
        return jsonify(new_item), 201
    except Exception as e:
        print(f"ERROR creating Notion item: {e}")
        # Attempt to parse NotionClientError if possible
        error_message = str(e)
        try:
            # Notion errors often have a JSON body
            error_body = getattr(e, 'body', None)
            if error_body:
                error_message = f"{e} - Body: {error_body}"
        except Exception:
            pass # Keep original error message
        return jsonify({"error": f"Failed to create item in Notion database {database_id}", "details": error_message}), 500

@app.route("/notion/pages/<string:page_id>", methods=["PATCH"])
def update_database_item(page_id):
    """Updates properties of a Notion page (database item)."""
    client = get_notion_client()
    if not client:
        return jsonify({"error": "Not authorized. Please go to /notion/authorize"}), 401

    data = request.json
    if not data or 'properties' not in data:
        return jsonify({"error": "Missing 'properties' in request body"}), 400

    try:
        print(f"DEBUG: Updating page {page_id} with properties: {data['properties']}")
        updated_item = client.pages.update(page_id=page_id, properties=data['properties'])
        return jsonify(updated_item)
    except Exception as e:
        print(f"ERROR updating Notion page {page_id}: {e}")
        error_message = str(e)
        try:
            error_body = getattr(e, 'body', None)
            if error_body:
                error_message = f"{e} - Body: {error_body}"
        except Exception:
            pass
        return jsonify({"error": f"Failed to update Notion page {page_id}", "details": error_message}), 500

@app.route("/notion/databases/<string:database_id>/query", methods=["POST"])
def query_database(database_id):
    """Queries a Notion database based on filters."""
    client = get_notion_client()
    if not client:
        return jsonify({"error": "Not authorized. Please go to /notion/authorize"}), 401

    query_params = request.json or {}
    # Default to empty filter if not provided
    filter_data = query_params.get('filter')
    sorts_data = query_params.get('sorts')
    start_cursor = query_params.get('start_cursor')
    page_size = query_params.get('page_size', 100) # Default page size

    try:
        print(f"DEBUG: Querying DB {database_id} with filter: {filter_data}")
        results = client.databases.query(
            database_id=database_id,
            filter=filter_data,
            sorts=sorts_data,
            start_cursor=start_cursor,
            page_size=page_size
        )
        return jsonify(results)
    except Exception as e:
        print(f"ERROR querying Notion database {database_id}: {e}")
        error_message = str(e)
        try:
            error_body = getattr(e, 'body', None)
            if error_body:
                error_message = f"{e} - Body: {error_body}"
        except Exception:
            pass
        return jsonify({"error": f"Failed to query Notion database {database_id}", "details": error_message}), 500

# --- Add other endpoints as needed (GET page, GET database etc.) ---

# --- Run the App ---
if __name__ == "__main__":
    # Use 0.0.0.0 to be accessible externally (like on Railway)
    # Use port 8080 as a common practice for web apps
    app.run(host="0.0.0.0", port=8080, debug=True) # Debug=True for development

