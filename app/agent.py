import base64
import datetime
import json
import os
from zoneinfo import ZoneInfo
from typing import Optional

import requests
from dotenv import load_dotenv
import google.auth
from google import genai
from google.cloud import firestore, storage
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import (
    AgentEngineSandboxCodeExecutor,
)
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from app.a2ui_utils import a2ui_callback

# Load local environment variables
load_dotenv()

# Hardcoded Project ID as required (project number breaks Firestore on Agent Platform)
PROJECT_ID = "qwiklabs-gcp-01-f14e23f8d70e"
BUCKET_NAME = "devdesk-assistant-assets-qwiklabs-gcp-01-f14e23f8d70e"
DEPLOYMENT_METADATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json"
)


def _get_db():
    scopes = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/datastore",
    ]
    credentials, _ = google.auth.default(scopes=scopes)
    return firestore.Client(project=PROJECT_ID, credentials=credentials)


def _get_code_executor():
    """Initializes AgentEngineSandboxCodeExecutor using deployment_metadata.json."""
    sandbox_resource_name = None
    agent_engine_resource_name = None

    if os.path.exists(DEPLOYMENT_METADATA_PATH):
        try:
            with open(DEPLOYMENT_METADATA_PATH, "r") as f:
                metadata = json.load(f)
                sandbox_resource_name = metadata.get("sandbox_resource_name")
                agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
        except Exception:
            pass

    if sandbox_resource_name:
        return AgentEngineSandboxCodeExecutor(
            sandbox_resource_name=sandbox_resource_name
        )
    elif agent_engine_resource_name:
        return AgentEngineSandboxCodeExecutor(
            agent_engine_resource_name=agent_engine_resource_name
        )
    else:
        return AgentEngineSandboxCodeExecutor(
            agent_engine_resource_name=f"projects/{PROJECT_ID}/locations/us-central1/reasoningEngines/2924462885616746496"
        )


async def generate_support_badge_image(
    prompt_description: str,
    tool_context: ToolContext,
) -> str:
    """Generates an IT support badge or equipment icon image for DevDesk using gemini-3.1-flash-lite-image.

    Args:
        prompt_description: Description of the badge or IT asset image to generate (e.g. 'Server rack status badge').
        tool_context: ToolContext instance injected by ADK to save session artifacts.

    Returns:
        Public HTTPS URL of the generated image saved directly in Cloud Storage.
    """
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials, _ = google.auth.default(scopes=scopes)

        # 1. Generate image using gemini-3.1-flash-lite-image in global region
        genai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
            credentials=credentials,
        )

        full_prompt = (
            f"DevDesk IT Support asset badge: {prompt_description}. "
            "Clean, professional, high quality icon or badge."
        )

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=[full_prompt],
        )

        image_bytes = None
        mime_type = "image/png"

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not image_bytes:
            return "Error: No image bytes were returned by the image model."

        # 2. Save artifact to Playground Artifacts panel via tool_context.save_artifact
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        )
        artifact_filename = f"badge_{timestamp}.png"
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

        await tool_context.save_artifact(
            filename=artifact_filename,
            artifact=artifact_part,
        )

        # 3. Upload image bytes directly to public Cloud Storage bucket (no local file created)
        storage_client = storage.Client(project=PROJECT_ID, credentials=credentials)
        bucket = storage_client.bucket(BUCKET_NAME)

        blob_path = f"assets/images/{artifact_filename}"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_path}"
        return (
            f"Successfully generated support asset badge image!\n"
            f"Public URL: {public_url}"
        )
    except Exception as e:
        return f"Error generating image: {str(e)}"


async def generate_incident_animation_video(
    prompt_description: str, tool_context: ToolContext
) -> str:
    """Generates a short IT incident or system architecture status animation video using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Args:
        prompt_description: Description of the video clip to generate (e.g. 'Database server failover sequence', 'CPU spike incident animation', 'Network traffic surge pulse').
        tool_context: ToolContext for saving artifacts to the Playground panel.

    Returns:
        Confirmation message with public Cloud Storage URL.
    """
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials, _ = google.auth.default(scopes=scopes)

        # 1. Generate video using gemini-omni-flash-preview in global region
        genai_client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="global",
            credentials=credentials,
        )

        full_prompt = (
            f"DevDesk IT Incident & Support video animation: {prompt_description}. "
            "Clean, professional, high quality short IT status video clip."
        )

        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=full_prompt,
            response_format={
                "type": "video",
                "aspect_ratio": "16:9",
            },
        )

        video_bytes = None
        mime_type = "video/mp4"

        if (
            hasattr(interaction, "output_video")
            and interaction.output_video
            and getattr(interaction.output_video, "data", None)
        ):
            data_val = interaction.output_video.data
            if isinstance(data_val, str):
                video_bytes = base64.b64decode(data_val)
            elif isinstance(data_val, bytes):
                video_bytes = data_val

        if not video_bytes:
            return "Error: No video bytes were returned by gemini-omni-flash-preview model."

        # 2. Save artifact to Playground's Artifacts panel via tool_context.save_artifact
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        )
        artifact_filename = f"incident_video_{timestamp}.mp4"
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)

        await tool_context.save_artifact(
            filename=artifact_filename,
            artifact=artifact_part,
        )

        # 3. Upload video bytes directly to public Cloud Storage bucket (no local file created)
        storage_client = storage.Client(project=PROJECT_ID, credentials=credentials)
        bucket = storage_client.bucket(BUCKET_NAME)

        blob_path = f"assets/videos/{artifact_filename}"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_path}"
        return (
            f"Successfully generated IT incident animation video!\n"
            f"Public URL: {public_url}"
        )
    except Exception as e:
        return f"Error generating video: {str(e)}"


def geocode_address(address: str) -> str:
    """Turns a street address or location name into geographic coordinates (latitude, longitude) using the Geocoding API.

    Args:
        address: The street address or location description (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        Formatted string containing the formatted address, latitude, and longitude.
    """
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        if not api_key or api_key == "PASTE_KEY_HERE":
            return "Error: GOOGLE_MAPS_API_KEY is not configured in local .env file."

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address, "key": api_key}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed with status: {data.get('status', 'ZERO_RESULTS')}"

        result = data["results"][0]
        formatted_address = result.get("formatted_address", address)
        location = result.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        return f"Address: {formatted_address}\nLocation: {lat}, {lng}"
    except Exception as e:
        return f"Error during geocoding: {str(e)}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
) -> str:
    """Finds nearby places of a given type around a location using the Places API (New) REST endpoint.

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        place_type: Type of place to search for (e.g. 'restaurant', 'cafe', 'parking', 'bank').
        radius_meters: Search radius in meters (default 1000.0).

    Returns:
        List of nearby places with name, formatted address, and coordinates.
    """
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        if not api_key or api_key == "PASTE_KEY_HERE":
            return "Error: GOOGLE_MAPS_API_KEY is not configured in local .env file."

        url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        }
        body = {
            "includedTypes": [place_type.lower().strip()],
            "maxResultCount": 5,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_meters,
                }
            },
        }

        response = requests.post(url, headers=headers, json=body, timeout=5)
        response.raise_for_status()
        data = response.json()

        places = data.get("places", [])
        if not places:
            return f"No nearby places of type '{place_type}' found within {radius_meters}m."

        results = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "Unknown Name")
            address = p.get("formattedAddress", "N/A")
            loc = p.get("location", {})
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            results.append(
                f"- Name: {display_name}\n  Address: {address}\n  Location: {lat}, {lng}"
            )

        return "\n".join(results)
    except Exception as e:
        return f"Error searching nearby places: {str(e)}"


def get_github_system_status() -> str:
    """Fetches real-time operational status of GitHub services (Git, Actions, API, Copilot).

    Returns:
        A formatted string summarizing overall status and component statuses.
    """
    try:
        # Read API key from env var if provided (GitHub Status API doesn't require a key)
        api_key = os.getenv("GITHUB_STATUS_API_KEY", "")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = "https://www.githubstatus.com/api/v2/summary.json"
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()

        overall = data.get("status", {}).get("description", "Unknown")
        components = data.get("components", [])

        status_lines = [f"Overall GitHub Status: {overall}"]
        for comp in components:
            if comp.get("showcase"):
                status_lines.append(f"- {comp.get('name')}: {comp.get('status')}")

        incidents = data.get("incidents", [])
        if incidents:
            status_lines.append("\nActive Incidents:")
            for inc in incidents:
                status_lines.append(
                    f"- {inc.get('name')}: {inc.get('status')} (Impact: {inc.get('impact')})"
                )

        return "\n".join(status_lines)
    except Exception as e:
        return f"Error fetching GitHub system status: {str(e)}"


def upload_incident_log(
    ticket_id: str,
    log_content: str,
    filename: str = "incident.log",
) -> str:
    """Uploads diagnostic logs or error traces for a support ticket to Cloud Storage.

    Args:
        ticket_id: The ID of the ticket (e.g. 'TICK-101').
        log_content: The text content or stack trace log to upload.
        filename: Optional filename for the log file (default: 'incident.log').

    Returns:
        A confirmation message containing the public URL of the uploaded file.
    """
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials, _ = google.auth.default(scopes=scopes)
        client = storage.Client(project=PROJECT_ID, credentials=credentials)
        bucket = client.bucket(BUCKET_NAME)

        clean_ticket_id = ticket_id.strip().upper()
        clean_filename = filename.strip()
        blob_path = f"logs/{clean_ticket_id}/{clean_filename}"

        blob = bucket.blob(blob_path)
        blob.upload_from_string(log_content, content_type="text/plain")

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_path}"
        return (
            f"Successfully uploaded log for ticket {clean_ticket_id}.\n"
            f"Public URL: {public_url}"
        )
    except Exception as e:
        return f"Error uploading incident log: {str(e)}"


def search_tickets(status: str = "", severity: str = "") -> str:
    """Searches support tickets in Firestore with optional filters.

    Args:
        status: Optional filter by ticket status (e.g. 'OPEN', 'IN_PROGRESS', 'RESOLVED').
        severity: Optional filter by ticket severity (e.g. 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL').

    Returns:
        A list of matching tickets with their ID, title, status, severity, and assignee.
    """
    try:
        db = _get_db()
        query = db.collection("tickets")

        if status:
            query = query.where("status", "==", status.strip().upper())
        if severity:
            query = query.where("severity", "==", severity.strip().upper())

        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append(
                f"[{data.get('ticket_id')}] {data.get('title')} | Status: {data.get('status')} | Severity: {data.get('severity')} | Assignee: {data.get('assignee')}"
            )

        if not results:
            return "No tickets found matching the specified criteria."
        return "\n".join(results)
    except Exception as e:
        return f"Error searching tickets: {str(e)}"


def get_ticket_details(ticket_id: str) -> str:
    """Retrieves full details for a specific support ticket by its ID.

    Args:
        ticket_id: The unique identifier of the ticket (e.g. 'TICK-101').

    Returns:
        Detailed information including title, description, status, severity, assignee, and creation timestamp.
    """
    try:
        db = _get_db()
        doc_ref = db.collection("tickets").document(ticket_id.strip().upper())
        doc = doc_ref.get()

        if not doc.exists:
            return f"Ticket '{ticket_id}' was not found."

        data = doc.to_dict()
        return (
            f"Ticket ID: {data.get('ticket_id')}\n"
            f"Title: {data.get('title')}\n"
            f"Description: {data.get('description')}\n"
            f"Status: {data.get('status')}\n"
            f"Severity: {data.get('severity')}\n"
            f"Assignee: {data.get('assignee')}\n"
            f"Created At: {data.get('created_at')}"
        )
    except Exception as e:
        return f"Error fetching ticket details: {str(e)}"


def create_ticket(
    title: str,
    description: str,
    severity: str = "MEDIUM",
    assignee: str = "Unassigned",
) -> str:
    """Creates a new support ticket in Firestore.

    Args:
        title: Short summary of the issue.
        description: Detailed explanation of the bug or incident.
        severity: Severity level ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'). Default is 'MEDIUM'.
        assignee: Person or team assigned to resolve the issue. Default is 'Unassigned'.

    Returns:
        A confirmation message with the newly created ticket ID.
    """
    try:
        db = _get_db()
        # Generate next ticket ID
        docs = list(db.collection("tickets").stream())
        next_num = len(docs) + 101
        ticket_id = f"TICK-{next_num}"

        ticket = {
            "ticket_id": ticket_id,
            "title": title.strip(),
            "description": description.strip(),
            "status": "OPEN",
            "severity": severity.strip().upper(),
            "assignee": assignee.strip(),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        db.collection("tickets").document(ticket_id).set(ticket)
        return f"Successfully created ticket {ticket_id}: '{title}' with status OPEN and severity {severity.upper()}."
    except Exception as e:
        return f"Error creating ticket: {str(e)}"


def update_ticket_status(ticket_id: str, status: str) -> str:
    """Updates the status of an existing ticket in Firestore.

    Args:
        ticket_id: The ID of the ticket to update (e.g. 'TICK-101').
        status: The new status ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED').

    Returns:
        A confirmation message of the status update.
    """
    try:
        db = _get_db()
        clean_id = ticket_id.strip().upper()
        doc_ref = db.collection("tickets").document(clean_id)
        doc = doc_ref.get()

        if not doc.exists:
            return f"Ticket '{clean_id}' was not found."

        new_status = status.strip().upper()
        doc_ref.update({"status": new_status})
        return f"Updated status of ticket {clean_id} to '{new_status}'."
    except Exception as e:
        return f"Error updating ticket status: {str(e)}"


def calculate_expression(expression: str) -> str:
    """Evaluates a mathematical expression safely.

    Args:
        expression: A mathematical expression like '15 * 8' or '100 / 4'.

    Returns:
        The evaluated result as a string.
    """
    try:
        allowed_chars = set("0123456789+-*/(). ")
        if not set(expression).issubset(allowed_chars):
            return "Error: Expression contains unsupported characters."
        result = eval(expression, {"__builtins__": None}, {})
        return f"Result: {result}"
    except Exception as e:
        return f"Error evaluating expression: {str(e)}"


async def generate_memories_callback(callback_context: CallbackContext):
    """Sends session events to Memory Bank for extraction after each turn."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def memory_bank_service_builder():
    """Returns a VertexAiMemoryBankService pointed at the deployed Reasoning Engine."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-central1",
        agent_engine_id="2924462885616746496",
    )


a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = a2ui_schema_manager.generate_system_prompt(
    role_description=(
        "You are DevDesk Assistant, an IT and developer support assistant. "
        "You help engineers and IT teams manage support tickets, triage incidents, "
        "look up addresses and nearby places, check external system status (such as GitHub), "
        "generate support badges or asset images, run Python code in a safe sandbox environment, "
        "and track resolution status."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects. "
        "CRITICAL MEMORY DIRECTIVE: Always pay close attention to any user allergies or dietary restrictions "
        "mentioned in conversation. Make sure all user allergies are remembered across sessions using your memory bank, "
        "and always account for stated allergies in your responses, event catering suggestions, or place recommendations."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=_get_code_executor(),
    tools=[
        PreloadMemoryTool(),
        search_tickets,
        get_ticket_details,
        create_ticket,
        update_ticket_status,
        upload_incident_log,
        geocode_address,
        find_nearby_places,
        get_github_system_status,
        generate_support_badge_image,
        generate_incident_animation_video,
        calculate_expression,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)






