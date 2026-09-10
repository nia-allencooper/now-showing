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

function doGet(e) {
  const key = ((e && e.parameter && e.parameter.key) || '').trim();
  if (!key) return json_({ error: 'no key' });
  const sh = sheet_();
  const row = findRow_(sh, key);
  if (!row) return json_({ marks: {}, updated: 0 });
  const rec = sh.getRange(row, 2, 1, 2).getValues()[0];
  let marks = {};
  try { marks = JSON.parse(rec[0] || '{}'); } catch (err) { marks = {}; }
  return json_({ marks: marks, updated: Number(rec[1]) || 0 });
}

function doPost(e) {
  let body;
  try { body = JSON.parse(e.postData.contents); }
  catch (err) { return json_({ error: 'bad json' }); }

  const key = String(body.key || '').trim();
  if (!key) return json_({ error: 'no key' });
  const marks = (body.marks && typeof body.marks === 'object') ? body.marks : {};

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
