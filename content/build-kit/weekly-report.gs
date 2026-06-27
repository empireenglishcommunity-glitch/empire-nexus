/**
 * Empire English — Weekly Funnel Auto-Report
 * Google Apps Script (runs on the CRM Google Sheet)
 * 
 * SETUP:
 * 1. Open your Empire CRM Google Sheet
 * 2. Extensions → Apps Script
 * 3. Paste this entire file
 * 4. Set BOT_TOKEN and CHAT_ID below
 * 5. Run weeklyReport() once manually to test
 * 6. Add trigger: Edit → Current project's triggers → Add → 
 *    weeklyReport / Time-driven / Weekly / Monday / 8-9 AM
 * 
 * COST: $0 (Google Apps Script is free, unlimited runs)
 * MAKES: Zero Make.com operations consumed
 */

// ═══════════════════════════════════════════════════════
//  CONFIGURATION — fill these two values
// ═══════════════════════════════════════════════════════
const BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_HERE';  // @BotFather token for the n8n bot
const CHAT_ID = 'YOUR_FOUNDER_CHAT_ID_HERE';        // Your personal Telegram numeric ID

// ═══════════════════════════════════════════════════════
//  MAIN FUNCTION — generates and sends the weekly report
// ═══════════════════════════════════════════════════════
function weeklyReport() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const eventsSheet = ss.getSheetByName('Events');
  const subsSheet = ss.getSheetByName('Subscribers');
  
  if (!eventsSheet || !subsSheet) {
    sendTelegram('⚠️ Weekly report error: Events or Subscribers tab not found.');
    return;
  }
  
  // Date range: last 7 days
  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const weekStart = formatDate(weekAgo);
  const weekEnd = formatDate(now);
  
  // Count events from the last 7 days
  const events = getRecentEvents(eventsSheet, weekAgo);
  
  const joins = events.filter(e => e.type === 'JOINED_BOT').length;
  const quizzes = events.filter(e => e.type === 'QUIZ_COMPLETED').length;
  const resources = events.filter(e => e.type === 'RESOURCE_CLAIMED').length;
  const offers = events.filter(e => e.type === 'OFFER_OPENED').length;
  const booked = events.filter(e => e.type === 'BOOKED').length;
  const community = events.filter(e => e.type === 'COMMUNITY_CLICK').length;
  
  // Calculate conversion rates (avoid division by zero)
  const rateJoinToQuiz = joins > 0 ? Math.round((quizzes / joins) * 100) : 0;
  const rateQuizToOffer = quizzes > 0 ? Math.round((offers / quizzes) * 100) : 0;
  const rateOfferToBook = offers > 0 ? Math.round((booked / offers) * 100) : 0;
  
  // Find bottleneck (lowest conversion rate)
  const rates = [
    { step: 'Join→Quiz', rate: rateJoinToQuiz },
    { step: 'Quiz→Offer', rate: rateQuizToOffer },
    { step: 'Offer→Booked', rate: rateOfferToBook }
  ];
  
  // Only consider rates where the numerator step has data
  const validRates = rates.filter((r, i) => {
    if (i === 0) return joins > 0;
    if (i === 1) return quizzes > 0;
    if (i === 2) return offers > 0;
    return false;
  });
  
  let bottleneck = 'Not enough data yet';
  let suggestion = 'Keep driving traffic to the bot';
  
  if (validRates.length > 0) {
    const lowest = validRates.reduce((a, b) => a.rate < b.rate ? a : b);
    bottleneck = `${lowest.step} (${lowest.rate}%)`;
    suggestion = getSuggestion(lowest.step);
  }
  
  // Get totals from Subscribers
  const subsData = subsSheet.getDataRange().getValues();
  const totalSubs = Math.max(0, subsData.length - 1); // minus header
  const hotCount = subsData.filter(row => {
    const segCol = subsData[0].indexOf('segment');
    return segCol >= 0 && String(row[segCol]).toLowerCase() === 'hot';
  }).length;
  
  // Build the report message
  const report = `🏛 EMPIRE — WEEKLY FUNNEL DIGEST
Week: ${weekStart} → ${weekEnd}

📊 FUNNEL NUMBERS
━━━━━━━━━━━━━━━━━━
Reach:        +${joins} new bot starts
Engagement:   ${quizzes} quizzes · ${resources} resources claimed
Leads:        ${offers} offers viewed
Appointments: ${booked} booked ★
Community:    ${community} community taps
━━━━━━━━━━━━━━━━━━

📈 CONVERSION RATES
Start→Quiz:    ${rateJoinToQuiz}%
Quiz→Offer:    ${rateQuizToOffer}%
Offer→Booked:  ${rateOfferToBook}%

🎯 BOTTLENECK: ${bottleneck}
💡 Suggested focus: ${suggestion}

⚙️ Total subscribers: ${totalSubs}
Hot leads: ${hotCount}
Automation health: OK`;

  sendTelegram(report);
  
  // Also log to KPI_Weekly tab (create if missing)
  logToKPITab(ss, weekStart, joins, quizzes, resources, offers, booked, community,
              rateJoinToQuiz, rateQuizToOffer, rateOfferToBook, bottleneck);
}

// ═══════════════════════════════════════════════════════
//  HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════

function getRecentEvents(sheet, since) {
  const data = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];
  
  const headers = data[0];
  const typeCol = headers.indexOf('event_type');
  const tsCol = headers.indexOf('timestamp');
  
  if (typeCol < 0 || tsCol < 0) return [];
  
  const events = [];
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const ts = new Date(row[tsCol]);
    if (ts >= since) {
      events.push({ type: String(row[typeCol]), timestamp: ts });
    }
  }
  return events;
}

function getSuggestion(step) {
  switch(step) {
    case 'Join→Quiz':
      return 'Improve quiz CTA in welcome message; make the 2-min promise more prominent';
    case 'Quiz→Offer':
      return 'Quiz completers aren\'t exploring further — improve plan CTA buttons or add a nudge';
    case 'Offer→Booked':
      return 'People view offers but don\'t book — strengthen the "what you\'ll get on the call" message';
    default:
      return 'Review the lowest-converting step and experiment with copy/CTA';
  }
}

function formatDate(d) {
  return Utilities.formatDate(d, 'Asia/Dubai', 'yyyy-MM-dd');
}

function sendTelegram(text) {
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
  const payload = {
    chat_id: CHAT_ID,
    text: text,
    parse_mode: 'HTML'
  };
  
  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch(url, options);
    Logger.log('Telegram response: ' + response.getContentText());
  } catch(e) {
    Logger.log('Telegram send failed: ' + e.message);
  }
}

function logToKPITab(ss, weekStart, joins, quizzes, resources, offers, booked, community,
                     r1, r2, r3, bottleneck) {
  let kpiSheet = ss.getSheetByName('KPI_Weekly');
  
  // Create the tab if it doesn't exist
  if (!kpiSheet) {
    kpiSheet = ss.insertSheet('KPI_Weekly');
    kpiSheet.appendRow([
      'week_start', 'joins', 'quizzes', 'resources', 'offers', 
      'booked', 'community', 'rate_join_to_quiz', 'rate_quiz_to_offer',
      'rate_offer_to_book', 'bottleneck', 'notes'
    ]);
  }
  
  kpiSheet.appendRow([
    weekStart, joins, quizzes, resources, offers,
    booked, community, r1 + '%', r2 + '%', r3 + '%', bottleneck, ''
  ]);
}

// ═══════════════════════════════════════════════════════
//  MANUAL TEST — run this to verify Telegram delivery
// ═══════════════════════════════════════════════════════
function testTelegramConnection() {
  sendTelegram('✅ Empire Weekly Report — Telegram connection test successful!');
}
