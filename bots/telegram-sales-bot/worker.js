/**
 * Empire English — Smart Sales Bot (v11) — Cloudflare Workers
 * Guided buttons + Arabic-clean copy + Payment approval gate
 * (crypto & bank transfer are escalated to YOU to send personally)
 * + Auto-Learn + Memory + Daily reminders + Invoice capture + Subscribe confirm + Feedback.
 *
 * Setup: fill TELEGRAM_TOKEN + ADMIN_CHAT_ID, bind KV namespace "KV", add Cron "0 16 * * *".
 * Admin: /version /kv /list /stats
 */

// ======= عدّل دول بس =======
const TELEGRAM_TOKEN = "ضع_توكن_البوت_هنا";
const ADMIN_CHAT_ID  = "ضع_رقمك_من_userinfobot_هنا";
const PAY = {
  vodafone: "01004581035",
  instapay: "01004581035 / mohamedashry10041",
  paypal:   "paypal.me/bioroma"
};
// ===========================

const VERSION = "v13";
const MARK = "💰 محتوى دفع للمراجعة (وافق قبل الإرسال):\n";
const EDITMARK = "✏️ اكتب ردك للعميل (id: ";
const LEARNMARK = "🧠 اكتب الرد وهحفظه للمرة الجاية (id: ";

const WELCOME = `أهلاً بيك في إمبراطورية Empire English 👑

إحنا مش مجرد كورس... إحنا نظام كامل بيوصّلك لطلاقة حقيقية في الإنجليزي خطوة بخطوة 🔥

اختار من القائمة وأنا معاك في كل خطوة 👇`;

const SUB_WELCOME = `مبروك 🎉👑 بقيت من الأعضاء المؤسسين! أهلاً بيك في الإمبراطورية.

الخطوات دلوقتي:
١) هبعتلك رابط المجتمع وشارة العضو المؤسس
٢) ابدأ اختبار تحديد المستوى
٣) أول مجموعة بتبدأ يوم السبت ٢٧ يونيو 🚀

مبسوطين جدًا إنك معانا 💪`;

const FEEDBACK = `إزاي تجربتك معانا لحد دلوقتي؟ 🌟
رأيك مهم جدًا — ابعتلنا كلمتين أو أي اقتراح 👑`;

// payment text (sensitive → approved by you first)
function payText(pkg){
  const head = pkg ? `تمام يا بطل 👑 باقة ${pkg} — طرق الدفع:` : `💳 طرق الدفع:`;
  return `${head}

🇪🇬 جوّه مصر:
• فودافون كاش: ${PAY.vodafone}
• إنستا باي: ${PAY.instapay}

🌍 برّه مصر:
• باي بال (PayPal): ${PAY.paypal}

🪙 عايز تدفع كريبتو (USDT) أو 🏦 تحويل بنكي؟ قوللي وأبعتلك التفاصيل على طول 👌

📸 بعد الدفع ابعت صورة الإيصال هنا وأفعّل اشتراكك فورًا كعضو مؤسس 👑`;
}

// daily reminder funnel (one per day, in order)
const REMINDERS = [
  `🌟 قصة نجاح من الإمبراطورية:\n«بدأت من الصفر وكنت بتتلعثم لما أتكلم... بعد أسابيع بقيت أمسك محادثة كاملة بثقة!»\nتحب تبدأ قصتك إنت كمان؟ 👑`,
  `🤔 لسه محتار تختار؟\nأغلب الناس بيبدأوا بباقة Builder وبيتكلموا بثقة بسرعة. قوللي هدفك وأرشّحلك الأنسب ليك 🎯👑`,
  `🛡️ قلقان تجرّب؟\nمعاك ضمان استرجاع فلوسك خلال ٧ أيام — مفيش أي مخاطرة. مبتدئ؟ بنبدأ من الصفر. مشغول؟ النظام مرن 🔥`,
  `🎁 عرض التأسيس لسه شغّال، بس الأماكن بتقل ⏳\nسعر ثابت مدى الحياة + شارة عضو مؤسس. تحب أحجزلك مكانك؟ 👑`,
  `⏰ آخر فرصة — ده آخر تذكير مني 🙏\nلو جاد إنك تتكلم إنجليزي بثقة، دي لحظتك. ابعتلي كلمة «اشتراك» وأنا أرتبلك كل حاجة 👑`,
];

// text answer bank: menu = open buttons · sensitive = payment approval · personal = you handle · else auto-reply
const ANSWERS = [
  { keys:['قائمة','القائمة','منيو','menu','ابدأ','البداية','الرئيسية'], menu:"main" },
  { keys:['الباقات','باقات','الاسعار','اسعار','السعر','بكام','الخطط','packages','price','الباقا'], menu:"packages" },
  { keys:['عايز اشترك','هشترك','اشترك','اشتراك','انضم','join','subscribe'], menu:"sub" },
  { keys:['طرق الدفع','ازاي ادفع','الدفع','ادفع','فودافون','انستا','instapay','باي بال','paypal'], sensitive:true, reply: payText(null) },
  { keys:['كريبتو','crypto','usdt','بينانس','binance','تحويل بنكي','حساب بنكي','حواله بنكيه'], personal:true },
  { keys:['غالي','غاليه','مكلف','كتير اوي','مش مناسب','السعر عالي'], reply:`أفهمك 👌 بس خليني أوضّحلك:\nده أرخص بكتير من مدرّس خصوصي، ومعاك نظام متكامل + مجتمع طول اليوم + ضمان استرجاع ٧ أيام 🛡️\nولو ميزانيتك محدودة، باقة Recruit بـ ١٩٩ جنيه بداية ممتازة، وتقدر ترفّع باقتك بعدين. تحب أرشّحلك؟ 👑` },
  { keys:['ليه اغلى بره','ليه مغليها','الفرق بين مصر وبره','ليه السعر مختلف','ليه برة مصر'], reply:`سؤال في محلّه 👍\nالسعر بيختلف حسب مستوى المعيشة في كل بلد — زي نتفليكس بالظبط. يعني المصري بيدفع أقل مش أكتر 🇪🇬، وكل بلد بسعر عادل ليها 🌍👑` },
  { keys:['recruit','ريكروت','الباقه الاولى'], reply:`باقة Recruit 🥉 — ١٩٩ جنيه / ١٩ دولار شهريًا (البداية الصح)\n\n✅ نظام يومي متكامل\n✅ ملخصات أسبوعية\n✅ قنوات المستوى (كتابة وصوت)\n✅ تقييم أسبوعي لتقدمك\n\n💡 وعشان تتكلم أسرع، باقة Builder بتزوّدلك تصحيح فوري وجلسات يومية 🔥` },
  { keys:['builder','بيلدر','الباقه التانيه','التانيه'], reply:`باقة Builder ⭐ — ٣٩٩ جنيه / ٣٩ دولار شهريًا (الأكثر اختيارًا 🔥)\n\n✅ كل مميزات Recruit\n✅ تصحيح كلامك وكتابتك بالذكاء الاصطناعي\n✅ كل الجلسات الصوتية اليومية (بتتكلم والمجموعة بتسمعك)\n✅ مكتبة أفلام وبودكاست + اختبارات الترقية\n\nدي الباقة اللي بتخليك تتكلم فعلاً 👑` },
  { keys:['empire','امباير','الباقه التالته'], reply:`باقة Empire 🥇 — ٧٩٩ جنيه / ٨٩ دولار شهريًا (نتيجة أسرع + اهتمام شخصي)\n\n✅ كل مميزات Builder\n✅ جلستين تدريب جماعي شهريًا\n✅ خطة شهرية شخصية + مراجعة فردية\n✅ شهادات إتقان معتمدة من الإمبراطورية 👑` },
  { keys:['vip','في اي بي','خاص','لوحدي','مدرس خاص'], reply:`باقة VIP 👑 — ٣٥٠٠ جنيه / ٢٤٩ دولار شهريًا (أماكن محدودة جدًا)\n\n✅ كل مميزات Empire\n✅ ٤ جلسات خاصة فردية شهريًا (إنت بس مع المدرّب)\n✅ تصحيح غير محدود خلال ٢٤ ساعة\n✅ تواصل مباشر على واتساب\n\nكأن معاك مدرّب خاص ليك لوحدك 🔥` },
  { keys:['الفرق','قارن','مقارنه','محتار','انهي احسن','انهي افضل'], menu:"compare" },
  { keys:['ساعدني','رشحلي','اختار ايه','يناسبني','انهي باقه'], menu:"help" },
  { keys:['مبتدئ','من الصفر','ضعيف','مستواي','صفر','beginner'], reply:`متقلقش خالص 🌟\nبنبدأ من المستوى صفر تمامًا، والنظام معمول للمبتدئين بالظبط، وأول ما تدخل بتعمل اختبار تحديد مستوى يحطك في المكان الصح 👑` },
  { keys:['ضمان','استرجاع','تجربه','مجاني','free','مخاطره'], reply:`معاك ضمان استرجاع فلوسك خلال ٧ أيام 🛡️\nيعني تجرّب وانت مطمّن تمامًا — لو مش مناسب ترجعلك فلوسك. مفيش أي مخاطرة 🔥👑` },
  { keys:['تسجيل','تسجيلات','مسجل','فيديو'], reply:`أيوه 🎥 كل الجلسات بتتسجّل، وتقدر ترجعلها في أي وقت طول ما اشتراكك شغّال (من باقة Builder وفوق) 👑` },
  { keys:['مواعيد','ميعاد','الساعه','بتبدا'], reply:`الجلسات يومية وفيها أكتر من معاد عشان تناسب الجميع 🎤 (وكلها بتتسجّل لو فاتك حاجة).\nالجدول الكامل بيوصلك أول ما تدخل، وأول مجموعة بتبدأ السبت ٢٧ يونيو 👑` },
  { keys:['اونلاين','حضوري','online','مكان','عن بعد'], reply:`كله أونلاين بالكامل 🌍 — مجتمع + جلسات صوتية مباشرة تحضرها من أي مكان 👑` },
  { keys:['شهاده','شهادة','certificate','ايلتس','ielts','توفل'], reply:`عندنا شهادات إتقان في باقتي Empire و VIP 🏅\nوالنظام بيقوّي مهاراتك في الكلام والاستماع اللي بتفيدك في أي امتحان زي IELTS — بس إحنا مش جهة الامتحان الرسمي 👑` },
  { keys:['نصب','مضمون','ثقة','حقيقي','تجارب'], reply:`سؤال في محلّه 👍\nعندك ضمان استرجاع ٧ أيام، وأعضاء حقيقيين بنتايج، ومجتمع شغّال طول اليوم تقدر تشوفه بنفسك 🛡️👑` },
  { keys:['عرض','خصم','اوفر','offer','discount'], sensitive:true, reply:`🎁 أحسن عرض دلوقتي:\nسعر التأسيس ثابت مدى الحياة، والاشتراك السنوي بيوفّرلك حوالي ٣٥٪.\nتحب أحجزلك قبل ما الأماكن تخلص؟ 👑` },
  { keys:['شكرا','متشكر','تسلم','thanks'], reply:`العفو يا فندم 🌟 تحت أمرك في أي وقت 👑` },
];

export default {
  async fetch(req, env, ctx){
    if (req.method !== "POST") return new Response("Empire English bot ✅ " + VERSION);
    let u; try { u = await req.json(); } catch(e){ return new Response("ok"); }
    try {
      if (u.callback_query) await onCallback(u.callback_query, env);
      else if (u.message)   await onMessage(u.message, env, ctx);
    } catch(err){ await tg("sendMessage",{chat_id:ADMIN_CHAT_ID, text:"⚠️ خطأ: "+err}); }
    return new Response("ok");
  },
  async scheduled(event, env, ctx){
    if (!env || !env.KV) return;
    const now = Date.now();
    const list = await env.KV.list({prefix:"u:"});
    for (const k of list.keys){
      const u = await env.KV.get(k.name,"json"); if(!u) continue;
      const id = k.name.slice(2);
      try {
        if (u.subscribed){
          if (!u.feedbackAsked && u.subAt && now - u.subAt > 2*864e5){ await tg("sendMessage",{chat_id:Number(id),text:FEEDBACK}); u.feedbackAsked=true; await env.KV.put(k.name,JSON.stringify(u)); }
          continue;
        }
        if ((u.reminders||0) >= REMINDERS.length) continue;
        if (now - (u.lastReminder||0) < 20*36e5) continue;
        if (now - (u.lastSeen||0) < 20*36e5) continue;
        await tg("sendMessage",{chat_id:Number(id), text:REMINDERS[u.reminders||0]});
        u.reminders=(u.reminders||0)+1; u.lastReminder=now; await env.KV.put(k.name,JSON.stringify(u));
      } catch(e){}
    }
  }
};

async function tg(method, payload){
  return fetch(`https://api.telegram.org/bot${TELEGRAM_TOKEN}/${method}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
}
function K(rows){ return {inline_keyboard: rows}; }
function B(t,d){ return {text:t, callback_data:d}; }
function bg(ctx, p){ if (ctx && ctx.waitUntil) ctx.waitUntil(p); else return p; }
function norm(s){ return (s||"").toString().toLowerCase().replace(/[\u064B-\u0652\u0670]/g,"").replace(/\u0640/g,"").replace(/[أإآ]/g,"ا").replace(/ى/g,"ي").replace(/ة/g,"ه").replace(/\s+/g," ").trim(); }

function view(name){
  if (name === "main") return { text: WELCOME, kb: K([
    [B("📦 الباقات","m:packages"), B("🎯 ساعدني أختار","m:help")],
    [B("🆚 قارن الباقات","m:compare"), B("💳 طرق الدفع","m:pay")],
    [B("❓ أسئلة شائعة","m:faq"), B("👑 عايز أشترك","m:sub")] ]) };
  if (name === "packages") return { text:`دي باقاتنا يا بطل 👑 (السعر بيتظبط حسب بلدك):\n\n🥉 Recruit — ١٩٩ج / ١٩$\n🥈 Builder ⭐ — ٣٩٩ج / ٣٩$\n🥇 Empire — ٧٩٩ج / ٨٩$\n👑 VIP — ٣٥٠٠ج / ٢٤٩$\n\nاختار باقة تعرف تفاصيلها 👇`, kb:K([
    [B("🥉 Recruit","p:recruit"), B("🥈 Builder ⭐","p:builder")],
    [B("🥇 Empire","p:empire"), B("👑 VIP","p:vip")],
    [B("👑 عايز أشترك","m:sub"), B("↩️ رجوع","m:main")] ]) };
  if (name === "compare") return { text:"عايز تقارن بين أنهي باقتين؟ 🆚", kb:K([
    [B("Recruit ⚔️ Builder","cmp:rb"), B("Recruit ⚔️ Empire","cmp:re")],
    [B("Recruit ⚔️ VIP","cmp:rv"), B("Builder ⚔️ Empire","cmp:be")],
    [B("Builder ⚔️ VIP","cmp:bv"), B("Empire ⚔️ VIP","cmp:ev")],
    [B("📊 قارن الكل","cmp:all"), B("↩️ رجوع","m:main")] ]) };
  if (name === "help") return { text:"إيه أقرب حاجة ليك؟ وأنا أرشّحلك الباقة المثالية 🎯", kb:K([
    [B("💰 ميزانيتي محدودة","rec:budget")],
    [B("🗣️ عايز أتكلم بثقة","rec:speak")],
    [B("🎯 عندي هدف أو موعد محدد","rec:goal")],
    [B("👑 عايز مدرّب خاص","rec:personal")],
    [B("↩️ رجوع","m:main")] ]) };
  if (name === "faq") return { text:"اختار سؤالك 👇", kb:K([
    [B("🛡️ الضمان","faq:guarantee"), B("🧑‍🎓 مبتدئ؟","faq:beginner")],
    [B("🎥 التسجيلات","faq:rec"), B("🕐 المواعيد","faq:time")],
    [B("🌍 أونلاين؟","faq:online"), B("💸 غالية عليّا؟","faq:price")],
    [B("↩️ رجوع","m:main")] ]) };
  if (name === "sub") return { text:"اختار باقتك وأنا أجهّزلك طريقة الدفع 👑", kb:K([
    [B("🥉 Recruit","buy:Recruit"), B("🥈 Builder ⭐","buy:Builder")],
    [B("🥇 Empire","buy:Empire"), B("👑 VIP","buy:VIP")],
    [B("↩️ رجوع","m:main")] ]) };
  return null;
}
const PKG = {
  recruit:`باقة Recruit 🥉 — ١٩٩ج / ١٩$ شهريًا (البداية الصح)\n✅ نظام يومي متكامل\n✅ ملخصات أسبوعية\n✅ قنوات المستوى (كتابة وصوت)\n✅ تقييم أسبوعي\n«تبدأ صح وتبني عادة يومية» 👑`,
  builder:`باقة Builder ⭐ — ٣٩٩ج / ٣٩$ شهريًا (الأكثر اختيارًا 🔥)\n✅ كل مميزات Recruit\n✅ تصحيح كلامك وكتابتك بالذكاء الاصطناعي\n✅ كل الجلسات الصوتية اليومية\n✅ مكتبة أفلام وبودكاست + اختبارات الترقية\n«اللي بتخليك تتكلم فعلاً» 👑`,
  empire:`باقة Empire 🥇 — ٧٩٩ج / ٨٩$ شهريًا (أسرع + اهتمام شخصي)\n✅ كل مميزات Builder\n✅ جلستين تدريب جماعي شهريًا\n✅ خطة شهرية شخصية + مراجعة فردية\n✅ شهادات إتقان 👑`,
  vip:`باقة VIP 👑 — ٣٥٠٠ج / ٢٤٩$ شهريًا (أماكن محدودة)\n✅ كل مميزات Empire\n✅ ٤ جلسات خاصة فردية شهريًا\n✅ تصحيح غير محدود\n✅ تواصل مباشر على واتساب\n«كأن معاك مدرّب خاص» 🔥`
};
const CMP = {
  rb:`⚔️ Recruit ضد Builder\n\n🥉 Recruit (١٩٩ج/١٩$): نظام يومي + ملخصات + تقييم أسبوعي — بتذاكر بمفردك بنظام منظّم.\n🥈 Builder (٣٩٩ج/٣٩$): كل ده + تصحيح كلامك بالذكاء الاصطناعي + كل الجلسات الصوتية اليومية (بتتكلم فعلاً) + مكتبة + اختبارات ترقية.\n\n📌 الخلاصة: لو عايز تتكلم وتتدرّب مع ناس، Builder هو الفرق الحقيقي 🔥`,
  re:`⚔️ Recruit ضد Empire\n\n🥉 Recruit (١٩٩ج/١٩$): مذاكرة ذاتية بنظام منظّم.\n🥇 Empire (٧٩٩ج/٨٩$): النظام + تصحيح بالذكاء الاصطناعي + كل الجلسات + كوتشينج جماعي + خطة شخصية + مراجعة فردية + شهادات.\n\n📌 الخلاصة: Recruit يخليك تذاكر، Empire يخليك توصل بسرعة وباهتمام شخصي 👑`,
  rv:`⚔️ Recruit ضد VIP\n\n🥉 Recruit (١٩٩ج/١٩$): تبدأ بمفردك.\n👑 VIP (٣٥٠٠ج/٢٤٩$): كل حاجة + ٤ جلسات خاصة فردية شهريًا + تصحيح غير محدود + واتساب مباشر + خطة مخصصة بالكامل.\n\n📌 الخلاصة: من «تذاكر لوحدك» لـ «مدرّب خاص ماشي معاك» — أقصى فرق ممكن 🔥`,
  be:`⚔️ Builder ضد Empire\n\n🥈 Builder (٣٩٩ج/٣٩$): تتكلم بثقة وسط المجموعة + تصحيح بالذكاء الاصطناعي.\n🥇 Empire (٧٩٩ج/٨٩$): كل ده + كوتشينج جماعي + خطة شخصية + مراجعة فردية + شهادات.\n\n📌 الخلاصة: Empire بيضيف اللمسة البشرية والخطة الشخصية = نتيجة أسرع 👑`,
  bv:`⚔️ Builder ضد VIP\n\n🥈 Builder (٣٩٩ج/٣٩$): تدريب جماعي + تصحيح بالذكاء الاصطناعي.\n👑 VIP (٣٥٠٠ج/٢٤٩$): كل ده + ٤ جلسات خاصة فردية + تصحيح غير محدود + واتساب مباشر + خطة مخصصة.\n\n📌 الخلاصة: Builder جماعي وقيمته عالية، VIP خصوصي وأقصى سرعة واهتمام 🔥`,
  ev:`⚔️ Empire ضد VIP\n\n🥇 Empire (٧٩٩ج/٨٩$): كوتشينج جماعي + خطة شخصية + مراجعة فردية.\n👑 VIP (٣٥٠٠ج/٢٤٩$): جلسات خاصة فردية بالكامل + تصحيح غير محدود + تواصل مباشر يومي.\n\n📌 الخلاصة: Empire اهتمام وسط مجموعة صغيرة، VIP كل التركيز عليك إنت لوحدك 👑`,
  all:`📊 مقارنة كاملة:\n🥉 Recruit (١٩٩ج) — البداية: نظام يومي + ملخصات.\n🥈 Builder (٣٩٩ج) — الأكثر اختيارًا: + تصحيح بالذكاء الاصطناعي + جلسات صوتية + مكتبة.\n🥇 Empire (٧٩٩ج) — أسرع: + كوتشينج + خطة شخصية + شهادات.\n👑 VIP (٣٥٠٠ج) — مدرّب خاص: + جلسات فردية + تصحيح غير محدود + واتساب.\n\nأغلب الناس بيبدأوا بـ Builder ⭐👑`
};
const REC = {
  budget:["recruit","ميزانيتك محدودة؟ باقة Recruit 🥉 بداية ممتازة، وتقدر ترفّع باقتك بعدين 👑"],
  speak:["builder","عايز تتكلم بثقة؟ باقة Builder ⭐ هي اختيارك المثالي 🔥"],
  goal:["empire","عندك هدف أو موعد محدد؟ باقة Empire 🥇 هتوصّلك أسرع 👑"],
  personal:["vip","عايز اهتمام شخصي كامل؟ باقة VIP 👑 مدرّبك الخاص 🔥"]
};
const FAQ = {
  guarantee:`🛡️ معاك ضمان استرجاع فلوسك خلال ٧ أيام — تجرّب وانت مطمّن تمامًا 👑`,
  beginner:`🧑‍🎓 بنبدأ من المستوى صفر تمامًا، والنظام معمول للمبتدئين بالظبط 🌟`,
  rec:`🎥 كل الجلسات بتتسجّل وترجعلها أي وقت (من باقة Builder وفوق) 👑`,
  time:`🕐 جلسات يومية بأكتر من معاد وكلها بتتسجّل. أول مجموعة بتبدأ السبت ٢٧ يونيو 👑`,
  online:`🌍 كله أونلاين بالكامل — مجتمع + جلسات صوتية مباشرة من أي مكان 👑`,
  price:`💸 أرخص من مدرّس خصوصي ومعاك نظام متكامل + ضمان ٧ أيام. ولو الميزانية محدودة، باقة Recruit بداية ممتازة 🥉👑`
};

async function touch(env, chatId, name, stage){
  if (!env || !env.KV) return;
  const key = "u:"+chatId;
  const u = (await env.KV.get(key,"json")) || {firstSeen:Date.now(), reminders:0, subscribed:false};
  if (name) u.name = name; u.lastSeen = Date.now();
  const rank = {engaged:1, considering:2, intent:3, paid_pending:4};
  if (stage && (!u.stage || (rank[stage]||0) >= (rank[u.stage]||0))) u.stage = stage;
  await env.KV.put(key, JSON.stringify(u));
}

async function requestPayment(env, custId, name, pkg){
  await tg("sendMessage", {chat_id: Number(custId), text:"تمام يا بطل 👑 ثواني وأجهّزلك طريقة الدفع 🙌"});
  await tg("sendMessage", {chat_id: ADMIN_CHAT_ID,
    text: `💰 طلب دفع من ${name} (id: ${custId})${pkg? " — باقة "+pkg : ""}:\n\n${MARK}${payText(pkg)}`,
    reply_markup: K([ [B("✅ موافقة وإرسال","ok:"+custId)], [B("✏️ تعديل","edit:"+custId)] ]) });
  await touch(env, custId, name, "intent");
}

async function onMessage(msg, env, ctx){
  const chatId = msg.chat.id;
  const fromId = String(msg.from.id);
  const text = msg.text || "";

  // ---- Admin ----
  if (fromId === String(ADMIN_CHAT_ID)){
    if (text === "/version"){ await tg("sendMessage",{chat_id:ADMIN_CHAT_ID,text:"✅ النسخة المنشورة: "+VERSION}); return; }
    if (text === "/kv"){ const a=env&&env.KV?(await env.KV.get("LEARNED","json"))||[]:null; await tg("sendMessage",{chat_id:ADMIN_CHAT_ID,text: a?("✅ KV متصلة. المتعلّم: "+a.length):"❌ KV مش متصلة."}); return; }
    if (text === "/list"){ if(env&&env.KV){const a=(await env.KV.get("LEARNED","json"))||[]; await tg("sendMessage",{chat_id:ADMIN_CHAT_ID,text:a.length?("📚 ("+a.length+"):\n"+a.slice(-10).map((e,i)=>(i+1)+". «"+e.q+"»").join("\n")):"📭 مفيش متعلّم."});} else await tg("sendMessage",{chat_id:ADMIN_CHAT_ID,text:"❌ KV مش متصل."}); return; }
    if (text === "/stats"){ if(env&&env.KV){const us=await env.KV.list({prefix:"u:"}); let s=0; for(const k of us.keys){const u=await env.KV.get(k.name,"json"); if(u&&u.subscribed)s++;} const inv=(await env.KV.get("INVOICES","json"))||[]; await tg("sendMessage",{chat_id:ADMIN_CHAT_ID,text:`📊 عملاء: ${us.keys.length} · مشتركين: ${s} · إيصالات: ${inv.length}`});} else await tg("sendMessage",{chat_id:ADMIN_CHAT_ID,text:"❌ KV مش متصل."}); return; }
    const rt = msg.reply_to_message;
    if (rt && rt.text){
      if (rt.text.indexOf(LEARNMARK) !== -1){
        const m = rt.text.match(/id:\s*(-?\d+)/), qm = rt.text.match(/«([^»]*)»/);
        if (m){ const cid=m[1], q=qm?qm[1]:""; await tg("sendMessage",{chat_id:Number(cid),text:text}); let learned=false,c=0;
          if(env&&env.KV&&q){const arr=(await env.KV.get("LEARNED","json"))||[]; arr.push({q:norm(q),reply:text}); await env.KV.put("LEARNED",JSON.stringify(arr)); learned=true; c=arr.length;}
          await tg("sendMessage",{chat_id:ADMIN_CHAT_ID,text:learned?("✅ اتبعت واتعلمت 🧠 (إجمالي: "+c+")"):"✅ اتبعت ردك."}); }
      } else if (rt.text.indexOf(EDITMARK) !== -1){
        const m = rt.text.match(/id:\s*(-?\d+)/); if(m){ await tg("sendMessage",{chat_id:Number(m[1]),text:text}); await tg("sendMessage",{chat_id:ADMIN_CHAT_ID,text:"✅ اتبعت ردك."}); }
      }
    }
    return;
  }

  const name = ((msg.from.first_name||"")+" "+(msg.from.last_name||"")).trim() || "عميل";

  // ---- payment proof (photo/document) ----
  if (msg.photo || msg.document){
    await tg("forwardMessage",{chat_id:ADMIN_CHAT_ID, from_chat_id:chatId, message_id:msg.message_id});
    await tg("sendMessage",{chat_id:ADMIN_CHAT_ID, text:`🧾 إثبات دفع من ${name} (id: ${chatId}). راجعه واضغط للتأكيد:`, reply_markup:K([[B("✅ تأكيد الاشتراك","sub:"+chatId)]])});
    if(env&&env.KV){const inv=(await env.KV.get("INVOICES","json"))||[]; inv.push({id:String(chatId),name,ts:Date.now()}); await env.KV.put("INVOICES",JSON.stringify(inv));}
    await touch(env, chatId, name, "paid_pending");
    await tg("sendMessage",{chat_id:chatId, text:"استلمنا الإيصال ✅ بنراجعه ونفعّل اشتراكك حالًا 👑"});
    return;
  }

  // ---- first time -> welcome + menu ----
  if (env && env.KV){
    const existing = await env.KV.get("u:"+chatId);
    if (!existing){ await touch(env, chatId, name, "engaged"); const v=view("main"); await tg("sendMessage",{chat_id:chatId, text:v.text, reply_markup:v.kb}); return; }
  }
  if (text === "/start"){ await touch(env,chatId,name,"engaged"); const v=view("main"); await tg("sendMessage",{chat_id:chatId,text:v.text,reply_markup:v.kb}); return; }

  bg(ctx, touch(env, chatId, name, "engaged"));
  let item = matchStatic(text);
  if (!item){ const l = await matchLearned(text, env); if (l) item = {reply:l}; }

  if (item && item.menu){ const v=view(item.menu); await tg("sendMessage",{chat_id:chatId, text:v.text, reply_markup:v.kb}); return; }
  if (item && item.personal){ // crypto / bank -> you send personally
    await tg("sendMessage",{chat_id:chatId, text:"تمام 🙌 ثواني وأبعتلك التفاصيل."});
    await tg("sendMessage",{chat_id:ADMIN_CHAT_ID, text:`🪙🏦 ${name} (id: ${chatId}) عايز يدفع كريبتو أو تحويل بنكي:\n«${text}»\n\nاضغط الزر وابعتله التفاصيل بنفسك:`, reply_markup:K([[B("✏️ رد على العميل","edit:"+chatId)]])});
    await touch(env, chatId, name, "intent");
    return;
  }
  if (item && item.sensitive){ // payment/offer -> approval
    await tg("sendMessage",{chat_id:chatId, text:"تمام 🙌 ثواني وبرد عليك بالتفاصيل."});
    await tg("sendMessage",{chat_id:ADMIN_CHAT_ID, text:`💰 استفسار دفع من ${name} (id: ${chatId}):\n«${text}»\n\n${MARK}${item.reply}`, reply_markup:K([[B("✅ موافقة وإرسال","ok:"+chatId)],[B("✏️ تعديل","edit:"+chatId)]])});
    return;
  }
  if (item && item.reply){
    await tg("sendMessage",{chat_id:chatId, text:item.reply, reply_markup:K([[B("📋 القائمة","m:main"), B("👑 اشترك","m:sub")]])});
    return;
  }
  // unknown -> show the customer the menu (so they're never stuck) + notify admin
  const vm = view("main");
  await tg("sendMessage",{chat_id:chatId, text:"اختار من القائمة وأنا أساعدك 👇\n(ولو سؤالك مختلف، استنى ثواني وهنرد عليك)", reply_markup:vm.kb});
  await tg("sendMessage",{chat_id:ADMIN_CHAT_ID, text:`🚩 سؤال جديد مالوش رد — من ${name} (id: ${chatId}):\n«${text}»\n\nاضغط الزر وردّ (وهحفظه للمرة الجاية):`, reply_markup:K([[B("🧠 رد + تعليم","learn:"+chatId)]])});
}

function matchStatic(text){
  const t = norm(text); if(!t) return null;
  for (const it of ANSWERS) for (const k of it.keys) if (t.indexOf(norm(k)) !== -1) return it;
  return null;
}
async function matchLearned(text, env){
  if(!env||!env.KV) return null; const t=norm(text); if(!t) return null;
  const arr=(await env.KV.get("LEARNED","json"))||[]; for(const e of arr) if(e.q && t.indexOf(e.q)!==-1) return e.reply; return null;
}

async function onCallback(cq, env){
  const data = cq.data || "";
  const presser = String(cq.from.id);
  const chatId = cq.message ? cq.message.chat.id : cq.from.id;

  if (presser === String(ADMIN_CHAT_ID) && /^(ok|edit|sub):/.test(data)){
    const [action, custId] = data.split(":");
    if (action === "ok"){
      const t = cq.message.text || ""; const idx = t.indexOf(MARK);
      const ans = idx !== -1 ? t.slice(idx + MARK.length) : "";
      if (ans){ await tg("sendMessage",{chat_id:Number(custId), text:ans}); await tg("editMessageText",{chat_id:cq.message.chat.id, message_id:cq.message.message_id, text:t+"\n\n✅ اتبعت للعميل."}); }
    } else if (action === "edit"){
      await tg("sendMessage",{chat_id:ADMIN_CHAT_ID, text:`${EDITMARK}${custId}):`, reply_markup:{force_reply:true}});
    } else if (action === "sub"){
      if(env&&env.KV){const u=(await env.KV.get("u:"+custId,"json"))||{}; u.subscribed=true; u.subAt=Date.now(); u.stage="subscribed"; await env.KV.put("u:"+custId,JSON.stringify(u));}
      await tg("sendMessage",{chat_id:Number(custId), text:SUB_WELCOME});
      await tg("editMessageText",{chat_id:cq.message.chat.id, message_id:cq.message.message_id, text:(cq.message.text||"")+"\n\n✅ تم تأكيد الاشتراك 👑"});
    }
    await tg("answerCallbackQuery",{callback_query_id:cq.id});
    return;
  }

  const name = ((cq.from.first_name||"")+" "+(cq.from.last_name||"")).trim() || "عميل";
  const [pre, arg] = data.split(":");
  async function show(v){ await tg("editMessageText",{chat_id:chatId, message_id:cq.message.message_id, text:v.text, reply_markup:v.kb}).catch(async()=>{ await tg("sendMessage",{chat_id:chatId, text:v.text, reply_markup:v.kb}); }); }

  if (pre === "m"){
    if (arg === "pay"){ await requestPayment(env, chatId, name, null); }
    else { const v=view(arg); if(v){ await show(v); await touch(env,chatId,name, arg==="sub"?"intent":(arg==="compare"||arg==="packages"||arg==="help"?"considering":"engaged")); } }
  }
  else if (pre === "p"){ await show({text:PKG[arg]||"—", kb:K([[B("👑 اشترك في دي","buy:"+(arg.charAt(0).toUpperCase()+arg.slice(1)))],[B("🆚 قارن","m:compare"), B("↩️ رجوع","m:packages")]])}); await touch(env,chatId,name,"considering"); }
  else if (pre === "cmp"){ await show({text:CMP[arg]||"—", kb:K([[B("👑 عايز أشترك","m:sub"), B("↩️ رجوع","m:compare")]])}); await touch(env,chatId,name,"considering"); }
  else if (pre === "rec"){ const r=REC[arg]; if(r){ await show({text:r[1]+"\n\n"+PKG[r[0]], kb:K([[B("👑 اشترك في دي","buy:"+(r[0].charAt(0).toUpperCase()+r[0].slice(1)))],[B("↩️ رجوع","m:help")]])}); await touch(env,chatId,name,"considering"); } }
  else if (pre === "faq"){ await show({text:FAQ[arg]||"—", kb:K([[B("👑 عايز أشترك","m:sub"), B("↩️ رجوع","m:faq")]])}); }
  else if (pre === "buy"){ await requestPayment(env, chatId, name, arg); }
  await tg("answerCallbackQuery",{callback_query_id:cq.id});
}
