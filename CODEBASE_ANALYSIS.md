# TeleMind Bot - Comprehensive Codebase Analysis Report

**Report Date:** May 1, 2026
**Project:** Telegram AI Bot (telemind_bot)
**Analysis Scope:** Full codebase exploration including imports, handlers, databases, services, and architecture

---

## 1. GROQ/PROVIDER REFERENCES ANALYSIS

### Summary
- **Groq References:** NONE FOUND
- **Groq Provider:** NOT PRESENT
- **AI Providers Configured:** Gemini only (hardcoded)
- **Multi-Provider Support:** NOT IMPLEMENTED

### Details
- No imports of `groq` or `Groq` libraries
- No `GroqProvider` class or references
- No configuration for Groq API keys
- No mention in requirements.txt
- AI is exclusively tied to Google Gemini API via `gemini_service.py`

### Provider References (Non-Groq)
Location: [app/database/models.py](app/database/models.py#L39)
- `User.preferred_ai_provider`: String field defaulting to `"gemini"` 
- Database migration in [app/database/session.py](app/database/session.py#L32-L41) sets all providers to "gemini"
- Payment model includes generic `provider` field for payment providers (Telegram Stars)
- Autoreply logging has `provider` field tracking AI response source

---

## 2. ALL HANDLER FILES & THEIR PURPOSES

### Handler Files Summary (9 files)

| Handler File | Purpose | Key Routes | Status |
|---|---|---|---|
| **start.py** | Initial bot greeting | `/start` command | ✅ Active |
| **ai_chat.py** | Main AI conversation | Callback: `main:ai_chat` | ✅ Active |
| **prompt.py** | Custom prompt management | `main:prompt`, `prompt:view`, `prompt:set`, `prompt:clear` | ✅ Active |
| **account.py** | **EMPTY** (router only) | None | ⚠️ Stub |
| **profile.py** | User profile & settings | `main:profile`, `account:link` | ✅ Active |
| **autoreply.py** | **EMPTY** (router only) | None | ⚠️ Stub |
| **premium.py** | Premium tier purchase | `main:premium`, `premium:buy_pro`, `premium:buy_business` | ✅ Active |
| **payments.py** | Invoice pre-checkout & confirmation | Pre-checkout, successful_payment | ✅ Active |
| **admin.py** | Admin panel & statistics | `admin:panel`, `admin:users`, `admin:stats`, `admin:payments` | ✅ Active |
| **common.py** | Fallback, error handling | `back:main`, `main:help`, error routes | ✅ Active |

### Detailed Handler Breakdown

#### [start.py](app/handlers/start.py)
- **Handler:** `cmd_start()` - CommandStart filter
- **Output:** Main menu with 6-8 buttons (admin gets extra admin panel)
- **Dependencies:** main_menu keyboard, User model

#### [ai_chat.py](app/handlers/ai_chat.py)  
- **Handlers:**
  1. `ai_chat_menu()` - Enter chat state
  2. `handle_ai_chat()` - Process user message
- **Logic Flow:**
  - Check daily limit before response
  - Load conversation history (last 8 messages)
  - Call Gemini API with `generate_text()`
  - Store message in conversation logs
  - Log usage for statistics
- **Dependencies:** GeminiServiceError, ConversationRepository, UsageRepository

#### [prompt.py](app/handlers/prompt.py)
- **Handlers:** 5 total
  1. `prompt_menu()` - Show prompt options
  2. `prompt_view()` - Display current custom prompt
  3. `prompt_set()` - Enter prompt edit state
  4. `save_prompt()` - Save custom prompt to DB
  5. `prompt_reset()` - Clear custom prompt
  6. `prompt_info()` - Show help about prompts
- **State:** PromptStates.waiting_for_prompt

#### [profile.py](app/handlers/profile.py)
- **Handlers:** 
  1. `profile_menu()` - Display user profile with stats
  2. `account_link_warning()` - Warning before account link
  3. `ask_phone()` - Request phone for account link
  4. `receive_phone()` - Start Telegram auth flow
- **Auth Flow:** phone → code → 2FA (if needed)
- **Dependencies:** TelegramAuthError, SessionSecurityError, auth_service

#### [premium.py](app/handlers/premium.py)
- **Handlers:**
  1. `premium_menu()` - Display plans
  2. `premium_buy()` - Create invoice and send to user
  3. `premium_compare()` - Show plan comparison
- **Payment:** Telegram Stars (XTR currency)
- **Plans:** Pro (100⭐/30d), Business (250⭐/30d)

#### [payments.py](app/handlers/payments.py)
- **Handlers:**
  1. `pre_checkout()` - Validate payment before charge
  2. `successful_payment()` - Process completed payment
- **Logic:** Activate premium tier, update daily limits

#### [admin.py](app/handlers/admin.py)
- **Handlers:**
  1. `admin_panel()` - Admin menu
  2. `admin_users()` - User statistics
  3. `admin_stats()` - Comprehensive statistics dashboard
  4. `admin_payments()` - Recent payments list
- **Protected:** `ensure_admin()` checks role AND admin_ids config
- **Stats Tracked:** Total users, active users, linked accounts, premium count, AI requests, payment success

#### [common.py](app/handlers/common.py)
- **Handlers:**
  1. `back_to_main()` - Return to main menu
  2. `help_menu()` - Show help text
  3. `errors_handler()` - Global error handler (filters message_not_modified)
  4. `fallback_message()` - Catch unhandled messages
- **Special:** Suppresses aiogram's common "message is not modified" error

---

## 3. ALL KEYBOARD/MENU FILES

### Keyboard Files (8 files)

| File | Buttons | Purpose |
|---|---|---|
| **main_menu.py** | 8 (6 user + admin option) | Primary navigation |
| **account.py** | Link warning, code pad | Account connection |
| **admin.py** | 6 panels | Admin controls |
| **autoreply.py** | ? | Autoreply settings (not checked) |
| **premium.py** | ? | Premium plan selection (not checked) |
| **profile.py** | ? | Profile options (not checked) |
| **prompt.py** | ? | Prompt actions (not checked) |

### Main Menu Structure
```
1. 🤖 AI bilan suhbat (main:ai_chat)
2. 🧠 Mening promptim (main:prompt)
3. 👤 Profilim (main:profile)
4. 🔗 Account ulash (account:link)
5. 💬 AI yordamchi (autoreply:menu)
6. 💎 Premium (main:premium)
7. ❓ Yordam (main:help)
8. 🛠 Admin paneli (admin:panel) [Admin only]
```

### Account Keyboard (account.py)
- **Code Entry:** 10 digit buttons (0-9) + backspace + confirm
- **Warning Confirmations:** Yes/No buttons

---

## 4. DATABASE MODELS (12 total)

### Core Models

#### User
- PK: `id` (Integer)
- UK: `telegram_id` (BigInteger)
- Profile: `username`, `first_name`, `last_name`, `language_code`
- Access Control: `role` (admin/user), `is_banned`
- Plan: `plan` (free/pro/business), `premium_until`
- AI Usage: `daily_limit`, `used_today`, `limit_reset_date`
- Account Link: `is_account_linked`, `selected_persona`
- Preferences: `preferred_ai_provider` (default: "gemini"), `custom_prompt`
- Timestamps: `created_at`, `updated_at`, `last_active_at`
- Relationships: conversations (1-to-many)

#### Conversation
- PK: `id`
- FK: `user_id` → User
- Fields: `title`, `created_at`
- Relationships: messages (1-to-many)

#### MessageLog
- PK: `id`
- FK: `user_id` → User, `conversation_id` → Conversation (optional)
- Fields: `role` (user/assistant/system), `content`, `tokens_used`, `created_at`

#### Payment
- PK: `id`
- FK: `user_id` → User
- Fields: `plan`, `amount` (deprecated), `amount_stars`, `currency` (default: XTR)
- Status: `status` (pending/paid), `provider` (default: telegram_stars)
- Charge IDs: `telegram_payment_charge_id`, `provider_payment_charge_id`
- Tracking: `invoice_payload`, `created_at`, `paid_at`

#### UsageLog
- PK: `id`
- FK: `user_id` → User
- Fields: `action` (ai_chat, etc), `created_at`

#### AdminAction
- PK: `id`
- Fields: `admin_id`, `action`, `target_user_id`, `details`, `created_at`

#### TelegramSession
- PK: `id`
- UK: `user_id` (one session per user)
- Fields: `phone`, `encrypted_session`, `is_active`, `created_at`, `updated_at`

#### AIAutoreplySettings
- PK: `id`
- UK: `user_id`
- Enable/Mode: `enabled`, `mode` (off/assistant_only/full)
- Persona: `persona`, `custom_prompt`
- Away Mode: `reply_only_when_away`, `away_after_minutes`
- Timing: `delay_seconds`, `daily_reply_limit`, `used_today`, `reset_date`
- Notifications: `notify_owner_on_reply`
- Timestamps: `created_at`, `updated_at`

#### AutoreplyChatState
- PK: `id`
- FK: `user_id`, Indexed: `peer_id`
- Fields: `peer_name`, `intro_sent`, `last_incoming_at`, `last_reply_at`, `last_owner_outgoing_at`
- Cooldown: `cooldown_until`, `message_count`
- Timestamps: `created_at`, `updated_at`

#### AutoreplyLog
- PK: `id`
- FK: `user_id`
- Fields: `incoming_chat_id`, `incoming_user_id`, `peer_id`, `peer_name`
- Content: `incoming_text`, `ai_reply`, `status`, `skipped_reason`, `error_text`
- Tracking: `provider`, `persona_key`, `created_at`

#### AllowedChat
- PK: `id`
- FK: `user_id`
- Fields: `chat_id`, `title`, `is_allowed`

#### BlockedChat
- PK: `id`
- FK: `user_id`
- Fields: `chat_id`, `title`, `reason`

---

## 5. SERVICE LAYER STRUCTURE

### Directory Layout
```
app/services/
├── ai/
│   ├── __init__.py (exports 3 functions)
│   └── gemini_service.py (AI backend)
├── telegram_account/
│   ├── __init__.py
│   ├── auth_service.py (Telethon login)
│   ├── autoreply_service.py (AI auto-responder)
│   ├── client_manager.py (Client lifecycle)
│   └── session_service.py (Encryption/decryption)
├── __init__.py
├── payment_service.py (Stripe/Stars API)
├── prompt_service.py (Prompt building)
└── usage_service.py (Rate limiting & quotas)
```

### Key Services

#### AI Service (gemini_service.py)
**Exports:** `generate_text()`, `generate_autoreply()`, `generate_tool_response()`, `GeminiServiceError`

**Main Function:** `_call_gemini(messages, timeout=12)`
- HTTP POST to Google Gemini API
- Retry logic (2 attempts, 0.4s wait)
- Timeout: 12 seconds (tunable)
- Safety block detection
- JSON response parsing with error handling

**Helper:** `extract_gemini_text(data)` 
- Validates response structure
- Checks for safety blocks
- Extracts text from response candidates

#### Payment Service (payment_service.py)
- `StarsPlan`: dataclass (key, title, stars, days)
- Plans: Pro (100⭐), Business (250⭐)
- `build_payload()`: Creates invoice payload
- `create_pending_payment()`: Creates Payment record
- `activate_payment()`: Marks as paid, updates user plan & limits

#### Prompt Service (prompt_service.py)
**System Prompts:**
1. `UZBEK_QUALITY_PROMPT` - Language quality enforcement
2. `NORMAL_SYSTEM_PROMPT` - General chat assistant
3. `AUTORESPONDER_PROMPT` - Private message responder
4. `TOOL_PROMPTS` - write, translate, summarize, rewrite, ideas, hashtags, ad_copy

**Functions:**
- `build_normal_messages()` - Regular chat context
- `build_tool_messages()` - Tool-specific context
- `build_autoreply_messages()` - Autoreply context

#### Usage Service (usage_service.py)
**Plan Limits:** Free=30, Pro=150, Business=300 (daily)

**Functions:**
- `can_use_ai(user)` - Check remaining credits
- `consume_ai_credit(user)` - Decrement usage
- `reset_daily_usage_if_needed(user)` - Reset on new day
- `get_remaining_credits(user)` - Calculate balance
- `update_user_plan(session, user_id, plan)` - Change tier
- `limit_text(user)` - Format "used/limit" string

#### Telegram Auth Service (auth_service.py)
**Dependencies:** Telethon library for TG client auth

**Flow:**
1. `start_login(user_id, phone)` - Request code
2. `confirm_code(db_session, user_id, code)` - Enter code
3. `confirm_2fa_password(db_session, user_id, password)` - 2FA if needed
4. `save_encrypted_session()` - Store encrypted session

**Errors Handled:**
- PhoneNumberInvalidError
- PhoneCodeInvalidError, PhoneCodeExpiredError
- SessionPasswordNeededError (2FA)
- FloodWaitError (Telegram rate limit)

#### Autoreply Service (autoreply_service.py)
**Architecture:** Queue-based async processing per (user_id, peer_id) pair

**Key Components:**
- `IncomingPrivateMessage` dataclass
- `enqueue_incoming_message()` - Queue incoming message
- `_process_peer_queue()` - Worker consumes queue (300s timeout)
- `COMBINE_WINDOW_SECONDS = 1.2` - Batch messages for better context
- `MIN_REPLY_INTERVAL_SECONDS = 5` - Prevent spam replies

**Reply Logic:**
1. Check if enabled & mode
2. Check cooldown period
3. Send intro if first message
4. Call Gemini with context (last messages)
5. Log response (pending → sent)
6. Optionally notify owner

#### Client Manager (client_manager.py)
**Responsibilities:**
- Lifecycle management of TelegramClient instances
- Event handler registration
- Autoreply message routing
- Session persistence

**Functions:**
- `start_enabled_clients(bot)` - Start all active client sessions
- `start_user_client(user_id)` - Start individual client
- `stop_user_client(user_id)` - Stop and cleanup
- `send_manual_reply()` - Send message from user's account
- `_client_supervisor()` - Backoff reconnection loop

**asyncio.create_task Usage:**
- Line 49: `_tasks[user_id] = asyncio.create_task(_client_supervisor(user_id))`
- Line 157: `asyncio.create_task(...)` in message handler

---

## 6. STATE MANAGEMENT SETUP

### State Groups (5 groups)

#### AIChatStates
- `chatting` - User composing message to AI

#### AccountLinkStates
- `waiting_for_phone` - Enter phone number
- `waiting_for_code` - Enter SMS/app code
- `waiting_for_2fa_password` - 2FA password (if enabled)

#### AutoreplyStates
- `waiting_for_prompt` - Edit autoreply persona prompt
- `waiting_for_draft_edit` - Edit pending autoreply response

#### AdminStates
- `waiting_for_broadcast` - Admin sending message to all users
- `waiting_for_ban_user` - Admin banning user

#### PromptStates
- `waiting_for_prompt` - User setting custom AI prompt

### FSM Storage
- **Type:** MemoryStorage (line [app/loader.py](app/loader.py#L14))
- **Not Persistent:** States lost on bot restart
- **Scope:** Per-user FSM context

---

## 7. MIDDLEWARE SETUP

### 2 Middleware Components

#### UserMiddleware (app/middlewares/user_middleware.py)
**Position:** Update-level
**Responsibilities:**
1. Extract telegram user from event
2. Load/create User from database
3. Check if user is banned (block if true)
4. Inject `session` (AsyncSession) into data
5. Inject `db_user` (User model) into data
6. Auto-commit on handler completion

**Order:** Executes first

#### ThrottlingMiddleware (app/middlewares/throttling.py)
**Position:** Update-level  
**Responsibilities:**
1. Rate limit by user_id
2. Rate: 0.8 seconds per message (tunable via `THROTTLE_RATE_SECONDS` config)
3. Responds with "⏳ Please slow down" for both callbacks and messages
4. Silently drops message if throttled

**Order:** Executes second (after UserMiddleware)

### Middleware Chain
```
Aiogram
├─ ThrottlingMiddleware (0.8s rate limit)
└─ UserMiddleware (DB lookup, ban check)
   └─ Router (handlers)
```

---

## 8. MAIN BOT ENTRY POINT & REGISTRATION

### Entry Points

#### [run.py](run.py) - Process Entry
```python
asyncio.run(main())  # Call async main()
```

#### [app/main.py](app/main.py) - Bot Initialization
**Sequence:**
1. Load settings from .env
2. Setup logging
3. Verify BOT_TOKEN configured
4. Initialize database (create tables)
5. Create Bot & Dispatcher instances
6. **Register routers:** `setup_routers()`
7. **Start Telegram clients:** `start_enabled_clients(bot)` (autoreply accounts)
8. Start polling (blocking)

#### [app/loader.py](app/loader.py) - Bot & Dispatcher Factory
```python
Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
Dispatcher(storage=MemoryStorage())
  .middleware(ThrottlingMiddleware)
  .middleware(UserMiddleware)
```

#### [app/handlers/__init__.py](app/handlers/__init__.py) - Router Setup
**setup_routers()** returns merged router with inclusion order:
1. start
2. ai_chat
3. prompt
4. account
5. autoreply
6. profile
7. premium
8. payments
9. admin
10. common (fallback)

---

## 9. IMPORTS ANALYSIS

### Critical Dependencies
```
aiogram>=3.7,<4.0           # Telegram bot framework
SQLAlchemy>=2.0,<3.0        # ORM
aiosqlite>=0.19             # Async SQLite
pydantic>=2.6               # Settings validation
httpx>=0.27                 # HTTP client (Gemini API)
Telethon>=1.36              # Telegram account client (autoreply)
cryptography>=42.0          # Session encryption
```

### Broken Imports: NONE FOUND
- All imports resolve correctly
- No circular dependencies detected
- No dangling references

### Import Patterns
- Forward declaration usage: `from __future__ import annotations`
- Type hints with string literals
- Lazy imports in some services (models imported inside functions)

---

## 10. ASYNCIO.create_task() USAGE IN APP CODE

### Locations (3 uses)

1. **[app/services/telegram_account/client_manager.py:49](app/services/telegram_account/client_manager.py#L49)**
```python
_tasks[user_id] = asyncio.create_task(_client_supervisor(user_id))
```
- **Purpose:** Start background Telegram client supervisor
- **Supervisor:** Infinite loop with exponential backoff reconnection

2. **[app/services/telegram_account/client_manager.py:157](app/services/telegram_account/client_manager.py#L157)**
```python
asyncio.create_task(...)  # Task creation (full context not shown)
```
- **Purpose:** Likely message event handler registration

3. **[app/services/telegram_account/autoreply_service.py:59](app/services/telegram_account/autoreply_service.py#L59)**
```python
_workers[key] = asyncio.create_task(_process_peer_queue(bot, client, key))
```
- **Purpose:** Create message processing worker per (user_id, peer_id) pair
- **Worker:** Consumes queue with 300s timeout, batches messages by 1.2s window

### Task Management
- Tasks stored in module-level dicts
- No explicit cleanup on bot shutdown
- Potential issue: Tasks may orphan on SIGTERM

---

## 11. EXCEPTION HANDLING PATTERNS

### Custom Exceptions
1. **GeminiServiceError** - AI API errors
2. **TelegramAuthError** - Login failures
3. **TelegramTwoFactorRequired** - Extends TelegramAuthError
4. **SessionSecurityError** - Session encryption/decryption

### Error Handling Strategy

#### AI Handler (ai_chat.py)
```python
try:
    answer = await generate_text(...)
except GeminiServiceError as exc:
    await waiting.edit_text(f"⚠️ {exc}")
    return
```
- **Approach:** Show error to user, don't crash

#### Payment Handler (payments.py)
```python
if payment is None or payment.status != "pending":
    await query.answer(ok=False, error_message="...")
    return
```
- **Approach:** Pre-check validation, clear error messages

#### Admin Handler (admin.py)
```python
async def ensure_admin(callback, db_user) -> bool:
    if db_user.role != "admin" or not is_admin(db_user.telegram_id):
        await callback.answer("Bu bo'lim faqat adminlar uchun.", show_alert=True)
        return False
    return True
```
- **Approach:** Permission guard pattern

#### Global Error Handler (common.py)
```python
@router.error()
async def errors_handler(event: ErrorEvent) -> None:
    if is_message_not_modified_error(event.exception):
        return  # Suppress known harmless error
    logger.exception("Unhandled update error", exc_info=event.exception)
```
- **Approach:** Filter known errors, log unhandled ones

---

## 12. CRITICAL BUGS & DESIGN ISSUES

### 🔴 CRITICAL

1. **No Graceful Shutdown for Tasks**
   - Location: [app/services/telegram_account/client_manager.py](app/services/telegram_account/client_manager.py#L49)
   - Issue: `asyncio.create_task()` tasks not awaited on shutdown
   - Risk: Orphaned tasks, incomplete operations
   - Fix: Add explicit `await asyncio.gather(*_tasks.values())` in main.py on exit

2. **Hardcoded Gemini-Only AI Provider**
   - Location: [app/config.py](app/config.py#L10-L11), [app/database/session.py](app/database/session.py#L33)
   - Issue: `preferred_ai_provider` field exists but always set to "gemini"
   - Risk: Dead code, false multi-provider architecture
   - Fix: Either implement provider selection or remove field

3. **Unencrypted Telethon Sessions in DB**
   - Location: [app/services/telegram_account/session_service.py](app/services/telegram_account/session_service.py)
   - Issue: Encryption key in config.SESSION_ENCRYPTION_KEY could be weak
   - Risk: Session compromise → account takeover
   - Fix: Use AES-256, rotate keys, add integrity checks

### 🟠 HIGH

4. **No Conversation Cleanup**
   - Location: [app/database/repositories.py](app/database/repositories.py#L89-L91)
   - Issue: `clear_memory()` exists but never called
   - Risk: Conversation tables grow unbounded
   - Fix: Add automatic pruning (e.g., delete conversations >30 days old)

5. **Race Condition in Autoreply Queue**
   - Location: [app/services/telegram_account/autoreply_service.py](app/services/telegram_account/autoreply_service.py#L59)
   - Issue: Multiple calls to `enqueue_incoming_message()` could create duplicate workers
   - Risk: Duplicate replies to same message
   - Fix: Use lock or atomic dict.setdefault()

6. **Limited Error Recovery in Client Supervisor**
   - Location: [app/services/telegram_account/client_manager.py](app/services/telegram_account/client_manager.py#L89-L110)
   - Issue: Max backoff not specified, infinite backoff possible
   - Risk: Zombie tasks consuming memory indefinitely
   - Fix: Add max_backoff=60 or explicit retry limit

### 🟡 MEDIUM

7. **Message Truncation Without Warning**
   - Location: [app/services/telegram_account/autoreply_service.py](app/services/telegram_account/autoreply_service.py#L111-L115)
   - Issue: Incoming/outgoing text truncated to 4000/1000 chars silently
   - Risk: User doesn't know message was truncated
   - Fix: Split long messages or notify user

8. **No Input Validation in Admin Broadcast**
   - Location: [app/handlers/admin.py](app/handlers/admin.py)
   - Issue: AdminStates.waiting_for_broadcast state exists but handler not shown
   - Risk: Could send unvalidated HTML/markup to all users
   - Fix: HTML escape, length limit, preview before send

9. **Memory Leak in Throttling Middleware**
   - Location: [app/middlewares/throttling.py](app/middlewares/throttling.py#L13)
   - Issue: `_last_seen` dict never purged for inactive users
   - Risk: Dict grows to millions of entries over time
   - Fix: Add TTL or periodic cleanup

### 🟢 LOW

10. **Empty Handler Modules**
    - Locations: [app/handlers/account.py](app/handlers/account.py), [app/handlers/autoreply.py](app/handlers/autoreply.py)
    - Issue: Stub routers included but no handlers
    - Risk: Confusing for maintenance, suggests incomplete migration
    - Fix: Remove empty files or add handlers

11. **No Request ID Logging**
    - Location: All handlers
    - Issue: Can't trace message flow through logs
    - Risk: Hard to debug production issues
    - Fix: Add request IDs to log context

12. **Hardcoded Language Assumptions**
    - Location: [app/services/prompt_service.py](app/services/prompt_service.py)
    - Issue: Prompt assumes Uzbek as primary language
    - Risk: Non-Uzbek users get lower quality responses
    - Fix: Detect user language from config or headers

---

## 13. SUMMARY STATISTICS

| Metric | Count |
|---|---|
| **Total Handler Routers** | 9 |
| **Active Handlers** | 6 |
| **Stub Handlers** | 2 |
| **Database Models** | 12 |
| **Services** | 7 |
| **Middleware** | 2 |
| **State Groups** | 5 |
| **Plans** | 3 (free/pro/business) |
| **AI Providers** | 1 (Gemini hardcoded) |
| **Groq References** | 0 |
| **Custom Exceptions** | 4 |
| **asyncio.create_task() Calls** | 3 |
| **Critical Bugs** | 3 |
| **High Priority Issues** | 3 |
| **Medium Priority Issues** | 3 |

---

## 14. ARCHITECTURE OVERVIEW

```
┌─ run.py (Entry)
│  └─ app/main.py (Setup)
│     ├─ config.py (Settings from .env)
│     ├─ database/session.py (Init DB)
│     ├─ loader.py (Create Bot + Dispatcher)
│     │  ├─ Middleware: ThrottlingMiddleware
│     │  └─ Middleware: UserMiddleware → data["db_user"], data["session"]
│     ├─ handlers/__init__.py (setup_routers)
│     │  ├─ start → handlers/start.py
│     │  ├─ ai_chat → handlers/ai_chat.py → services/ai/gemini_service.py
│     │  ├─ prompt → handlers/prompt.py
│     │  ├─ profile → handlers/profile.py → services/telegram_account/auth_service.py
│     │  ├─ premium → handlers/premium.py → services/payment_service.py
│     │  ├─ payments → handlers/payments.py
│     │  ├─ admin → handlers/admin.py
│     │  └─ common → handlers/common.py (global error handler)
│     └─ services/telegram_account/client_manager.py (start_enabled_clients)
│        ├─ TelegramClient instance per user (autoreply)
│        └─ Message handler → autoreply_service.py (queue + Gemini)
│
├─ Database Layer
│  ├─ database/models.py (12 ORM models)
│  ├─ database/session.py (AsyncSession, migrations)
│  └─ database/repositories.py (Data access layer)
│
└─ Service Layer
   ├─ services/ai/gemini_service.py (Gemini HTTP API)
   ├─ services/payment_service.py (Stars plan definitions)
   ├─ services/usage_service.py (Rate limiting)
   ├─ services/prompt_service.py (Prompt templates)
   └─ services/telegram_account/
      ├─ auth_service.py (Telethon login)
      ├─ autoreply_service.py (Queue + AI responses)
      ├─ client_manager.py (Client lifecycle)
      └─ session_service.py (Encryption)
```

---

## 15. CONFIGURATION REQUIREMENTS

### .env Variables (Required)
```
BOT_TOKEN=              # Telegram Bot API token
GEMINI_API_KEY=         # Google Gemini API key
TELEGRAM_API_ID=        # Telethon API ID
TELEGRAM_API_HASH=      # Telethon API hash
SESSION_ENCRYPTION_KEY= # 32-char key for session encryption
ADMIN_IDS=              # Comma-separated admin Telegram IDs
```

### Optional
```
GEMINI_MODEL=gemini-1.5-flash  # Model selection
DATABASE_URL=...               # SQLAlchemy DB URL
LOG_LEVEL=INFO                 # Logging level
AI_TIMEOUT_SECONDS=45          # Gemini timeout
THROTTLE_RATE_SECONDS=0.8      # Rate limit per user
```

---

## 16. DEPLOYMENT NOTES

1. **Database:** Supports SQLite (default) and any SQLAlchemy-compatible DB
2. **Async Runtime:** Requires Python 3.10+ (uses async/await)
3. **Long-Running:** Uses `dp.start_polling()` (CPU-inefficient, consider webhook)
4. **Multi-Instance:** Middleware FSM state NOT shared; use external storage for horizontal scaling
5. **Secrets Management:** SESSION_ENCRYPTION_KEY critical — use strong random key, rotate periodically

---

## CONCLUSION

**System Status:** Functional with 3 critical issues

The TeleMind bot is a **Gemini-only** AI assistant with premium tier support, Telegram account linking, and autoreply capabilities. No Groq integration exists despite the provider field in the database. The architecture is well-organized but has critical production issues:

1. Task cleanup on shutdown
2. Multi-provider support disconnect (field exists but hardcoded)
3. Session encryption key management

Recommend addressing critical bugs before production deployment.

