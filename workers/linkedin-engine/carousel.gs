/**
 * LinkedIn Content Engine — Carousel generator (Google Apps Script) — Phase 3
 * ---------------------------------------------------------------------------
 * Free, unlimited, on-brand carousels. The Cloudflare Worker POSTs slide copy here;
 * this script builds a branded Google Slides deck, exports it as a PDF, and returns a
 * shareable PDF link. You upload that PDF to LinkedIn as a "document" post (= a carousel).
 *
 * SETUP (one time, ~3 minutes):
 *   1. Go to https://script.google.com  ->  New project. Paste this whole file.
 *   2. Project Settings -> Script properties -> add property:
 *         name:  TOKEN          value:  <any long random string>
 *      Put the SAME string in the Worker's CAROUSEL_TOKEN (env var or fallback const).
 *   3. Deploy -> New deployment -> type "Web app".
 *         Execute as: Me      Who has access: Anyone
 *      Copy the Web app URL into the Worker's CAROUSEL_WEBAPP_URL.
 *   4. Done. Tap "🎠 Carousel" in Telegram.
 *
 * Brand: matte black slides, gold (#D4AF37) titles. Default 4:3 (works fine on LinkedIn).
 */

var BG_COLOR    = '#0A0A0A'; // matte black
var GOLD_COLOR  = '#D4AF37'; // gold
var TEXT_COLOR  = '#F5F5F5'; // near-white
var FOOTER_SIZE = 10;

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents || '{}');
    var expected = PropertiesService.getScriptProperties().getProperty('TOKEN');
    if (!expected || body.token !== expected) return json_({ error: 'unauthorized' });

    var slides = body.slides || [];
    if (!slides.length) return json_({ error: 'no slides provided' });

    var pdfUrl = buildCarousel_(body.title || 'Carousel', slides, body.handle || '');
    return json_({ pdf_url: pdfUrl });
  } catch (err) {
    return json_({ error: String(err) });
  }
}

function doGet() {
  return json_({ ok: true, service: 'linkedin-carousel', usage: 'POST {token, title, slides:[{title,body}], handle}' });
}

function buildCarousel_(title, slides, handle) {
  var pres = SlidesApp.create('LI Carousel ' + new Date().toISOString());
  var presId = pres.getId();

  // Use the auto-created first slide as the cover, then add the rest.
  var deck = pres.getSlides();
  styleSlide_(deck[0], slides[0], handle, true);
  for (var i = 1; i < slides.length; i++) {
    var s = pres.appendSlide(SlidesApp.PredefinedLayout.BLANK);
    styleSlide_(s, slides[i], handle, false);
  }
  pres.saveAndClose();

  // Export as PDF and share it.
  var slideFile = DriveApp.getFileById(presId);
  var pdfBlob = slideFile.getAs('application/pdf').setName((title || 'carousel') + '.pdf');
  var pdfFile = DriveApp.createFile(pdfBlob);
  pdfFile.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

  // Clean up the editable Slides file (keep only the PDF).
  slideFile.setTrashed(true);

  return pdfFile.getUrl();
}

function styleSlide_(slide, content, handle, isCover) {
  // Background
  slide.getBackground().setSolidFill(BG_COLOR);

  var W = slide.getParent ? 720 : 720; // points (10in * 72) for default 4:3
  var pageW = SlidesApp.getActivePresentation ? 720 : 720;
  var left = 50, width = 620;

  // Title
  var titleText = (content && content.title) || '';
  if (titleText) {
    var tBox = slide.insertTextBox(titleText, left, isCover ? 230 : 80, width, isCover ? 180 : 140);
    var tr = tBox.getText();
    tr.getTextStyle().setForegroundColor(GOLD_COLOR).setBold(true)
      .setFontSize(isCover ? 40 : 30).setFontFamily('Arial');
    tBox.getText().getParagraphs().forEach(function (p) {
      p.getRange().getParagraphStyle().setParagraphAlignment(SlidesApp.ParagraphAlignment.START);
    });
  }

  // Body
  var bodyText = (content && content.body) || '';
  if (bodyText && !isCover) {
    var bBox = slide.insertTextBox(bodyText, left, 240, width, 180);
    bBox.getText().getTextStyle().setForegroundColor(TEXT_COLOR).setFontSize(20).setFontFamily('Arial');
  }

  // Footer handle
  if (handle) {
    var fBox = slide.insertTextBox(handle, left, 470, width, 30);
    fBox.getText().getTextStyle().setForegroundColor(GOLD_COLOR).setFontSize(FOOTER_SIZE).setFontFamily('Arial');
  }

  // "swipe ->" hint on the cover
  if (isCover) {
    var hint = slide.insertTextBox('swipe →', left, 430, width, 30);
    hint.getText().getTextStyle().setForegroundColor(TEXT_COLOR).setFontSize(14).setItalic(true);
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
