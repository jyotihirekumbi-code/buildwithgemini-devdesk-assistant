# My agent: DevDesk Assistant
One-liner: A conversational IT & Developer support assistant that helps software teams triage incidents, manage support tickets, and maintain contextual knowledge across support sessions.

Tool coverage:
- Memory: Remembers user role, tech stack preferences, active ticket IDs, and past resolution history across sessions.
- Tools: Search ticket database, create new support tickets, update ticket status/severity, and query knowledge base articles.
- Catalog/UI: Support ticket inventory, incident logs, and SLA summaries rendered as A2UI cards and tables.
- Image gen: Generates visual system status badges and architecture diagrams.
- Sandbox: Evaluates stack traces, computes SLA resolution times, and parses error logs.

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch: Code sandbox for stack trace analysis & SLA calculations, Firestore ticket storage, Vertex AI Memory Bank.
