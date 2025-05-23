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
# Ensure https:// is prepended to the Railway domain
railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_domain:
    # Prepend https:// if not already present (unlikely for Railway var, but safe)
    if not railway_domain.startswith(("http://", "https://")):
        base_url = "https://" + railway_domain
    else:
        base_url = railway_domain # Assume it includes the protocol if it starts with http/https
else:
    base_url = "http://localhost:8080" # Default for local dev

NOTION_REDIRECT_URI = base_url + "/notion/oauth-callback"

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
    """Returns an initialized Notion client if token exists in session."""
    access_token = session.get("notion_access_token") # Get from session
    if not access_token:
        print("Warning: Notion token not available in session.")
        return None
    return Client(auth=access_token)

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
        # Store token in session
        session["notion_access_token"] = notion_access_token
        # Store other potentially useful info in session too
        session["notion_workspace_id"] = notion_workspace_id
        session["notion_workspace_name"] = notion_workspace_name
        session["notion_bot_id"] = notion_bot_id

        print(f"Access Token received and stored in session: {session['notion_access_token'][:10]}...")

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



# --- Debug Endpoint ---
@app.route("/notion/check-token")
def notion_check_token():
    """Checks if the Notion token exists in the current session."""
    access_token = session.get("notion_access_token")
    if access_token:
        return jsonify({
            "status": "Token found in session!",
            "token_start": access_token[:10] + "...",
            "workspace_id": session.get("notion_workspace_id"),
            "workspace_name": session.get("notion_workspace_name")
        })
    else:
        return jsonify({"status": "Token NOT found in session."}), 404




# --- Temporary Test Endpoint for Creation ---
@app.route("/notion/test-create-item/<string:database_id>")
def test_create_item_endpoint(database_id):
    """Temporary endpoint to test item creation from the browser session."""
    client = get_notion_client()
    if not client:
        return jsonify({"error": "Not authorized. Please go to /notion/authorize first."}), 401

    # Hardcoded test data
    test_item_title = "Teste API Alcides v1.6"
    # Assuming the main title property is named "Título"
    test_properties = {
        "Título": {
            "title": [
                {
                    "text": {
                        "content": test_item_title
                    }
                }
            ]
        }
    }

    try:
        print(f"DEBUG: Attempting to create test item '{test_item_title}' in DB {database_id}")
        new_item = client.pages.create(
            parent={"database_id": database_id},
            properties=test_properties
        )
        print(f"DEBUG: Test item created successfully: {new_item.get('id')}")
        return jsonify({
            "message": f"Successfully created test item '{test_item_title}'!",
            "item_id": new_item.get('id'),
            "item_url": new_item.get('url')
        }), 201
    except Exception as e:
        print(f"ERROR creating test item in DB {database_id}: {e}")
        error_message = str(e)
        try:
            error_body = getattr(e, 'body', None)
            if error_body:
                error_message = f"{e} - Body: {error_body}"
        except Exception:
            pass
        return jsonify({"error": f"Failed to create test item in Notion database {database_id}", "details": error_message}), 500

