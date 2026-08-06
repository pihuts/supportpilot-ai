# SupportPilot AI

An n8n workflow that turns a raw support message into a classified, prioritized, answered, and tracked ticket.

![SupportPilot AI workflow](screenshots/SupportPilot%20AI.png)

## What it does

1. Receives a support message via webhook.
2. GPT-5.6 Luna classifies category, priority, and sentiment.
3. The AI drafts a reply and estimates confidence.
4. The ticket is logged to Google Sheets.
5. Low-confidence, urgent, or flagged tickets are escalated to the support team by email.
6. The caller gets an immediate JSON response with the AI answer.

No vector database required. Company policy lives in environment variables, so it is easy to update.

## Current tech

- n8n webhooks + AI Agent (LangChain) nodes
- OpenAI GPT-5.6 Luna with structured JSON output
- Google Sheets logging
- Gmail escalation
- Human-in-the-loop: `needs_human` flag controls escalation

## Setup

1. Import `SupportPilot AI.json`.
2. Set environment variables:

   | Variable | Purpose |
   |---|---|
   | `SUPPORT_SHEET_ID` | Google Sheet ID for tickets |
   | `SUPPORT_EMAIL_TO` | Escalation inbox |
   | `SUPPORT_COMPANY_NAME` | Company name for AI context |
   | `SUPPORT_COMPANY_INFO` | Policies, products, refund rules |

3. Connect OpenAI, Google Sheets, and Gmail credentials.
4. Create a sheet tab `Tickets` with headers:

   ```
   Ticket ID, Date, Customer, Email, Channel, Category, Priority, Sentiment, Confidence, Summary, Suggested Reply, Escalated, Status
   ```

5. Activate the workflow.

## Test it

```bash
curl -X POST https://your-n8n.com/webhook/supportpilot-triage \
  -H "Content-Type: application/json" \
  -d '{"message":"I was charged twice for my subscription","customer_name":"Alice","email":"alice@example.com"}'
```

