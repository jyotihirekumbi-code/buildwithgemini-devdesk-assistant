import datetime
import google.auth
from google.cloud import firestore

# Hardcoded Project ID as required (project number breaks Firestore on Agent Platform)
PROJECT_ID = "qwiklabs-gcp-01-f14e23f8d70e"

def seed_firestore():
    scopes = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/datastore",
    ]
    credentials, _ = google.auth.default(scopes=scopes)
    db = firestore.Client(project=PROJECT_ID, credentials=credentials)

    tickets = [
        {
            "ticket_id": "TICK-101",
            "title": "Database connection pool exhaustion during peak hours",
            "description": "Intermittent timeouts observed between 14:00 and 16:00 UTC under heavy load.",
            "status": "OPEN",
            "severity": "HIGH",
            "assignee": "DevOps Team",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        {
            "ticket_id": "TICK-102",
            "title": "OAuth SSO callback error on mobile browsers",
            "description": "Mobile Safari users receive invalid redirect URL when logging in via Google SSO.",
            "status": "IN_PROGRESS",
            "severity": "MEDIUM",
            "assignee": "Frontend Lead",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        {
            "ticket_id": "TICK-103",
            "title": "Renew SSL certificates for api.devdesk.internal",
            "description": "Internal domain SSL cert expiring in 7 days. Renewal and deployment required.",
            "status": "RESOLVED",
            "severity": "LOW",
            "assignee": "Security Team",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    ]

    collection_ref = db.collection("tickets")
    for ticket in tickets:
        doc_ref = collection_ref.document(ticket["ticket_id"])
        doc_ref.set(ticket)
        print(f"Seeded ticket {ticket['ticket_id']}: {ticket['title']}")

    print("Firestore seeding complete!")

if __name__ == "__main__":
    seed_firestore()
