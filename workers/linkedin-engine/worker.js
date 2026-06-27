/**
 * LinkedIn Content Engine v3.0 — Cloudflare Worker
 * ============================================================================
 * MACAL Empire "Common Sense First" — daily brand-voice LinkedIn posts delivered
 * to Telegram with one-tap approval. Nothing auto-publishes.
 *
 * v3.0 UPGRADES:
 *   - 50+ pre-written power hooks (5 categories)
 *   - 25 visual composition styles for image prompts
 *   - 15 content formats (up from 9)
 *   - Angle randomizer (perspective x emotion x structure) — regeneration = genuinely different
 *   - Self-contained carousel (8-10 slides as formatted Telegram text, no Google Apps Script)
 *   - 15+ evergreen posts covering all pillars
 *   - All buttons working: Approve, Regenerate, Hook, Tweak, Image, Carousel, Skip
 *
 * Cockpit buttons:
 *   [Approve & Save] [Regenerate] [Other hook] [Tweak]
 *   [New image] [Carousel] [Skip]
 *
 * Admin commands: /new  /queue  /export  /clearqueue  /stats  /pillars  /version
 */

// ============================================================
//  1) SECRETS / INTEGRATIONS
// ============================================================
const TELEGRAM_TOKEN_FALLBACK = "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE";
const ADMIN_CHAT_ID_FALLBACK  = "PUT_YOUR_TELEGRAM_CHAT_ID_HERE";
const GEMINI_API_KEY_FALLBACK = "PUT_YOUR_GEMINI_API_KEY_HERE";
const GROQ_API_KEY_FALLBACK   = "";

const PUBLISH_WEBHOOK_URL_FALLBACK = "";

const VERSION = "linkedin-engine v3.0";
const GEMINI_MODEL = "gemini-2.5-flash-lite";
const GROQ_MODEL   = "llama-3.3-70b-versatile";
const IMAGE_MODEL  = "@cf/black-forest-labs/flux-1-schnell";


// ============================================================
//  2) BRAND VOICE
// ============================================================
const LANGUAGE = "en";

const BRAND_VOICE = `
MACAL Empire voice — "Common Sense First". I cut through noise, jargon, and hype with
straight talk and proven principles. Persona: a seasoned operator (real estate, markets,
capital protection) who's been through multiple cycles. Three tones, always blended:
- Authoritative but NOT arrogant — authority comes from proof and reps, never posturing.
- Sarcastic but NEVER cruel — sarcasm is a scalpel that exposes absurdity, not a weapon.
- Paternal / protective — I warn the reader like a father who wishes someone had warned him.
Worldview: hard work beats hype every time; if it sounds too good to be true, grab your
wallet; the best tool is the one that works; complexity is often a smokescreen; respect is
earned by showing up and delivering. Underneath everything: family, legacy, and protecting
people's futures. Plain-spoken, experienced, honest, direct, unapologetic, grounded, real.
`.trim();

const BEST_POSTS = [
`You know what's crazy? People are paying $800,000 for a 600-square-foot condo because it has "smart home features."
It has a Wi-Fi thermostat, Karen. That's not smart. That's a thermostat with an app.
Here's the common-sense version: a home is shelter that holds its value. Not a gadget you finance for 30 years.
You don't build wealth chasing shiny features. You build it on fundamentals — location, cash flow, and a price that makes sense.
The market doesn't care how cool your thermostat is. It cares whether you overpaid.
We don't do hype. We do homework.`,
`They promise passive income with zero effort.
I'll promise you this: the only thing passive about that plan is how passively you'll watch your money disappear.
Real estate is like hunting. You don't bag a trophy buck by sitting on the couch posting about it. You scout. You wait. You prepare. Then you move.
The "overnight success" guys are selling you the highlight reel and skipping the three years of boring reps that actually built it.
Do the homework or be the lesson. Your call.`,
`Twenty years in this business, and I still see folks treat a mortgage like a personality trait.
A '69 Mustang with a solid frame will outlast a brand-new luxury sedan full of electrical gremlins. Old and solid beats new and fragile — every time.
Same with your money. Boring fundamentals will quietly outlast flashy speculation dressed up as "strategy."
I'm telling you this because I wish someone had told me at 25.
Build smart. Build solid. And never trust a guy in a rented suit selling shortcuts.`,
];


const SARCASM_MAX_LEVEL = 3;
const SARCASM_PROBABILITY = 0.5;
const PROMO_EVERY_N_POSTS = 6;
const PROMO_BRANDS = [
  "Macal Empire (real estate, secondary market, and capital protection)",
  "Empire English Community (my community for learning English with confidence)",
];

const BRAND_IMAGE_STYLE =
  "Premium, grounded, masculine editorial illustration. Deep matte black background with rich " +
  "gold (#D4AF37) accents, empire/royal aesthetic crossed with rugged classic Americana (classic " +
  "cars, workshop tools, the outdoors). High contrast, cinematic lighting, lots of negative space, " +
  "no text, no words, no logos, sophisticated, timeless, 4k.";
const AUTO_IMAGE = true;
const BRAND_HANDLE = "MACAL Empire — Common Sense First";

// ============================================================
//  3) CONTENT MATRIX — EXPANDED (15 formats, 13 pillars)
// ============================================================
const PILLARS = [
  "investing", "financial markets", "trading", "real estate", "AI",
  "marketing", "social media", "design", "modeling", "cooking",
  "writing", "life coaching", "entrepreneurship",
];

const FORMATS = [
  "contrarian take",
  "personal story",
  "actionable how-to",
  "numbered listicle",
  "mini case study",
  "myth-bust",
  "thought-provoking question",
  "lessons learned",
  "carousel deep-dive",
  "before vs after",
  "one principle explained",
  "unpopular opinion",
  "analogy breakdown",
  "rapid-fire tips",
  "letter to my younger self",
];


const HASHTAG_BANK = {
  "investing":         ["#Investing", "#WealthBuilding", "#FinancialFreedom", "#MoneyMindset"],
  "financial markets": ["#Markets", "#Finance", "#Economy", "#Investing"],
  "trading":           ["#Trading", "#Markets", "#RiskManagement", "#Discipline"],
  "real estate":       ["#RealEstate", "#PropertyInvesting", "#Wealth", "#RealEstateInvesting"],
  "AI":                ["#AI", "#ArtificialIntelligence", "#Automation", "#FutureOfWork"],
  "marketing":         ["#Marketing", "#Branding", "#GrowthMarketing", "#ContentStrategy"],
  "social media":      ["#SocialMedia", "#ContentCreation", "#PersonalBrand", "#CreatorEconomy"],
  "design":            ["#Design", "#DesignThinking", "#Creativity", "#Branding"],
  "modeling":          ["#Modeling", "#Confidence", "#PersonalBrand", "#Mindset"],
  "cooking":           ["#Cooking", "#Food", "#Discipline", "#Creativity"],
  "writing":           ["#Writing", "#Copywriting", "#Storytelling", "#ContentCreation"],
  "life coaching":     ["#LifeCoaching", "#PersonalGrowth", "#Mindset", "#SelfImprovement"],
  "entrepreneurship":  ["#Entrepreneurship", "#StartupLife", "#Business", "#Founder"],
};

const HOW_MANY_RECENT_TO_AVOID = 4;


// ============================================================
//  4) POWER HOOKS — 55 pre-written opening lines (5 categories x 11)
// ============================================================
const POWER_HOOKS = {
  // Category 1: Absurdity callouts
  absurdity: [
    "You know what's crazy? We have more information than ever and somehow make worse decisions.",
    "Everyone's an expert on social media. Nobody's an expert at showing up for 10 years straight.",
    "We've normalized paying $7 for coffee but panicking over a $7 book that could change your life.",
    "People will spend 3 hours researching a TV purchase and 3 minutes researching where to put their retirement.",
    "The internet convinced an entire generation that watching someone else work counts as learning.",
    "We live in an era where a 22-year-old with a ring light gives financial advice to people with mortgages.",
    "Somehow 'doing the boring thing consistently' became a revolutionary business strategy.",
    "Half the business advice online is written by people whose only business is selling business advice.",
    "We've got apps that track our sleep, our steps, our calories — but nobody tracks whether they actually kept their promises this week.",
    "The average person scrolls the equivalent of 300 feet of content a day and retains approximately none of it.",
    "People will ghost a $200/hour mentor but show up daily for a free guru who's never built anything.",
  ],
  // Category 2: Contrarian / unpopular truth
  contrarian: [
    "Unpopular opinion: most 'passive income' is just deferred disappointment.",
    "The market doesn't reward the smartest person in the room. It rewards the most patient.",
    "Your network isn't your net worth. Your ability to deliver is.",
    "Nobody ever went broke by admitting they don't know something.",
    "The worst investment advice always starts with 'trust me, this time it's different.'",
    "Hard truth: if your strategy only works in a bull market, you don't have a strategy.",
    "Consistency will always beat intensity. Always. No exceptions.",
    "The people who talk the most about hustle culture are usually the ones selling courses about it.",
    "Hot take: most people don't need more information. They need fewer excuses.",
    "Everyone wants to be a thought leader. Almost nobody wants to do the thinking.",
    "The best business plan in the world is worthless without someone willing to do boring work.",
  ],


  // Category 3: Paternal warnings
  paternal: [
    "I'm telling you this because I wish someone had told me 20 years ago.",
    "Listen. I've watched good people lose everything chasing shortcuts. Don't be next.",
    "Son, the guy promising you the world without sweat equity is reaching for your wallet.",
    "Here's what nobody tells you when you're starting out — and it cost me six figures to learn.",
    "If your father didn't teach you about money, let me give you the short version.",
    "I've seen this movie three times. I know how it ends. Let me save you the ticket.",
    "The most expensive lessons are the ones you refuse to learn from someone else's mistakes.",
    "Kid, when someone shows you a screenshot of their profits but hides their losses — run.",
    "You want real advice? Find someone with scars, not someone with a slide deck.",
    "Every generation gets a new version of the same scam wrapped in shinier packaging.",
    "Twenty years from now, you won't remember the viral post. You'll remember whether you built something real.",
  ],
  // Category 4: Stat/evidence openers
  stat: [
    "90% of traders lose money. The other 10% have one thing in common — and it's not talent.",
    "The average millionaire has 7 income streams. The average broke person has 7 subscriptions.",
    "It takes 10,000 hours to master a skill. Or about 3 years of showing up while everyone else quits.",
    "80% of businesses fail in 5 years. The survivors all share one boring trait: they adapted.",
    "A study showed people overestimate what they can do in a year and underestimate what they can do in a decade.",
    "The S&P 500 has averaged 10% annually for 100 years. And people are still chasing 'the next big thing.'",
    "Real estate has created more millionaires than any other asset class. Not crypto. Not stocks. Dirt.",
    "Warren Buffett made 99% of his wealth after age 50. Patience isn't a virtue — it's a strategy.",
    "Only 3% of people who start a course finish it. That's not a learning problem. That's a commitment problem.",
    "The average CEO reads 60 books a year. The average person reads 4. That gap isn't about time.",
    "First-generation wealth builders work an average of 12 years before their first major breakthrough.",
  ],


  // Category 5: Rhetorical questions
  rhetorical: [
    "When's the last time you did something hard on purpose — not because you had to, but because you knew it would pay off in five years?",
    "If your current strategy only works when everything goes right, is it really a strategy?",
    "What would you build if you stopped worrying about what LinkedIn thinks is 'trending'?",
    "How many times are you going to restart on Monday before you admit the plan is broken?",
    "Would you take financial advice from someone who rents everything they show you on Instagram?",
    "If you can't explain your investment to a 12-year-old, do you actually understand it?",
    "What's the point of building an audience if you have nothing real to sell them?",
    "Are you building a business or just performing one for social media?",
    "If your mentor's only proof of success is telling you they're successful — what does that tell you?",
    "Would your 10-year-from-now self thank you for what you're doing today? Or shake their head?",
    "What would happen to your income if you couldn't post online for 6 months?",
  ],
};

// Flatten for random access
const ALL_HOOKS = Object.values(POWER_HOOKS).flat();


// ============================================================
//  5) VISUAL COMPOSITION STYLES — 25 unique image prompt modifiers
// ============================================================
const VISUAL_STYLES = [
  "dramatic low-angle shot with deep shadows and a single gold spotlight",
  "aerial bird's-eye view of geometric patterns, matte black and gold palette",
  "split composition — left side chaos, right side clean order, divided by a gold line",
  "extreme close-up of weathered hands working with precision tools",
  "silhouette against a massive golden sunset, wide cinematic aspect",
  "noir-style high contrast with rain reflections on dark pavement",
  "minimalist single object centered on vast negative space, spotlight from above",
  "double exposure blending a cityscape with mechanical gears",
  "vintage workshop scene with warm tungsten light and dust particles",
  "architectural symmetry with leading lines converging to a vanishing point",
  "underwater shot with light rays penetrating dark depths, gold shimmer",
  "time-lapse motion blur of a city at night with golden light trails",
  "rugged outdoor landscape at golden hour with a lone figure in the distance",
  "chiaroscuro portrait lighting (Rembrandt-style) on objects, not faces",
  "deconstructed mechanical parts floating in zero gravity against black",
  "smoke and fog with backlit gold particles suspended in air",
  "reflections on polished obsidian surface with a single gold element",
  "macro photography of textures — wood grain, metal, leather — extreme detail",
  "isometric 3D render of abstract building blocks in black and gold",
  "long exposure of a winding road through mountains at twilight",
  "shattered glass reconstruction with gold kintsugi repair lines",
  "blueprint/technical drawing style with gold annotations on dark navy",
  "campfire scene at night — warm glow against cold darkness",
  "vintage film grain with muted tones and a single saturated gold accent",
  "chess pieces on a board with dramatic side-lighting and shallow depth of field",
];


// ============================================================
//  6) ANGLE RANDOMIZER — 3 independent axes for genuine variety
// ============================================================
const ANGLES = {
  perspective: [
    "seasoned operator sharing a war story",
    "protective father giving tough love",
    "mentor coaching a protege through a mistake",
    "contrarian calling out industry BS",
    "storyteller painting a vivid scene",
    "analyst breaking down the numbers cold",
  ],
  emotion: [
    "fired-up and fed up with the nonsense",
    "calm and reflective after years of experience",
    "protective — trying to save someone from a costly mistake",
    "amused by the absurdity of modern hype",
    "dead-serious with zero room for games",
    "encouraging — building someone up with truth",
  ],
  structure: [
    "open with a bold claim then prove it",
    "open with a shocking stat then explain why it matters",
    "open with an absurd observation then name the real problem",
    "open with a short personal story then extract the lesson",
    "open with a contrast (then vs now, them vs us) then land the point",
    "open with a direct question then answer it with authority",
  ],
};


// ============================================================
//  7) EVERGREEN FALLBACK BANK — 16 posts across all pillars
// ============================================================
const EVERGREEN = [
  { pillar:"entrepreneurship", hook:"Everyone wants the trophy. Nobody wants the cold mornings in the blind.",
    body:"The trophy shot is 30 seconds.\nThe scouting, the waiting, the boring reps — that's 3 years.\n\nThe folks you admire aren't more talented. They just kept showing up on the days it felt pointless.\n\nConsistency isn't flashy. It's just undefeated.\n\nWe don't do hype. We do homework.",
    hashtags:["#Entrepreneurship", "#Discipline", "#CommonSense"],
    image:"a lone hunter waiting patiently in a misty blind at dawn",
    comments:["What's one boring rep you're committing to this month?"] },
  { pillar:"investing", hook:"The best investment I ever made paid 0% for two years.",
    body:"It wasn't a stock. It was a skill.\n\nIt paid nothing while I learned it. Then it paid for everything after.\n\nA '69 Mustang with a solid frame outlasts a flashy sedan full of electrical gremlins. Old and solid beats new and fragile.\n\nStop optimizing for this quarter. Start compounding for this decade.",
    hashtags:["#Investing", "#WealthBuilding", "#CommonSense"],
    image:"a restored classic car engine gleaming under workshop light",
    comments:["What skill are you compounding right now?"] },
  { pillar:"real estate", hook:"They keep building McMansions nobody can afford while families can't find a starter home.",
    body:"It's like bringing a million-dollar race car to a demolition derby. Wrong tool, wrong arena, wrong result.\n\nA home isn't a gadget you finance for 30 years. It's shelter that holds its value.\n\nThe market doesn't care how smart your thermostat is. It cares whether you overpaid.\n\nBuild smart. Build solid.",
    hashtags:["#RealEstate", "#PropertyInvesting", "#CommonSense"],
    image:"a solid brick family home foundation at golden hour",
    comments:["Buyers: what's the most overpriced 'feature' you've been pitched?"] },


  { pillar:"trading", hook:"The market doesn't care about your feelings. It cares about your preparation.",
    body:"Every blown account I've seen had the same story: too much leverage, too little patience, too much ego.\n\nTrading isn't a slot machine. It's a chess game where you only move when the odds are stacked in your favor.\n\nThe pros don't win by being right more often. They win by losing small and winning big.\n\nDiscipline isn't sexy. But bankruptcy is worse.",
    hashtags:["#Trading", "#RiskManagement", "#Discipline"],
    image:"a chess clock ticking in dramatic side-lighting",
    comments:["What's the most expensive lesson the market taught you?"] },
  { pillar:"AI", hook:"AI won't replace you. A person who uses AI will replace a person who doesn't.",
    body:"The calculator didn't replace accountants. It made good ones faster and lazy ones obsolete.\n\nSame playbook. Different decade.\n\nStop debating whether AI is 'ethical enough.' Start asking: am I learning fast enough?\n\nThe tool doesn't care about your opinion of it. It just works for whoever picks it up first.\n\nAdapt or spectate. Your call.",
    hashtags:["#AI", "#FutureOfWork", "#Automation"],
    image:"a craftsman's workbench with both antique tools and a glowing modern device",
    comments:["What's one task you automated this month that used to eat your time?"] },
  { pillar:"marketing", hook:"The best marketing doesn't look like marketing. It looks like someone telling the truth.",
    body:"People can smell a pitch from three scrolls away.\n\nYou know what they can't resist? Someone who says what everyone's thinking but nobody's brave enough to post.\n\nStop writing like a brochure. Start writing like a human with an opinion.\n\nThe brands that win aren't the loudest. They're the most honest.\n\nTruth is the ultimate growth hack.",
    hashtags:["#Marketing", "#ContentStrategy", "#Branding"],
    image:"a megaphone lying unused next to a person having genuine conversation",
    comments:["What brand earned your trust by being brutally honest?"] },


  { pillar:"social media", hook:"You don't have a content problem. You have a courage problem.",
    body:"Everyone's got ideas. Everyone's got opinions.\n\nThe gap isn't creativity — it's the willingness to hit publish when it's imperfect.\n\nPerfection is procrastination in a fancy outfit.\n\nThe algorithm rewards consistency. Your audience rewards honesty. Neither one rewards waiting until you 'feel ready.'\n\nPost it. Learn. Adjust. Repeat.",
    hashtags:["#SocialMedia", "#ContentCreation", "#PersonalBrand"],
    image:"a publish button glowing in darkness surrounded by crumpled drafts",
    comments:["What post are you sitting on right now that you're afraid to publish?"] },
  { pillar:"design", hook:"Good design is invisible. Bad design is unforgettable — for all the wrong reasons.",
    body:"Nobody notices when a door opens smoothly. Everyone remembers pushing a pull door.\n\nDesign isn't decoration. It's removing friction until the obvious path is the only path.\n\nThe best product wins by being the simplest to use, not the prettiest to screenshot.\n\nSubtract until only the essential remains.\n\nThat's the whole game.",
    hashtags:["#Design", "#DesignThinking", "#Simplicity"],
    image:"a perfectly balanced single stone on a zen garden, minimal composition",
    comments:["What's a design that frustrated you this week?"] },
  { pillar:"modeling", hook:"Confidence isn't something you feel. It's something you build — rep by rep.",
    body:"I've met models who look like statues and can't hold a room.\n\nAnd I've met average-looking people who own every space they walk into.\n\nThe difference? Reps. They've practiced being themselves until it became magnetic.\n\nConfidence is a skill, not a gift. It's built in the mirror, on the stage, in the room — not in your head.\n\nStop waiting to feel ready. Start acting like you already are.",
    hashtags:["#Confidence", "#PersonalBrand", "#Mindset"],
    image:"a figure walking through a golden doorway with purposeful stride",
    comments:["What's one confidence rep you're going to do today?"] },


  { pillar:"cooking", hook:"Every man should know how to cook at least three meals from scratch. No excuses.",
    body:"Cooking isn't about impressing people. It's about self-sufficiency.\n\nA man who can't feed himself is dependent. Full stop.\n\nYou don't need a culinary degree. You need a sharp knife, a hot pan, and the discipline to follow a recipe before you start improvising.\n\nMaster the basics. Then break the rules.\n\nSame as business. Same as life.",
    hashtags:["#Cooking", "#Discipline", "#SelfReliance"],
    image:"a cast iron skillet on open flame with dramatic steam rising",
    comments:["What's the one dish every person should master?"] },
  { pillar:"writing", hook:"Write like you talk. Then edit like you think.",
    body:"The best writers don't sound like writers. They sound like smart friends at a dinner table.\n\nFirst draft: let it flow. Say it ugly. Get the idea out.\n\nSecond pass: cut every word that doesn't earn its seat.\n\nThe craft isn't in fancy vocabulary. It's in making complex ideas feel obvious.\n\nIf your reader has to re-read a sentence, you failed that sentence.\n\nSimple wins. Every time.",
    hashtags:["#Writing", "#Copywriting", "#Storytelling"],
    image:"a notebook with crossed-out lines and one clean sentence remaining",
    comments:["What's the best writing advice you've ever received?"] },
  { pillar:"life coaching", hook:"Stop looking for motivation. Start building systems that don't require it.",
    body:"Motivation is a feeling. Feelings come and go.\n\nSystems are structures. They work whether you feel like it or not.\n\nYou don't brush your teeth because you're motivated. You do it because it's built into your day.\n\nBuild the system. Remove the decision. Let the routine carry you on days your willpower won't.\n\nDiscipline isn't punishment. It's freedom from your own excuses.",
    hashtags:["#PersonalGrowth", "#Discipline", "#Mindset"],
    image:"a clock mechanism with precise interlocking gears in gold and black",
    comments:["What's one system that runs your life without requiring motivation?"] },


  { pillar:"financial markets", hook:"Everyone's a genius in a bull market. The real test is what you do when it bleeds.",
    body:"When everything goes up, you feel smart. But you're not smart — you're lucky.\n\nSmart is having a plan for when it drops 30% and executing that plan without panic.\n\nThe market is a wealth transfer machine. It moves money from the impatient to the patient.\n\nProtect your downside. The upside takes care of itself.\n\nWe don't predict. We prepare.",
    hashtags:["#Markets", "#Finance", "#RiskManagement"],
    image:"a calm lighthouse in a violent storm at sea",
    comments:["What's your rule for when markets drop 20%+?"] },
  { pillar:"entrepreneurship", hook:"Your first business won't make you rich. It'll make you competent. That's the point.",
    body:"Nobody talks about Business #1 — the one that taught you everything and paid you nothing.\n\nThat's not failure. That's tuition.\n\nThe guy on his fifth business knows things the first-timer can't Google. He's been punched. He's adapted. He knows which corners not to cut.\n\nStop romanticizing the launch. Respect the reps.\n\nThe money comes after the mastery. Not before.",
    hashtags:["#Entrepreneurship", "#StartupLife", "#Business"],
    image:"a worn pair of work boots next to polished dress shoes — same owner",
    comments:["How many attempts did it take before something clicked for you?"] },
  { pillar:"investing", hook:"Compound interest is the 8th wonder of the world. But only if you don't touch it for 20 years.",
    body:"Everyone quotes Einstein on compound interest.\n\nNobody mentions the part where you sit there watching paint dry for two decades.\n\nThat's the actual strategy. Boring. Slow. Unsexy. Effective.\n\nThe people getting rich slowly are too busy getting rich to post about it.\n\nMeanwhile, the 'get rich quick' crowd is on their third restart.\n\nPick boring. Pick patient. Pick winning.",
    hashtags:["#Investing", "#CompoundInterest", "#Patience"],
    image:"a single tree growing through cracked concrete, mature and strong",
    comments:["What's one investment you made 5+ years ago that you're glad you held?"] },
  { pillar:"real estate", hook:"Location, location, location. But nobody tells you HOW to evaluate location.",
    body:"Here's the cheat code: follow the infrastructure money.\n\nGovernments don't build highways, hospitals, and schools in areas they expect to decline.\n\nFind where the concrete is being poured. Buy before the ribbon-cutting.\n\nThat's not speculation. That's reading the map the government already drew for you.\n\nDo the homework. Follow the plans. Move before the crowd notices.\n\nThat's how generational wealth is built. One boring decision at a time.",
    hashtags:["#RealEstate", "#PropertyInvesting", "#WealthBuilding"],
    image:"an architectural blueprint with golden location markers on a dark table",
    comments:["What's the one thing you check first when evaluating a property location?"] },
];


// ============================================================
//  8) RUNTIME — entrypoints
// ============================================================
export default {
  async fetch(req, env) {
    if (req.method !== "POST") return new Response(VERSION + " OK");
    let u; try { u = await req.json(); } catch (e) { return new Response("ok"); }
    try {
      if (u.callback_query) await onCallback(u.callback_query, env);
      else if (u.message)   await onMessage(u.message, env);
    } catch (err) {
      await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Error: " + (err && err.stack ? err.stack : err) });
    }
    return new Response("ok");
  },

  async scheduled(event, env) {
    await generateAndDeliver(env, { reason: "daily" });
  },
};

// ============================================================
//  9) HELPERS
// ============================================================
function TOKEN(env)       { return (env && env.TELEGRAM_TOKEN) || TELEGRAM_TOKEN_FALLBACK; }
function ADMIN(env)       { return (env && env.ADMIN_CHAT_ID) || ADMIN_CHAT_ID_FALLBACK; }
function GKEY(env)        { return (env && env.GEMINI_API_KEY) || GEMINI_API_KEY_FALLBACK; }
function QKEY(env)        { return (env && env.GROQ_API_KEY) || GROQ_API_KEY_FALLBACK; }
function PUBLISH_URL(env) { return (env && env.PUBLISH_WEBHOOK_URL) || PUBLISH_WEBHOOK_URL_FALLBACK; }

async function tg(env, method, payload) {
  return fetch(`https://api.telegram.org/bot${TOKEN(env)}/${method}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}
async function tgPhoto(env, chatId, bytes, caption) {
  const form = new FormData();
  form.append("chat_id", String(chatId));
  if (caption) form.append("caption", caption);
  form.append("photo", new Blob([bytes], { type: "image/png" }), "post.png");
  return fetch(`https://api.telegram.org/bot${TOKEN(env)}/sendPhoto`, { method: "POST", body: form });
}
function K(rows) { return { inline_keyboard: rows }; }
function B(t, d) { return { text: t, callback_data: d }; }
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function pickN(arr, n) {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}
function weightedPick(items, weights) {
  const total = weights.reduce((a, b) => a + b, 0);
  let r = Math.random() * total;
  for (let i = 0; i < items.length; i++) { r -= weights[i]; if (r <= 0) return items[i]; }
  return items[items.length - 1];
}
function b64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}


const TWEAKMARK = "Tweak instructions for draft #";

function draftKeyboard() {
  return K([
    [B("Approve & Save", "lp:ap"), B("Regenerate", "lp:rg")],
    [B("Other hook", "lp:hk"), B("Tweak", "lp:tw")],
    [B("New image", "lp:img"), B("Carousel", "lp:car")],
    [B("Skip", "lp:sk")],
  ]);
}

// ============================================================
//  10) ANGLE RANDOMIZER — generates a unique creative angle each time
// ============================================================
function randomAngle() {
  return {
    perspective: pick(ANGLES.perspective),
    emotion: pick(ANGLES.emotion),
    structure: pick(ANGLES.structure),
  };
}

// Pick a power hook that matches the chosen structure type
function pickHookForAngle(angle) {
  // Map structure keywords to hook categories
  if (angle.structure.includes("stat")) return pick(POWER_HOOKS.stat);
  if (angle.structure.includes("absurd")) return pick(POWER_HOOKS.absurdity);
  if (angle.structure.includes("question")) return pick(POWER_HOOKS.rhetorical);
  if (angle.structure.includes("contrast") || angle.structure.includes("bold claim")) return pick(POWER_HOOKS.contrarian);
  if (angle.structure.includes("story")) return pick(POWER_HOOKS.paternal);
  // Default: random from all
  return pick(ALL_HOOKS);
}


// ============================================================
//  11) TOPIC ROTATION (approval-weighted + idea inbox)
// ============================================================
async function chooseTopic(env) {
  let recent = [], stats = {}, ideas = [];
  if (env && env.KV) {
    recent = (await env.KV.get("recent", "json")) || [];
    stats  = (await env.KV.get("stats", "json")) || {};
    ideas  = (await env.KV.get("ideas", "json")) || [];
  }

  // Idea inbox: if you texted the bot a raw idea, use (and consume) the oldest one.
  let seed = null;
  if (ideas.length) {
    seed = ideas.shift().text;
    if (env && env.KV) await env.KV.put("ideas", JSON.stringify(ideas));
  }

  const recentPillars = recent.slice(-HOW_MANY_RECENT_TO_AVOID).map(r => r.pillar);
  let available = PILLARS.filter(p => !recentPillars.includes(p));
  if (available.length === 0) available = PILLARS.slice();

  // Weight by approve/skip behaviour (Laplace-smoothed)
  const weights = available.map(p => {
    const s = stats[p] || { approved: 0, skipped: 0 };
    return (s.approved + 1) / (s.approved + s.skipped + 2);
  });
  const pillar = weightedPick(available, weights);
  const format = pick(FORMATS);

  let count = 0;
  if (env && env.KV) count = Number(await env.KV.get("post_count")) || 0;
  const isPromo = PROMO_EVERY_N_POSTS > 0 && (count + 1) % PROMO_EVERY_N_POSTS === 0;
  const promoBrand = isPromo ? pick(PROMO_BRANDS) : null;
  const sarcasm = Math.random() < SARCASM_PROBABILITY ? 1 + Math.floor(Math.random() * SARCASM_MAX_LEVEL) : 0;

  // v3.0: generate a random angle for this draft
  const angle = randomAngle();

  return { pillar, format, isPromo, promoBrand, sarcasm, seed, angle };
}

async function rememberTopic(env, topic) {
  if (!env || !env.KV) return;
  const recent = (await env.KV.get("recent", "json")) || [];
  recent.push({ pillar: topic.pillar, format: topic.format, ts: Date.now() });
  await env.KV.put("recent", JSON.stringify(recent.slice(-20)));
  const count = (Number(await env.KV.get("post_count")) || 0) + 1;
  await env.KV.put("post_count", String(count));
}

async function bumpStat(env, pillar, key) {
  if (!env || !env.KV || !pillar) return;
  const stats = (await env.KV.get("stats", "json")) || {};
  stats[pillar] = stats[pillar] || { approved: 0, skipped: 0 };
  stats[pillar][key] = (stats[pillar][key] || 0) + 1;
  await env.KV.put("stats", JSON.stringify(stats));
}


// ============================================================
//  12) PROMPT BUILDING + AI CALLS
// ============================================================
function buildPrompt(topic, tweakInstruction) {
  const langLine = LANGUAGE === "ar" ? "Write the post in Arabic."
    : LANGUAGE === "mix" ? "Write in whichever language (English or Arabic) best fits the topic."
    : "Write the post in English.";

  const sarcasmLine = topic.sarcasm > 0
    ? `Sarcasm: ON at intensity ${topic.sarcasm}/3. RULES: punch up at systems/scams/hype, never at people struggling; always follow sarcasm with substance; keep it clean; pass the "friendly wink" test.`
    : "Sarcasm: OFF — sincere, direct, and protective.";

  const promoLine = topic.isPromo && topic.promoBrand
    ? `At the end, weave ONE soft mention of "${topic.promoBrand}" with a light CTA. Not salesy.`
    : "Do NOT promote any product or brand. Pure value only.";

  const seedLine = topic.seed
    ? `\nBase the post on THIS idea from me: "${topic.seed}"`
    : "";

  // v3.0: inject the random angle
  const angleLine = topic.angle
    ? `\nANGLE FOR THIS POST:\n- Perspective: ${topic.angle.perspective}\n- Emotional tone: ${topic.angle.emotion}\n- Structure: ${topic.angle.structure}`
    : "";

  // v3.0: provide a power hook as inspiration
  const suggestedHook = topic.angle ? pickHookForAngle(topic.angle) : pick(ALL_HOOKS);
  const hookLine = `\nINSPIRATION HOOK (use as-is OR write something better in the same spirit):\n"${suggestedHook}"`;

  const examples = BEST_POSTS
    .map((p, i) => `--- EXAMPLE ${i + 1} ---\n${p.trim()}`)
    .filter(e => e.replace(/--- EXAMPLE \d+ ---/, "").trim().length > 0)
    .join("\n\n");

  const tweakLine = tweakInstruction
    ? `\n\nIMPORTANT REVISION: "${tweakInstruction}"`
    : "";

  return `You are my ghostwriter for LinkedIn. Match MY voice precisely.

MY VOICE:
${BRAND_VOICE}

${examples ? "EXAMPLES OF MY VOICE:\n" + examples + "\n" : ""}
TODAY'S BRIEF:
- Pillar: ${topic.pillar}
- Format: ${topic.format}
- ${langLine}
- ${sarcasmLine}
- ${promoLine}${seedLine}${angleLine}${hookLine}

STRUCTURE:
1. HOOK (first line): stop the scroll in 5 seconds. Use the inspiration hook or write better.
2. MEAT: deliver through ONE relatable analogy (hunting, tools, classic cars, sports, military, family).
3. CLOSE: direct, punchy, authoritative sign-off.

HARD RULES:
- Short, punchy lines. Fragments for emphasis. One idea per sentence. End paragraphs with a kicker.
- No jargon without translation. No guaranteed returns. No attacks on individuals.
- No profanity. No fluff. No "In today's fast-paced world". Plain text only (no markdown).
- Every claim backed by logic. 80-200 words for body. End inviting a reply.
- A 12-year-old should understand the main point.${tweakLine}

Return ONLY valid JSON:
{
  "hooks": ["hook 1", "hook 2", "hook 3"],
  "body": "post body WITHOUT hook and WITHOUT hashtags",
  "hashtags": ["#Tag1", "#Tag2", "#Tag3"],
  "image_prompt": "visual concept for the post, no text in image",
  "comments": ["first-comment idea 1", "first-comment idea 2", "first-comment idea 3"]
}`;
}


function extractJson(text) {
  if (!text) return null;
  let t = text.trim().replace(/^```json\s*/i, "").replace(/^```\s*/, "").replace(/```\s*$/, "");
  const s = t.indexOf("{"), e = t.lastIndexOf("}");
  if (s !== -1 && e !== -1 && e > s) t = t.slice(s, e + 1);
  try { return JSON.parse(t); } catch (err) { return null; }
}

async function callGemini(env, prompt) {
  const key = GKEY(env);
  if (!key || key.indexOf("PUT_YOUR") === 0) return null;
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${key}`;
  const res = await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.95, responseMimeType: "application/json" },
    }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  const text = data && data.candidates && data.candidates[0] &&
    data.candidates[0].content && data.candidates[0].content.parts &&
    data.candidates[0].content.parts[0] && data.candidates[0].content.parts[0].text;
  return extractJson(text);
}

async function callGroq(env, prompt) {
  const key = QKEY(env);
  if (!key) return null;
  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key },
    body: JSON.stringify({
      model: GROQ_MODEL, temperature: 0.95,
      messages: [
        { role: "system", content: "You are an expert LinkedIn ghostwriter. Return valid JSON only." },
        { role: "user", content: prompt },
      ],
    }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  const text = data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
  return extractJson(text);
}


// Draft object: { pillar, format, hooks[], hookIdx, body, hashtags[], imagePrompt, comments[], source, angle }
async function generateDraft(env, topic, tweakInstruction) {
  const prompt = buildPrompt(topic, tweakInstruction);
  let out = await callGemini(env, prompt);
  let source = "gemini";
  if (!out) { out = await callGroq(env, prompt); source = "groq"; }

  if (out && Array.isArray(out.hooks) && out.body) {
    const hashtags = Array.isArray(out.hashtags) && out.hashtags.length
      ? out.hashtags : (HASHTAG_BANK[topic.pillar] || []).slice(0, 4);
    return {
      pillar: topic.pillar, format: topic.format,
      hooks: out.hooks.filter(Boolean).slice(0, 3),
      hookIdx: 0, body: String(out.body).trim(), hashtags,
      imagePrompt: out.image_prompt || `${topic.pillar}, professional conceptual illustration`,
      comments: Array.isArray(out.comments) ? out.comments.slice(0, 3) : [],
      source, angle: topic.angle || null,
    };
  }

  // Fallback: evergreen bank
  const ev = pick(EVERGREEN);
  return {
    pillar: ev.pillar, format: "evergreen", hooks: [ev.hook], hookIdx: 0,
    body: ev.body, hashtags: ev.hashtags, imagePrompt: ev.image,
    comments: ev.comments || [], source: "evergreen", angle: null,
  };
}


// ============================================================
//  13) IMAGE GENERATION (Phase 2) — now with 25 visual styles
// ============================================================
function buildImagePrompt(basePrompt) {
  // Combine the post's image concept with a random visual style
  const style = pick(VISUAL_STYLES);
  return `${basePrompt}. Composition style: ${style}. ${BRAND_IMAGE_STYLE}`;
}

async function genImage(env, prompt) {
  const ai = env && env.AI;
  if (!ai || !prompt) return null;
  try {
    const fullPrompt = buildImagePrompt(prompt);
    const res = await ai.run(IMAGE_MODEL, { prompt: fullPrompt, seed: Math.floor(Math.random() * 1e6) });
    if (res && typeof res.image === "string") return b64ToBytes(res.image);
    if (res instanceof ReadableStream) return new Uint8Array(await new Response(res).arrayBuffer());
    if (res instanceof ArrayBuffer) return new Uint8Array(res);
    return null;
  } catch (e) { return null; }
}

async function maybeSendImage(env, draft) {
  if (!AUTO_IMAGE || !(env && env.AI)) return;
  const bytes = await genImage(env, draft.imagePrompt);
  if (bytes) await tgPhoto(env, ADMIN(env), bytes, "Suggested image (tap New image to regenerate)").catch(() => {});
}


// ============================================================
//  14) SELF-CONTAINED CAROUSEL — generates 8-10 slides as Telegram text
//      NO Google Apps Script dependency. Just formatted text slides.
// ============================================================
async function generateCarouselText(env, draft) {
  const prompt = `Turn this LinkedIn post into a punchy CAROUSEL of 8-10 slides.

RULES:
- Slide 1: Bold cover hook (just the big statement, attention-grabbing)
- Slides 2-8: Each makes ONE point. Title (max 6 words) + body (max 20 words)
- Second-to-last slide: Summary/recap of key points
- Last slide: Call-to-action (follow, comment, share)
- Keep it punchy, visual-friendly, direct
- No markdown, no asterisks

POST:
${renderPost(draft)}

Return ONLY valid JSON:
{"slides":[{"title":"slide title","body":"slide body text"}]}`;

  let out = await callGemini(env, prompt);
  if (!out) out = await callGroq(env, prompt);
  if (out && Array.isArray(out.slides) && out.slides.length >= 4) return out.slides;

  // Fallback: manually split the post into slide-sized chunks
  const lines = draft.body.split("\n").filter(l => l.trim());
  const slides = [
    { title: "COVER", body: draft.hooks[draft.hookIdx] || draft.hooks[0] || "" },
  ];
  for (let i = 0; i < Math.min(lines.length, 7); i++) {
    slides.push({ title: `Point ${i + 1}`, body: lines[i].trim() });
  }
  slides.push({ title: "Follow for more", body: "Common Sense First. No hype. No shortcuts." });
  return slides;
}

function formatCarouselMessage(slides) {
  const divider = "━━━━━━━━━━━━━━━━━━━━";
  let msg = "🎠 CAROUSEL SLIDES\n" + divider + "\n\n";

  for (let i = 0; i < slides.length; i++) {
    const s = slides[i];
    const num = String(i + 1).padStart(2, "0");
    msg += `📄 SLIDE ${num}/${String(slides.length).padStart(2, "0")}\n`;
    msg += `▸ ${s.title}\n`;
    if (s.body) msg += `${s.body}\n`;
    msg += "\n" + (i < slides.length - 1 ? "- - - - - - - - - - -\n\n" : "");
  }

  msg += divider + "\n";
  msg += `📋 ${slides.length} slides ready.\n`;
  msg += "Screenshot each slide or use as text carousel on LinkedIn.\n";
  msg += `🏷️ ${BRAND_HANDLE}`;
  return msg;
}


// ============================================================
//  15) RENDERING + DELIVERY
// ============================================================
function renderPost(draft) {
  const hook = draft.hooks[draft.hookIdx] || draft.hooks[0] || "";
  const tags = (draft.hashtags || []).join(" ");
  return `${hook}\n\n${draft.body}${tags ? "\n\n" + tags : ""}`;
}

function renderTelegram(draft, topic) {
  const post = renderPost(draft);
  const angleInfo = topic && topic.angle
    ? ` | ${topic.angle.perspective.split(" ")[0]}-${topic.angle.emotion.split(" ")[0]}`
    : "";
  const meta = `${draft.pillar} | ${draft.format} | ${draft.source}` +
    (topic && topic.isPromo ? " | promo" : "") +
    (topic && topic.sarcasm ? ` | sarcasm ${topic.sarcasm}` : "") +
    (topic && topic.seed ? " | your idea" : "") +
    angleInfo;
  return `Your LinkedIn draft\n${meta}\n\n-----\n${post}\n-----\n\nReview and tap a button below`;
}

async function generateAndDeliver(env, opts) {
  const topic = await chooseTopic(env);
  const draft = await generateDraft(env, topic);

  const sent = await tg(env, "sendMessage", {
    chat_id: ADMIN(env), text: renderTelegram(draft, topic), reply_markup: draftKeyboard(),
  });

  try {
    const j = await sent.json();
    const mid = j && j.result && j.result.message_id;
    if (mid && env && env.KV) {
      await env.KV.put("draft:" + mid, JSON.stringify({ draft, topic }), { expirationTtl: 60 * 60 * 24 * 14 });
    }
    if (env && env.KV) await rememberTopic(env, topic);
  } catch (e) { /* ignore */ }

  await maybeSendImage(env, draft);
}


// ============================================================
//  16) MESSAGE HANDLING (admin only)
// ============================================================
async function onMessage(msg, env) {
  const fromId = String(msg.from && msg.from.id);
  const text = (msg.text || "").trim();
  if (fromId !== String(ADMIN(env))) return;

  // Admin replying to a "Tweak" force-reply
  const rt = msg.reply_to_message;
  if (rt && rt.text && rt.text.indexOf(TWEAKMARK) !== -1) {
    const m = rt.text.match(/draft #(\d+)/);
    if (m && env && env.KV) {
      const mid = m[1];
      const stored = await env.KV.get("draft:" + mid, "json");
      if (stored) {
        await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Reworking with your note..." });
        const draft = await generateDraft(env, stored.topic, text);
        await env.KV.put("draft:" + mid, JSON.stringify({ draft, topic: stored.topic }), { expirationTtl: 60 * 60 * 24 * 14 });
        await tg(env, "editMessageText", {
          chat_id: ADMIN(env), message_id: Number(mid),
          text: renderTelegram(draft, stored.topic), reply_markup: draftKeyboard(),
        });
        await maybeSendImage(env, draft);
        return;
      }
    }
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "That draft expired. Send /new for a fresh one." });
    return;
  }

  if (text === "/version") {
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: VERSION + " | text:" + GEMINI_MODEL + " | img:" + IMAGE_MODEL + " | hooks:" + ALL_HOOKS.length + " | styles:" + VISUAL_STYLES.length + " | formats:" + FORMATS.length + " | evergreen:" + EVERGREEN.length });
    return;
  }
  if (text === "/new" || text === "/start") {
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Generating a fresh draft..." });
    await generateAndDeliver(env, { reason: "manual" });
    return;
  }
  if (text === "/pillars") {
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Pillars:\n- " + PILLARS.join("\n- ") });
    return;
  }


  if (text === "/stats") {
    const stats = (env && env.KV) ? ((await env.KV.get("stats", "json")) || {}) : {};
    const rows = Object.keys(stats).sort().map(p => `${p}: +${stats[p].approved || 0} / -${stats[p].skipped || 0}`);
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: rows.length ? "Approve/skip by pillar:\n" + rows.join("\n") : "No stats yet." });
    return;
  }
  if (text === "/queue") {
    const q = (env && env.KV) ? ((await env.KV.get("queue", "json")) || []) : [];
    if (!q.length) { await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Approved queue is empty." }); return; }
    const list = q.slice(-10).map((p, i) => `${i + 1}. [${p.pillar}] ${(p.text || "").split("\n")[0].slice(0, 60)}...`).join("\n");
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: `Approved (${q.length}). /export to dump:\n${list}` });
    return;
  }
  if (text === "/export") {
    const q = (env && env.KV) ? ((await env.KV.get("queue", "json")) || []) : [];
    if (!q.length) { await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Nothing to export." }); return; }
    for (let i = 0; i < q.length; i++) {
      await tg(env, "sendMessage", { chat_id: ADMIN(env), text: `${i + 1}/${q.length} [${q[i].pillar}]\n\n${q[i].text}` });
    }
    return;
  }
  if (text === "/clearqueue") {
    if (env && env.KV) await env.KV.put("queue", "[]");
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Queue cleared." });
    return;
  }

  // Unknown slash command -> help
  if (text.startsWith("/")) {
    await tg(env, "sendMessage", {
      chat_id: ADMIN(env),
      text: "LinkedIn Engine v3.0\n\n/new - generate a draft\n/queue - see approved posts\n/export - dump approved posts\n/clearqueue - empty queue\n/stats - approve/skip by pillar\n/pillars - list topics\n/version\n\nTip: text me any idea and I'll turn it into your next post.",
    });
    return;
  }

  // Plain text -> idea inbox
  if (text.length > 0) {
    if (env && env.KV) {
      const ideas = (await env.KV.get("ideas", "json")) || [];
      ideas.push({ text, ts: Date.now() });
      await env.KV.put("ideas", JSON.stringify(ideas.slice(-50)));
    }
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Idea saved. Send /new to use it now." });
    return;
  }
}


// ============================================================
//  17) CALLBACK HANDLING (button taps)
// ============================================================
async function onCallback(cq, env) {
  const presser = String(cq.from && cq.from.id);
  if (presser !== String(ADMIN(env))) { await tg(env, "answerCallbackQuery", { callback_query_id: cq.id }); return; }

  const data = cq.data || "";
  const mid = cq.message && cq.message.message_id;
  const chatId = cq.message && cq.message.chat && cq.message.chat.id;
  const ack = (t) => tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: t || "" });

  if (data.indexOf("lp:") !== 0 || !mid) { await ack(); return; }
  const action = data.split(":")[1];

  const stored = (env && env.KV) ? await env.KV.get("draft:" + mid, "json") : null;
  if (!stored) {
    await tg(env, "editMessageReplyMarkup", { chat_id: chatId, message_id: mid, reply_markup: K([]) }).catch(() => {});
    await ack("Draft expired — send /new");
    return;
  }
  let { draft, topic } = stored;

  // ---- APPROVE ----
  if (action === "ap") {
    const post = renderPost(draft);
    if (env && env.KV) {
      const q = (await env.KV.get("queue", "json")) || [];
      q.push({ pillar: draft.pillar, format: draft.format, text: post, ts: Date.now() });
      await env.KV.put("queue", JSON.stringify(q));
    }
    await bumpStat(env, draft.pillar, "approved");

    // Optional publish webhook
    if (PUBLISH_URL(env)) {
      fetch(PUBLISH_URL(env), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: post, pillar: draft.pillar, format: draft.format, hashtags: draft.hashtags }),
      }).catch(() => {});
    }

    const comments = (draft.comments || []).filter(Boolean).slice(0, 3);
    const commentBlock = comments.length
      ? "\n\nFirst-comment ideas:\n- " + comments.join("\n- ")
      : "";
    await tg(env, "editMessageText", {
      chat_id: chatId, message_id: mid,
      text: "APPROVED & SAVED\n\nCopy into LinkedIn scheduler:\n\n-----\n" + post + "\n-----" + commentBlock,
    });
    await ack("Saved");
    return;
  }


  // ---- OTHER HOOK ----
  if (action === "hk") {
    draft.hookIdx = (draft.hookIdx + 1) % Math.max(1, draft.hooks.length);
    await env.KV.put("draft:" + mid, JSON.stringify({ draft, topic }), { expirationTtl: 60 * 60 * 24 * 14 });
    await tg(env, "editMessageText", { chat_id: chatId, message_id: mid, text: renderTelegram(draft, topic), reply_markup: draftKeyboard() });
    await ack(`Hook ${draft.hookIdx + 1}/${draft.hooks.length}`);
    return;
  }

  // ---- REGENERATE (new angle!) ----
  if (action === "rg") {
    await ack("Regenerating with fresh angle...");
    // v3.0: give it a brand new angle so regeneration is genuinely different
    topic.angle = randomAngle();
    const fresh = await generateDraft(env, topic);
    await env.KV.put("draft:" + mid, JSON.stringify({ draft: fresh, topic }), { expirationTtl: 60 * 60 * 24 * 14 });
    await tg(env, "editMessageText", { chat_id: chatId, message_id: mid, text: renderTelegram(fresh, topic), reply_markup: draftKeyboard() });
    await maybeSendImage(env, fresh);
    return;
  }

  // ---- TWEAK ----
  if (action === "tw") {
    await tg(env, "sendMessage", {
      chat_id: ADMIN(env),
      text: `${TWEAKMARK}${mid}\n\nReply to THIS with what to change (e.g. "shorter", "more sarcasm", "add a stat", "different angle").`,
      reply_markup: { force_reply: true },
    });
    await ack();
    return;
  }

  // ---- NEW IMAGE ----
  if (action === "img") {
    await ack("Generating image...");
    if (!(env && env.AI)) {
      await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Image needs Workers AI binding 'AI' (see SETUP.md)." });
      return;
    }
    const bytes = await genImage(env, draft.imagePrompt);
    if (bytes) await tgPhoto(env, chatId, bytes, draft.pillar + " — " + (draft.imagePrompt || "").slice(0, 80));
    else await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Image generation failed. Try again." });
    return;
  }


  // ---- CAROUSEL (v3.0: self-contained, no external dependency) ----
  if (action === "car") {
    await ack("Building carousel...");
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: "Building your carousel slides..." });
    const slides = await generateCarouselText(env, draft);
    const msg = formatCarouselMessage(slides);
    await tg(env, "sendMessage", { chat_id: ADMIN(env), text: msg });
    return;
  }

  // ---- SKIP ----
  if (action === "sk") {
    await bumpStat(env, draft.pillar, "skipped");
    if (env && env.KV) await env.KV.delete("draft:" + mid);
    await tg(env, "editMessageText", { chat_id: chatId, message_id: mid, text: "Skipped. Send /new for another." });
    await ack("Skipped");
    return;
  }

  await ack();
}
