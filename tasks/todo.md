# Admin dashboard

- [x] PIN file outside the app, seeded once as 654321, read on every unlock
- [x] Circular admin button under the guest text field, then a 6-digit pin prompt
- [x] Wines tab: edit, add, delete, in-stock toggle, save_all writes the one master
- [x] save_all rewrites the markdown list and the live search records from that master
- [x] Information tab: top color, price, keyword, producer, emailed wine
- [x] Guest searches are recorded so the information tab has real counts
- [x] Out-of-stock bottles stay on the list and drop out of recommendations
- [x] Verify unlock, edit, save, and both tabs

## Review

Verified in Edge at phone (390x844) and desktop (1280x800) against http://127.0.0.1:8000.

- Circular admin button sits under the text field. A wrong pin is rejected. The pin file unlocks the dashboard.
- Wines tab lists 274 bottles with the requested columns. save_all rewrote the master, the markdown list, and the live search list. A price edit was saved and then put back, and Opus One is $400 again.
- Information tab shows the five stats. Search and email counts are empty until guests use the app. Yangarra Estate is the producer with the most bottles (4).
- Out-of-stock bottles are kept on the master and skipped when recommending.
