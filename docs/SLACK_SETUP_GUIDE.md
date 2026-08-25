# ⚡ Sympose: Complete Slack Socket Mode Setup Guide

> **Zero-Bloat Multi-Agent Slack Hub**: Learn how to configure your Slack workspace to run Samantha, Grace, and Aurelius over secure **Socket Mode** with zero public inbound ports, webhooks, or ngrok tunnels.

---

## 🚀 Quick Setup: 1-Click App Manifest Method (Fastest)

The fastest way to configure your Slack App is using Slack's **App Manifest**.

### Step 1: Create App from Manifest
1. Navigate to **[https://api.slack.com/apps](https://api.slack.com/apps)**.
2. Click **Create New App** $\to$ choose **From an app manifest**.
3. Select your **Workspace** $\to$ click **Next**.
4. Paste the following YAML manifest and click **Next** $\to$ **Create**:

```yaml
display_information:
  name: Samantha
  description: Master Strategic Orchestrator & AI Partner
  background_color: "#1a1a24"
features:
  app_home:
    home_tab_enabled: false
    messages_tab_enabled: true
    messages_tab_read_only_enabled: false
  bot_user:
    display_name: Samantha
    always_online: true
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - im:history
      - im:read
      - im:write
      - channels:history
      - reactions:read
      - reactions:write
settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.im
  socket_mode_enabled: true
```

---

### Step 2: Generate App-Level Token (`SLACK_APP_TOKEN`)
1. In the left sidebar, click **Basic Information** (or **Socket Mode**).
2. Under **App-Level Tokens**, click **Generate Token and Scopes**:
   - **Token Name**: `sympose-socket`
   - **Scopes**: Click **Add Scope** $\to$ add `connections:write`
   - Click **Generate**.
3. Copy the token starting with `xapp-1-...`.  
   👉 **This is your `SLACK_APP_TOKEN`.**

---

### Step 3: Install App to Workspace (`SLACK_BOT_TOKEN`)
1. In the left sidebar, click **OAuth & Permissions** (or **Install App**).
2. Click **Install to Workspace** $\to$ click **Allow**.
3. Copy the **Bot User OAuth Token** starting with `xoxb-...`.  
   👉 **This is your `SLACK_BOT_TOKEN`.**

---

### Step 4: Configure `.env` & Launch
Open your `.env` file in the project root:

```bash
# Samantha (Primary / Default Bot)
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-1-your-app-token-here
```

Launch the daemon:
```bash
./chat.sh --slack
```

---

## 🛠️ Manual UI Setup Guide (Step-by-Step)

If you prefer configuring the app manually through the Slack API portal:

| Step | Page in Slack Portal | Setting / Action | Required Values |
| :--- | :--- | :--- | :--- |
| **1. Create** | [api.slack.com/apps](https://api.slack.com/apps) | **Create New App** $\to$ **Blank app** | App Name: `Samantha` |
| **2. Socket Mode** | **Socket Mode** (sidebar) | Toggle **Enable Socket Mode** to `ON` | Generate token with `connections:write` (`xapp-1-...`) |
| **3. Bot Scopes** | **OAuth & Permissions** | Scroll to **Bot Token Scopes** | `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`, `channels:history`, `reactions:read`, `reactions:write` |
| **4. App Home** | **App Home** (sidebar) | Under **Messages Tab** | Check ☑️ **"Allow users to send Slash commands and messages from the messages tab"** |
| **5. Events** | **Event Subscriptions** | Toggle **Enable Events** to `ON` $\to$ **Subscribe to bot events** | Add `app_mention` and `message.im` $\to$ **Save Changes** |
| **6. Install** | **OAuth & Permissions** | Click **Install to Workspace** | Authorize $\to$ Copy Bot Token (`xoxb-...`) |

---

## 👥 Multi-Agent Setup (Dedicated Apps for Grace & Aurelius)

Sympose can run multiple dedicated Slack bots concurrently from a single `./chat.sh --slack` process.

### Configuration Template in `.env`:
```bash
# 1. Samantha (Master Orchestrator - Gemini 3.5 Flash-Lite)
SLACK_BOT_TOKEN=xoxb-samantha-bot-token...
SLACK_APP_TOKEN=xapp-1-samantha-app-token...

# 2. Grace Hopper (Surgical Engineer - Gemini 3.5 Flash-Lite temp:0.1)
SLACK_GRACE_BOT_TOKEN=xoxb-grace-bot-token...
SLACK_GRACE_APP_TOKEN=xapp-1-grace-app-token...

# 3. Marcus Aurelius (Stoic Journal - Local Offline Ollama Gemma 2 9B)
SLACK_AURELIUS_BOT_TOKEN=xoxb-aurelius-bot-token...
SLACK_AURELIUS_APP_TOKEN=xapp-1-aurelius-app-token...
```

When you launch `./chat.sh --slack`, Sympose auto-discovers all configured tokens and launches all bots concurrently:
```text
🚀 [Sympose] Launching 3 Slack Agent(s)...
  • @aurelius listening on Socket Mode...
  • @grace listening on Socket Mode...
  • @samantha listening on Socket Mode...
```

> [!IMPORTANT]
> **Checklist for each new agent app:**
> 1. **App Home:** Check ☑️ **"Allow users to send Slash commands and messages from the messages tab"** (unlocks 1-on-1 DMs).
> 2. **Event Subscriptions:** Ensure `app_mention` and `message.im` are added under **Subscribe to bot events**.
> 3. **Reinstall App:** Click **Reinstall to Workspace** after updating scopes or events.
> 4. **Local Models (Aurelius):** Ensure `ollama serve` is running for offline Ollama agents.

---

## 💬 How to Interact in Slack

### 1. In Direct Messages (1-on-1 DMs)
- Open a DM with **Samantha**, **Grace Hopper**, or **Marcus Aurelius**.
- Type naturally just like chatting with a human colleague:
  > *"Hey, can you help me structure the database schema?"*
  > *"Remember that I prefer 15-minute token TTL."*
- **Zero `@` tags or slash commands required!**

### 2. In Channels (`#general`, `#dev`, etc.)
1. First, invite the bot to the channel:
   ```slack
   /invite @Samantha
   /invite @Grace Hopper
   ```
2. Tag the bot with your prompt:
   ```slack
   @Grace Hopper review this git commit
   @Samantha how should we break down this sprint?
   @Aurelius Marcus reflect on handling unexpected delays
   ```

---

## ❓ Troubleshooting & FAQs

### 1. "Sending messages to this app has been turned off"
- **Cause**: The Messages Tab in App Home is disabled.
- **Fix**: Go to `api.slack.com/apps` $\to$ your app $\to$ **App Home** $\to$ check ☑️ **"Allow users to send Slash commands and messages from the messages tab"**.

### 2. Bot does not reply to `@mentions` in a channel
- **Cause 1**: The bot is not invited to the channel.  
  👉 **Fix**: Type `/invite @YourBotName` in that channel.
- **Cause 2**: `app_mention` event was not added or the app was not reinstalled.  
  👉 **Fix**: Go to **Event Subscriptions** $\to$ add `app_mention` $\to$ **Save Changes** $\to$ click **Reinstall to Workspace**.

### 3. "Local Model Offline (ollama/gemma2:9b)"
- **Cause**: Marcus Aurelius runs 100% offline and requires local Ollama.
- **Fix**: Open the Ollama macOS app or run `ollama serve` in a terminal window.
