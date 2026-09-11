/**
 * Now Showing — cross-device marks sync backend.
 *
 * SETUP (about 10 minutes, all clicking):
 *   1. Go to https://sheets.new  → name the spreadsheet e.g. "Now Showing marks".
 *   2. Extensions ▸ Apps Script. Delete the sample code, paste ALL of this file, Save.
 *   3. Deploy ▸ New deployment ▸ gear icon ▸ "Web app".
 *        - Description:      anything
 *        - Execute as:       Me
 *        - Who has access:   Anyone
 *      Deploy. Authorise when asked (it's your own script on your own sheet).
 *   4. Copy the Web app URL (ends in /exec).
 *   5. In the project folder, create a file  sync-url.txt  containing just that URL.
 *   6. Run  run-weekly.bat  (or python build.py + git push) so the site picks it up.
 *
 * The page then shows a "Sync" button. Turn it on, copy the link, open it on your
 * phone — both devices share the same marks. Anyone with the link can read/edit,
 * so treat it like a password.
 *
 * If you ever CHANGE this script, you must Deploy ▸ Manage deployments ▸ edit ▸
 * "New version" for the change to take effect. A brand-new deployment gives a new
 * URL (update sync-url.txt if so).
 *
 * NARROW THE PERMISSION PROMPT (optional but nice):
 *   The default prompt asks for access to ALL your spreadsheets, because that's
 *   the scope SpreadsheetApp defaults to. This script only touches its own sheet.
 *   To scope it down: ⚙ Project Settings ▸ tick "Show appsscript.json manifest",
 *   then in the editor replace appsscript.json with the copy in this repo
 *   (it pins  spreadsheets.currentonly  = "only this spreadsheet"). Save and
 *   re-deploy a new version; the re-auth prompt will then name just this sheet.
 */

const SHEET_NAME = 'marks';

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(['key', 'marks', 'updated']);
  }
  return sh;
}

function findRow_(sh, key) {
  const last = sh.getLastRow();
  if (last < 2) return 0;
  const keys = sh.getRange(2, 1, last - 1, 1).getValues();
  for (let i = 0; i < keys.length; i++) {
    if (String(keys[i][0]) === key) return i + 2;
  }
  return 0;
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function write_(key, marksObj) {
  const marks = (marksObj && typeof marksObj === 'object') ? marksObj : {};
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const sh = sheet_();
    const now = Date.now();
    const row = findRow_(sh, key);
    const payload = JSON.stringify(marks);
    if (row) sh.getRange(row, 2, 1, 2).setValues([[payload, now]]);
    else sh.appendRow([key, payload, now]);
    return json_({ ok: true, updated: now });
  } finally {
    lock.releaseLock();
  }
}

function read_(key) {
  const sh = sheet_();
  const row = findRow_(sh, key);
  if (!row) return json_({ marks: {}, updated: 0 });
  const rec = sh.getRange(row, 2, 1, 2).getValues()[0];
  let marks = {};
  try { marks = JSON.parse(rec[0] || '{}'); } catch (err) { marks = {}; }
  return json_({ marks: marks, updated: Number(rec[1]) || 0 });
}

// Both read and write go through doGet - browsers can't reliably POST to an
// Apps Script web app (the redirect drops the body), but GET always works.
//   read :  ?key=abc
//   write:  ?key=abc&marks=<url-encoded JSON>
function doGet(e) {
  const p = (e && e.parameter) || {};
  const key = String(p.key || '').trim();
  if (!key) return json_({ error: 'no key' });

  if (typeof p.marks === 'string') {
    let marks;
    try { marks = JSON.parse(p.marks); } catch (err) { return json_({ error: 'bad marks json' }); }
    return write_(key, marks);
  }
  return read_(key);
}

function doPost(e) {
  let body;
  try { body = JSON.parse(e.postData.contents); }
  catch (err) { return json_({ error: 'bad json' }); }
  const key = String(body.key || '').trim();
  if (!key) return json_({ error: 'no key' });
  return write_(key, body.marks);
}
