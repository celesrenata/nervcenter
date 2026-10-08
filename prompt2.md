# NerveCenter Addendum: Personal Operations & Attention Engine

**Addendum version:** 0.1  
**Parent specification:** NerveCenter v0.2  
**Status:** Additional implementation specification  
**Purpose:** Extend NerveCenter from an engineering operating system into a personal operational assistant.

---

# 1. Objective

NerveCenter must be capable of understanding and managing important day-to-day information from:

```text
Email
Messages
Voicemail
Calls where accessible
Calendar
Reminders
Personal tasks
Notifications
NerveCenter goals
Engineering systems
```

The system's responsibility is not to reproduce separate inboxes.

Its responsibility is to determine:

```text
What actually matters?

What requires action?

What am I waiting on?

What did I promise somebody?

What deadline is approaching?

What have I repeatedly ignored?

What can safely disappear?

What should be placed directly in front of me right now?
```

The primary abstraction is therefore:

# ATTENTION

---

# 2. Product Principle

Traditional systems operate like:

```text
EMAIL
  ↓
700 messages

MESSAGES
  ↓
38 conversations

VOICEMAIL
  ↓
6 recordings

CALENDAR
  ↓
events

TASKS
  ↓
lists
```

NerveCenter instead produces:

```text
                    COMMUNICATIONS
                          │
           ┌──────────────┼───────────────┐
           ▼              ▼               ▼
        Email          Messages        Voicemail
           │              │               │
           └──────────────┼───────────────┘
                          ▼
                 Understanding Layer
                          │
                          ▼
                    Commitments
                    Deadlines
                    Requests
                    Decisions
                    Relationships
                    Waiting-ons
                    Follow-ups
                          │
                          ▼
                    ATTENTION ENGINE
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
         NOW             LATER           IGNORE
          │
          ▼
   iPhone / Watch
```

The user should not need to manually organize everything first.

---

# 3. Core User Experience

The primary Personal Operations screen should look approximately like:

```text
GOOD MORNING

You have 4 things that actually matter.

1. 🔴 Reply to Alice
   She asked yesterday whether Friday still works.
   You haven't responded.
   19 hours ago

2. 🟠 Call pharmacy
   Voicemail says prescription requires clarification.
   Office closes at 5 PM.

3. 🟠 Insurance paperwork
   Email requests documents by Wednesday.
   2 days remaining.

4. 🟡 HelloDJ
   Zoo needs approval for the production deployment.

Everything else:
142 messages summarized / suppressed
```

That is the product.

Not:

```text
YOU HAVE 146 NOTIFICATIONS
```

---

# 4. Personal Operations Architecture

Add:

```text
NerveCenter
│
├── Personal Operations Plane
│   │
│   ├── Communication Ingestion
│   │
│   ├── Contact Resolution
│   │
│   ├── Conversation Threads
│   │
│   ├── Commitment Extraction
│   │
│   ├── Deadline Extraction
│   │
│   ├── Attention Engine
│   │
│   ├── Follow-Up Engine
│   │
│   ├── Briefing Engine
│   │
│   └── Response Assistant
│
├── Engineering Plane
│
├── Goal Plane
│
└── Knowledge Plane
```

Personal and engineering state remain distinct but may link through explicit entities.

---

# 5. New Core Entities

Add:

```text
Person
ContactIdentity
Conversation
Communication
Email
Message
Voicemail
Call
Commitment
Request
Deadline
FollowUp
AttentionItem
Reminder
CalendarEvent
ResponseDraft
PersonalTask
```

---

# 6. Unified Person Model

NerveCenter should recognize that:

```text
alice@example.com

+1-555-...

Alice Smith in Messages

Alice in Contacts

a voicemail from the same number
```

represent the same Person.

Example:

```text
Person: Alice Smith
│
├── email
│   └── alice@example.com
│
├── phone
│   └── +15551234567
│
├── Messages identity
│
└── conversation history
```

Identity merging must be conservative.

Uncertain matches remain separate until confirmed.

---

# 7. Communication Object

Normalize communication into:

```json
{
  "communication_id": "...",

  "channel": "email|imessage|sms|rcs|voicemail",

  "direction": "incoming|outgoing",

  "sender": "...",

  "recipients": [],

  "timestamp": "...",

  "thread_id": "...",

  "content_ref": "...",

  "attachments": [],

  "classification": {},

  "sensitivity": "...",

  "source": "..."
}
```

Raw content may live encrypted outside the primary knowledge graph.

---

# 8. Event Types

Add:

```text
communication.received
communication.sent
communication.read
communication.responded
communication.archived

email.received
email.sent

message.received
message.sent

voicemail.received
voicemail.transcribed

call.missed

commitment.detected
commitment.completed
commitment.overdue

request.detected
request.resolved

deadline.detected
deadline.updated
deadline.passed

followup.created
followup.triggered
followup.completed

attention.created
attention.promoted
attention.demoted
attention.acknowledged
attention.snoozed
attention.resolved

briefing.generated
```

---

# 9. Email Integration

Email should use provider APIs wherever possible.

Initial adapters:

```text
Gmail API

Microsoft Graph

IMAP / SMTP

optional provider-specific APIs
```

Email ingestion should support:

```text
message
thread
sender
recipients
subject
timestamp
attachments metadata
labels/folders
read state
reply relationships
```

---

# 10. Email Actions

NerveCenter may:

```text
summarize

classify

extract requests

extract deadlines

identify commitments

identify invoices / appointments / confirmations

create tasks

draft responses

recommend archive

recommend unsubscribe

surface follow-ups
```

Actual external actions require appropriate authorization.

Examples:

```text
send email
delete
archive
unsubscribe
forward
```

must follow explicit policy.

---

# 11. Messages Integration

Messages require multiple ingestion strategies.

## Strategy A — macOS Personal Relay

Preferred broad local integration.

Run:

```text
nerve-personal-relay
```

on the user's M5 Max or another trusted Mac.

Messages synchronized onto the Mac may be ingested locally.

The relay must:

```text
operate read-only against source message storage

require explicit macOS permissions

never modify the Messages database

detect schema incompatibility

fail closed when parsing is uncertain

send normalized events to NerveCenter
```

This is a personal/local integration and should not be treated as an App Store-portable API.

---

# 12. iPhone Messages Bridge

The iPhone client may additionally use supported Shortcuts automations for selected communication events.

Apple supports incoming Message-triggered Shortcuts automations based on criteria such as sender or message content.

This is particularly useful for:

```text
VIP contacts

high-priority senders

specific keywords

backup delivery when the Mac is offline
```

The iPhone Message Filter API must NOT be treated as a general inbox API: Apple's IdentityLookup path handles unknown-sender SMS/MMS filtering and excludes known-contact messages and iMessage.

---

# 13. Sending Messages

NerveCenter may prepare suggested replies.

Default policy:

```text
AI drafts

human sends
```

Example:

```text
Alice asked whether you're still free Friday.

Suggested reply:

"Yep, Friday still works for me. What time were you thinking?"

[Send]
[Edit]
[Later]
```

Automatic sending should require explicit per-person/per-category authorization.

---

# 14. Voicemail Integration

Voicemail ingestion should support multiple adapters.

Priority:

```text
1. carrier/provider API if available

2. carrier voicemail-to-email integration

3. user Share Sheet → NerveCenter

4. imported audio/transcript

5. future supported OS integration
```

Apple's Phone app exposes voicemail playback, transcript viewing, and sharing to the user, but the NerveCenter architecture must not assume a general third-party Visual Voicemail inbox API exists.

---

# 15. Local Voicemail Processing

Once voicemail audio is available:

```text
audio
  ↓
local transcription
  ↓
speaker/contact resolution
  ↓
summary
  ↓
request extraction
  ↓
deadline extraction
  ↓
Attention Engine
```

Preferred transcription:

```text
local Whisper-compatible model
```

Example:

```text
VOICEMAIL

Dr. Smith's office

"Please call us regarding your appointment."

Detected:
CALLBACK REQUIRED

Office:
open until 5 PM

Priority:
HIGH
```

---

# 16. Commitment Detection

This is a critical feature.

NerveCenter should detect statements made by the user such as:

```text
"I'll send it tonight."

"I'll call tomorrow."

"I can get that done Friday."

"Remind me next week."

"I'll take care of it."

"I'll check and get back to you."
```

These become:

```text
Commitment
```

Example:

```json
{
  "commitment": "Send Alice the document",

  "created_from": "message:8821",

  "due": "2026-10-05T23:59",

  "confidence": 0.91,

  "status": "OPEN"
}
```

This solves an important failure mode:

**things the user promised to do but never formally turned into a task.**

---

# 17. Request Detection

Incoming communications should be inspected for requests.

Examples:

```text
"Can you send me..."

"Please call..."

"Are you available..."

"Could you review..."

"Need this by Friday."

"Can you confirm..."
```

A request does not automatically become high priority.

It becomes a candidate for the Attention Engine.

---

# 18. Deadline Detection

Extract:

```text
explicit dates

relative dates

business-hour constraints

appointments

reservation deadlines

payment due dates

submission windows

expiration dates
```

Example:

```text
"We need the form by Tuesday."
```

becomes:

```text
Deadline:
Tuesday

Associated:
form submission

Source:
email X
```

---

# 19. Waiting-On Detection

NerveCenter should track outgoing requests that received no response.

Example:

```text
You:
"Can you send me the deployment credentials?"

3 days later:
No response.
```

Produces:

```text
WAITING ON
Sam

Deployment credentials

3 days

[Follow up]
```

---

# 20. AttentionItem

The principal output of the Personal Operations Plane is:

```json
{
  "attention_id": "...",

  "reason": "...",

  "priority": 0.92,

  "urgency": 0.81,

  "importance": 0.96,

  "due": "...",

  "entities": [],

  "sources": [],

  "suggested_action": "...",

  "status": "OPEN"
}
```

---

# 21. Attention Scoring

Initial ranking may consider:

```text
direct request

explicit deadline

deadline proximity

sender importance

existing relationship

unanswered direct question

user commitment

financial consequence

appointment consequence

repeated contact

previously snoozed item

missed follow-up

goal relationship

engineering incident severity
```

Initial scoring must be deterministic and explainable.

Do NOT begin with an opaque ML ranking model.

---

# 22. Explain Priority

Every AttentionItem must answer:

> Why are you showing me this?

Example:

```text
HIGH PRIORITY

Why:

• Direct question
• From a person you frequently respond to
• You have not replied
• 19 hours old
• Discussion references plans for tomorrow
```

---

# 23. User Feedback

Actions teach NerveCenter:

```text
Important

Not important

Never alert me about this

Always show me messages from this person

Snooze

Handled

This can wait

This sender is noise
```

This feedback adjusts future prioritization.

---

# 24. Do Not Become Another Notification Machine

The system must actively suppress low-value notifications.

Default philosophy:

```text
100 events
  ↓
12 potentially relevant
  ↓
4 actionable
  ↓
2 urgent
```

Only those two may need to interrupt the user.

Everything else remains available in briefings.

---

# 25. Attention States

```text
NOW

TODAY

SOON

WAITING ON

FYI

SUPPRESSED

RESOLVED
```

---

# 26. "Now" Screen

The iPhone home view should prioritize:

```text
NOW

1. Call pharmacy before 5 PM

2. Reply to Alice about tomorrow

3. Approve HelloDJ deployment
```

No scrolling through 100 communications should be necessary.

---

# 27. Watch Experience

The Watch should answer:

```text
WHAT NEEDS ME?
```

Example:

```text
NERVE

2 things need you

🔴 Pharmacy
Call before 5 PM

🟠 Alice
Waiting 19h

[Next]
```

Actions:

```text
Done

Snooze

Reply

Call

Open on Phone
```

---

# 28. Escalation

Attention items may escalate.

Example:

```text
Email arrives
     ↓
classified important
     ↓
appears in Today
     ↓
no action
     ↓
deadline approaches
     ↓
promoted to NOW
     ↓
Watch notification
```

Escalation should be based on consequence and timing rather than repeated nagging.

---

# 29. Adaptive Escalation

The system should learn practical behavior.

Example:

If the user consistently misses:

```text
email-only reminders
```

but responds to:

```text
Watch prompts
```

then important deadlines may surface through the Watch.

This preference remains local and user-controlled.

---

# 30. Briefings

Generate:

```text
Morning Brief

Midday optional check

Evening Wrap-Up
```

Morning example:

```text
Sunday

3 things need action today.

1. Call pharmacy before 5.
2. Reply to Alice.
3. Review Zoo's NerveCenter milestone.

You're waiting on:
• Sam — deployment credentials
• Insurance — claim response

Today:
• Dinner 6:30 PM

Overnight:
• 41 emails
• 12 messages
• 1 voicemail

Nothing else requires attention.
```

---

# 31. "Since I Last Looked"

NerveCenter should answer:

```text
"What did I miss?"

"What happened while I slept?"

"Anything important?"

"What do I need to do today?"

"Who am I ignoring?"

"What did I promise people?"

"What am I waiting for?"
```

---

# 32. Cross-Channel Conversation Understanding

The system should recognize:

```text
Email:
"Can we talk about this?"

then

Message:
"Just sent you the details."

then

Voicemail:
"Call me when you've read it."
```

as one evolving interaction rather than three unrelated inbox items.

---

# 33. Personal Goals

Personal tasks may become normal NerveCenter goals.

Example:

```text
Goal:
Resolve insurance issue

Sources:
email thread
phone call
voicemail
documents
calendar

Tasks:
call insurer
submit document
wait for response
follow up Friday
```

The same Goal engine used for engineering work should support these.

---

# 34. Project Association

Communications may link to projects.

Example:

```text
Email from licensing company
    ↓
recognized as HelloDJ-related
    ↓
associated with Goal:
HelloDJ Licensing
```

Relevant project agents may access the communication only when policy permits.

---

# 35. Personal/Engineering Context Firewall

Personal communications must NOT automatically become context for coding agents.

Default:

```text
Personal data
     │
     X
     │
Engineering Agent
```

Explicit relevant relationships may permit scoped access.

Example:

```text
licensing email
    ↓
HelloDJ legal/licensing goal
    ↓
allowed context
```

An unrelated personal conversation never enters a Zoo coding context.

---

# 36. Sensitivity Labels

Communications receive labels such as:

```text
PERSONAL

PRIVATE

FINANCIAL

WORK

PROJECT

LOW-SENSITIVITY
```

Raw communication defaults to:

```text
LOCAL_ONLY
```

---

# 37. OmniRoute Privacy Policy

Inference requests must carry data-policy metadata.

Example:

```json
{
  "privacy": "LOCAL_ONLY",

  "contains_personal_communications": true,

  "remote_provider_allowed": false
}
```

OmniRoute must respect this.

For sensitive personal communications:

```text
local inference is the default
```

Remote inference requires an explicit policy allowing it.

---

# 38. Personal Model Workloads

Good local model tasks include:

```text
classification

summarization

request extraction

deadline extraction

relationship resolution

drafting

thread summarization

importance ranking

commitment extraction
```

Most of these should not require the largest reasoning model.

---

# 39. Model Tiering

Example:

```text
Small fast local model
    ↓
classification / extraction

Medium local model
    ↓
summaries / ranking / drafting

Large reasoning model
    ↓
ambiguous or complicated situations
```

NerveCenter should avoid wasting the 5090 or M5 Max on trivial classifications.

---

# 40. Response Assistant

For actionable communications:

```text
incoming message
      ↓
understand request
      ↓
retrieve relevant context
      ↓
draft response
      ↓
user review
      ↓
send
```

Example:

```text
Alice:
"Are we still on for tomorrow?"

NerveCenter:

Your calendar is free after 6.

Suggested:

"Yep! I'm free after 6. Want to do 6:30?"

[Send]
[Edit]
[Later]
```

---

# 41. No Unauthorized Impersonation

Default external communications policy:

```text
DRAFT ONLY
```

NerveCenter does not silently communicate as the user.

Per-category automatic responses may be added later only through explicit configuration.

---

# 42. Calendar Integration

Connect:

```text
Apple Calendar where accessible

Google Calendar

Microsoft Calendar

CalDAV
```

Calendar provides context for:

```text
availability

appointments

deadlines

travel time

meeting preparation

follow-up timing
```

---

# 43. Calendar Conflict Reasoning

Example:

```text
Alice asks:
"Dinner tomorrow?"

NerveCenter sees:

18:00 appointment
ends 19:00

Suggested response:

"I can do after 7:30."
```

---

# 44. Reminders and Personal Tasks

AttentionItems may become persistent tasks.

Example:

```text
[Make Task]

Call pharmacy
Due: Today 4:30 PM
```

Completing the task resolves associated attention items.

---

# 45. Contact Priority

Users may designate:

```text
VIP

NORMAL

LOW

MUTE
```

NerveCenter may also recommend:

```text
"You almost always respond quickly to Alice.
Make Alice a VIP?"
```

It must not silently assign permanent social significance.

---

# 46. Personal Relay

Create a new daemon:

```text
nerve-personal-relay
```

Primary deployment:

```text
M5 Max
```

Responsibilities:

```text
Messages ingestion

local contact resolution

supported Mail integration where useful

local OS communication events

secure forwarding to NerveCenter

outbound user-approved actions
```

---

# 47. Personal Relay Security

The relay must:

```text
run under the user's account

use least privilege

require explicit OS permissions

bind locally where possible

authenticate to NerveCenter

encrypt transport

never expose Messages storage remotely

never accept arbitrary remote shell commands
```

---

# 48. Offline Behavior

If NerveCenter is unavailable:

```text
relay queues normalized events
```

Once connectivity returns:

```text
events replay
```

Ordering and original timestamps must be preserved.

---

# 49. Raw Content Retention

Retention should be configurable per source.

Example:

```text
raw message:
retain

embedding:
retain

audio voicemail:
delete after transcription

email attachments:
metadata only unless needed
```

Users should be able to choose more aggressive privacy settings.

---

# 50. Search

Examples:

```text
"What did Alice tell me about Friday?"

"Did I ever respond to that insurance email?"

"Who asked me for something this week?"

"What did I promise people?"

"Find the voicemail about the prescription."

"What communications relate to HelloDJ licensing?"
```

---

# 51. Memory Extraction

Not every message becomes permanent knowledge.

Extract durable information selectively.

Examples:

```text
appointment

commitment

decision

project requirement

deadline

relationship between entities
```

Routine conversation should not pollute the knowledge graph.

---

# 52. Daily Operational State

Maintain:

```text
Open commitments

Incoming requests

Waiting-ons

Upcoming deadlines

Pending approvals

Today's calendar

Active incidents

Blocked goals
```

This produces the user's current operational picture.

---

# 53. Unified Attention Across Personal + Engineering

The Attention Engine considers both worlds.

Example:

```text
🔴 Prescription callback
   closes in 45m

🟠 Production incident
   investigation complete

🟠 Reply to Alice
   plans are tomorrow

🟡 Zoo milestone complete
   review when convenient
```

One priority queue.

Not six applications competing for attention.

---

# 54. Priority Override

Real-world consequences outweigh arbitrary system severity.

Example:

```text
personal medical-office callback closes in 20 minutes
```

may outrank:

```text
non-production Kubernetes warning
```

The ranking model should represent the user's actual need for attention.

---

# 55. Interaction Actions

Every AttentionItem may expose appropriate actions:

```text
Done

Reply

Call

Approve

Reject

Snooze

Tomorrow

Make Task

Add Calendar

Show Context

Why Important?

Not Important
```

---

# 56. Snoozing

Snooze must be semantic where possible.

Examples:

```text
After work

Tomorrow morning

When Alice replies

30 minutes before deadline

When I get home

After current incident resolves
```

Conditional snoozes may use NerveCenter events.

---

# 57. Follow-Up Engine

Example:

```text
User sends:
"Please send me the document."

No reply.

48 hours later:

"You asked Sam for the document two days ago.
No response yet.

[Follow up]
[Wait]
[Forget]"
```

---

# 58. Attention Budget

NerveCenter should maintain an approximate interruption budget.

It should prefer:

```text
one bundled briefing
```

over:

```text
nine independent low-priority notifications
```

Urgent items bypass batching.

---

# 59. Quiet Periods

Support:

```text
sleep

meetings

focus sessions

driving

manual Do Not Disturb state
```

Only appropriately urgent AttentionItems should interrupt.

---

# 60. Watch Escalation

The Apple Watch is the final escalation surface.

Use it when:

```text
the item is actionable

timing matters

the user has not already handled it

the consequence justifies interruption
```

Do not use Watch alerts for routine summaries.

---

# 61. Example End-to-End Scenario

```text
09:14

Email arrives:

"Please submit the signed document by Wednesday."


09:14:01

Email connector creates event.


09:14:02

local classifier:

REQUEST detected
DEADLINE detected


09:14:03

NerveCenter creates:

Task:
Submit signed document

Deadline:
Wednesday


09:14:04

Attention Engine:

Not urgent yet.

Classification:
SOON


Tuesday evening

Task remains incomplete.

Attention promoted:

TODAY


Wednesday 09:00

iPhone briefing:

"Document due today."


Wednesday 13:00

Still incomplete.

Watch:

"Document due today.
Still outstanding."

[Done]
[Snooze 1h]
[Open]


User submits document.


NerveCenter observes confirmation email.

Task automatically reconciles:

COMPLETE
```

---

# 62. Example Cross-Channel Scenario

```text
10:00
Alice emails details.

10:12
Alice texts:
"Sent you the thing."

13:40
Alice leaves voicemail:
"Call me when you see it."

NerveCenter resolves all three to:

Person:
Alice

Topic:
same active conversation

Attention:

CALL ALICE

Reason:
direct callback request

Context available:
email + text + voicemail summary
```

---

# 63. New API Groups

Add:

```text
/api/personal/people

/api/personal/communications

/api/personal/conversations

/api/personal/commitments

/api/personal/requests

/api/personal/deadlines

/api/personal/followups

/api/personal/attention

/api/personal/briefings

/api/personal/drafts
```

---

# 64. New MCP Tools

Add:

```text
get_attention

get_daily_brief

get_person

get_conversation

search_communications

get_commitments

get_waiting_on

create_followup

snooze_attention

resolve_attention

draft_reply
```

Sending communications should use separately permissioned tools.

---

# 65. New CLI

Examples:

```bash
nerve attention

nerve today

nerve commitments

nerve waiting

nerve brief

nerve people alice

nerve communication search "insurance"

nerve attention snooze <id> tomorrow
```

---

# 66. iPhone Additions

Add primary Personal views:

```text
Today

Inbox

People

Waiting

Briefing
```

Recommended top-level experience:

```text
Today
Engineering
Ask
```

rather than exposing every subsystem as a separate app-like silo.

---

# 67. Watch Additions

Complications may show:

```text
3 NEED YOU
```

or:

```text
✓ CLEAR
```

This is preferable to raw unread counts.

---

# 68. Home Screen Widget

Example:

```text
NERVE

3 need you

🔴 Pharmacy
🟠 Alice
🟠 Deployment

Next:
Dinner 6:30
```

---

# 69. Morning Brief Widget

Example:

```text
TODAY

3 actions
2 waiting
4 calendar items

Next deadline:
4:30 PM
```

---

# 70. Privacy Requirement

Personal Operations must be local-first.

Default:

```text
messages
voicemail
personal email content
contacts
```

remain on user-controlled systems and local inference unless an explicit policy states otherwise.

---

# 71. Auditability

For every surfaced personal item, retain:

```text
source

reason selected

model used

classification

priority calculation

actions performed
```

The user must be able to ask:

> Why did you bother me about this?

or:

> Why didn't you show me this sooner?

---

# 72. Failure Principle

False negatives are more costly for high-impact communications.

Examples:

```text
deadline

appointment change

financial notice

urgent callback

explicit request
```

should favor recall.

Marketing/newsletters/social noise should favor precision.

---

# 73. Initial Parallel Workstreams

Add to Zoo:

```text
PERSONAL-A
Communication schemas

PERSONAL-B
Email connectors

PERSONAL-C
macOS Personal Relay

PERSONAL-D
Message ingestion

PERSONAL-E
Voicemail import/transcription

PERSONAL-F
Contact/entity resolution

PERSONAL-G
Commitment/request extraction

PERSONAL-H
Attention Engine

PERSONAL-I
Follow-Up Engine

PERSONAL-J
Briefing Engine

PERSONAL-K
Response drafting

PERSONAL-L
iPhone Today UI

PERSONAL-M
Watch Attention UI

PERSONAL-N
privacy/policy enforcement

PERSONAL-O
evaluation dataset
```

These should reuse existing NerveCenter:

```text
events

entities

evidence

goals

tasks

OmniRoute

scheduler

notifications
```

rather than building parallel infrastructure.

---

# 74. Build Dependency DAG

```text
             Communication Schemas
                     │
       ┌─────────────┼──────────────┐
       ▼             ▼              ▼
     Email        Messages       Voicemail
       │             │              │
       └─────────────┼──────────────┘
                     ▼
              Person Resolution
                     │
                     ▼
             Content Extraction
              ┌──────┼───────┐
              ▼      ▼       ▼
           Requests Deadline Commitments
              └──────┼───────┘
                     ▼
               Attention Engine
              ┌──────┼────────┐
              ▼      ▼        ▼
           Briefing Followup Response
              │      │        │
              └──────┼────────┘
                     ▼
                 API / MCP
                ┌────┴────┐
                ▼         ▼
              iPhone     Watch
```

---

# 75. Phase P0 — Email + Attention

Implement first:

```text
email ingestion

Person resolution

request extraction

deadline extraction

commitment extraction

AttentionItem

Today screen

daily briefing
```

This immediately produces useful value.

---

# 76. Phase P1 — Messages

Implement:

```text
macOS Personal Relay

message ingestion

thread reconstruction

cross-channel Person resolution

reply drafting
```

Acceptance:

A new Mac Messages conversation appears inside NerveCenter and can produce an AttentionItem.

---

# 77. Phase P2 — Voicemail

Implement:

```text
Share Sheet import

audio storage

local transcription

Person resolution

callback-request detection

AttentionItem generation
```

Add carrier-specific automatic adapters when available.

---

# 78. Phase P3 — Follow-Up Intelligence

Implement:

```text
commitment tracking

waiting-on tracking

missed reply detection

deadline escalation

semantic snoozing
```

---

# 79. Phase P4 — Full Mobile Attention Surface

Implement:

```text
Today screen

Morning Brief

Watch escalation

widgets

reply drafts

call actions

task completion

snoozing

priority feedback
```

---

# 80. Evaluation Dataset

Build synthetic communication scenarios.

Examples:

```text
spam newsletter

meeting confirmation

urgent callback

friend asking casual question

friend asking time-sensitive question

invoice due

appointment moved

insurance request

project licensing response

message requiring no reply

user makes promise

outgoing unanswered request
```

Expected results must define:

```text
importance

urgency

required action

deadline

whether interruption is justified
```

---

# 81. Attention Metrics

Track:

```text
important items missed

unnecessary interruptions

items immediately dismissed

items acted upon

snooze frequency

time-to-action

deadline misses

commitments forgotten

follow-ups recovered
```

The primary success metric is NOT:

```text
notification engagement
```

It is:

```text
important things successfully handled
```

---

# 82. Anti-Goal

NerveCenter must never optimize for keeping the user inside NerveCenter.

Successful operation may look like:

```text
NerveCenter surfaces three things.

User handles them.

NerveCenter says:

"You're clear."

User leaves.
```

That is success.

---

# 83. Personal Operations MVP Definition

This addendum is MVP-complete when NerveCenter can:

```text
ingest email

ingest Messages through the Mac relay

accept voicemail audio/transcripts

resolve contacts across channels

detect direct requests

detect deadlines

detect user commitments

track waiting-ons

create ranked AttentionItems

generate a daily briefing

surface the most important items on iPhone

escalate appropriate items to Watch

draft responses

snooze intelligently

link personal communications to Goals

keep sensitive communications local by default

explain why every interruption occurred
```

---

# 84. Canonical Personal Demo

The canonical demonstration:

```text
1. Email arrives with a deadline.

2. Friend sends a message requiring a response.

3. Voicemail contains an important callback request.

4. Fifty low-value emails/messages also arrive.

5. User opens NerveCenter.

6. NerveCenter does NOT display 53 unread things.

It displays:

THREE THINGS NEED YOU.

7. Each item explains why.

8. One can be replied to.

9. One can be called.

10. One becomes a task.

11. Remaining communications are summarized.

12. Once all three are handled:

NerveCenter displays:

YOU'RE CLEAR.
```

That demonstration defines Personal Operations.

---

# 85. Zoo Addendum Instruction

Append the following instruction to the existing Zoo implementation context:

```text
NerveCenter now includes a Personal Operations and Attention Engine.

Do not build this as another inbox.

The objective is to convert communications and personal operational state
into a small explainable set of items requiring the user's attention.

Reuse the existing event, entity, evidence, task, goal, policy, OmniRoute,
notification and mobile infrastructure.

Personal communication content is sensitive.

Default personal inference routes to LOCAL_ONLY through OmniRoute unless
explicit policy allows otherwise.

Implement provider-supported integrations wherever available.

For Apple Messages, treat the macOS Personal Relay as the broad local
ingestion mechanism. Do not incorrectly assume iOS exposes unrestricted
iMessage/SMS history to applications.

For voicemail, implement adapter interfaces and Share Sheet/audio
ingestion rather than assuming an unrestricted iOS voicemail API.

Freeze communication, person, commitment, request, deadline and
AttentionItem schemas before parallel implementation.

After schemas are frozen, execute independent email, Messages, voicemail,
Attention Engine, iPhone and Watch workstreams concurrently.

Optimize the system for important things successfully handled, not
notification volume or application engagement.

The canonical UX is:

"Three things need you."

followed eventually by:

"You're clear."
```