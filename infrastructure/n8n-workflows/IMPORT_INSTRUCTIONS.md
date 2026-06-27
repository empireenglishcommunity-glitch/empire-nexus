# n8n Workflow Import Instructions

## Files Ready for Import

| File | Purpose |
|------|---------|
| `empire-routes-complete.json` | 4 bot routes: resource, how, call, community |

## How to Import

1. Open `https://bot.empireenglish.online`
2. Click **"+ Add workflow"** (top left)
3. Click the **"..."** menu → **"Import from file"**
4. Select the `.json` file
5. The workflow will appear with all nodes connected

## After Import — Required Changes

You MUST update these placeholder values before activating:

### 1. Google Sheets credential
- Click any green Google Sheets node
- Select your existing Google Sheets credential (the same one used in the quiz workflow)
- Update `REPLACE_WITH_YOUR_SHEET_ID` with your actual CRM spreadsheet ID
  - Find it in the Google Sheet URL: `https://docs.google.com/spreadsheets/d/THIS_PART_IS_THE_ID/edit`

### 2. Telegram credential
- The HTTP Request nodes use the bot token via URL
- If you prefer, replace the HTTP Request nodes with the native Telegram node
- Or ensure the credential reference `telegramApi` matches your saved credential name

### 3. Community invite links (in "Build Community Message" code node)
- Replace `https://discord.gg/YOUR_INVITE_HERE` with your real Discord invite
- Replace `https://t.me/YOUR_GROUP_HERE` with your real Telegram group link

### 4. Resource link (in "Build Resource Message" code node)
- Replace `https://empireenglish.online/3sounds` with the real PDF/file URL once uploaded

### 5. Cal.com URL (in "Build Call Message" code node)
- Currently set to `https://cal.com/macalempire/empire-english`
- Update if your Cal.com username or event slug is different

## Integration with Existing Workflow

**Option A (Recommended): Merge into existing "Empire Bot — Main"**

Since your existing workflow already has the Telegram Trigger + Code Router + Switch, you only need the **route branches** from this file:

1. Import the workflow as a reference
2. In your existing "Empire Bot — Main" workflow:
   - Connect the Switch output `Resource` → copy the "Build Resource Message" Code Node content
   - Connect the Switch output `How` → copy the "Build How Message" Code Node content
   - Same for `Call` and `Community`
3. Add HTTP Request nodes after each Code Node (same config as shown)
4. Add Google Sheets "Append Row" nodes for resource/how/community (not call — that's logged by Cal.com webhook)

**Option B: Run as separate workflow**

Keep this as a standalone workflow with its own Telegram Trigger. Both workflows can receive the same webhook — n8n handles this. The existing workflow handles quiz/menu/start; this one handles resource/how/call/community.

To do this:
- Set the Telegram webhook to point to THIS workflow's webhook URL
- OR use the "Webhook" trigger instead and route from a single Telegram webhook to both workflows

**Option A is cleaner** — one workflow handles everything.

## Quick Copy-Paste Method (Fastest)

If you don't want to import:

1. Open your existing "Empire Bot — Main"
2. From the Switch node's `Resource` output, add a new **Code** node
3. Paste the JavaScript from "Build Resource Message" (from the JSON file or from `N8N_ROUTES_COMPLETE.md`)
4. Connect a **Telegram** node (Send Message) after it
5. Connect a **Google Sheets** node (Append Row to Events) after that
6. Repeat for How, Call, Community

This takes ~30 minutes using copy-paste from the Code Node contents in the JSON file.
