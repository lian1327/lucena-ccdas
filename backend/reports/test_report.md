# CCADSS automated test report

Run on November 02, 2026 18:23 · Django test runner · 164 tests in 36.883 s · **134 passed, 12 not passed**

## By area

| Area | Tests | Passed |
|---|---|---|
| Modules 6–7 – Analytics & Decision Support | 16 | 16 |
| Module 3 – AI Classification | 4 | 4 |
| Module 2 – ARTA deadlines | 6 | 6 |
| Module 4 – Duplicates & recurrence | 9 | 9 |
| Module 2 – Proof of work | 12 | 12 |
| Module 2 – Field view (check-in, blockers, live photos) | 14 | 14 |
| Module 5 – GIS (purok tagging) | 7 | 7 |
| Module 1 – Notifications (SMS/email/alerts) | 28 | 17 |
| Module 4 – Priority Scoring | 4 | 4 |
| Module 1 – Citizen Reporting Portal | 4 | 4 |
| Security – Role-based access | 6 | 6 |
| Deployment – health, site mode, scheduler | 6 | 6 |
| Module 1 – Report screening (false reports) | 17 | 16 |
| Module 2 – Case Management | 13 | 13 |

## Test cases

| ID | Area | Test | Result |
|---|---|---|---|
| TC-001 | Modules 6–7 – Analytics & Decision Support | Accomplished and fair 30 day rate | Pass |
| TC-002 | Modules 6–7 – Analytics & Decision Support | Open case not yet due is neither late nor on time | Pass |
| TC-003 | Modules 6–7 – Analytics & Decision Support | Young cohort has no 30 day rate yet | Pass |
| TC-004 | Modules 6–7 – Analytics & Decision Support | Backtest is mean absolute percentage error | Pass |
| TC-005 | Modules 6–7 – Analytics & Decision Support | Holt follows a trend | Pass |
| TC-006 | Modules 6–7 – Analytics & Decision Support | Naive and mean3 | Pass |
| TC-007 | Modules 6–7 – Analytics & Decision Support | Seasonal needs enough history | Pass |
| TC-008 | Modules 6–7 – Analytics & Decision Support | Seasonal wins on a yearly pattern | Pass |
| TC-009 | Modules 6–7 – Analytics & Decision Support | Selects the method with lowest error | Pass |
| TC-010 | Modules 6–7 – Analytics & Decision Support | Short series falls back to naive | Pass |
| TC-011 | Modules 6–7 – Analytics & Decision Support | Index matches hand calculation | Pass |
| TC-012 | Modules 6–7 – Analytics & Decision Support | Low on time needs attention | Pass |
| TC-013 | Modules 6–7 – Analytics & Decision Support | On time counts against the case deadline | Pass |
| TC-014 | Modules 6–7 – Analytics & Decision Support | Perfect office scores 100 and good | Pass |
| TC-015 | Modules 6–7 – Analytics & Decision Support | Tiny sample is not graded | Pass |
| TC-016 | Modules 6–7 – Analytics & Decision Support | Weights sum to one | Pass |
| TC-017 | Module 3 – AI Classification | Links and numbers removed | Pass |
| TC-018 | Module 3 – AI Classification | Texting style is normalised | Pass |
| TC-019 | Module 3 – AI Classification | Trained pipeline generalises to hand written reports | Pass |
| TC-020 | Module 3 – AI Classification | Without a model reports are still accepted | Pass |
| TC-021 | Module 2 – ARTA deadlines | Routed case gets acceptance and resolution deadlines | Pass |
| TC-022 | Module 2 – ARTA deadlines | Service classes match arta | Pass |
| TC-023 | Module 2 – ARTA deadlines | Seven working days spans a week and more | Pass |
| TC-024 | Module 2 – ARTA deadlines | Skips holiday | Pass |
| TC-025 | Module 2 – ARTA deadlines | Skips weekend | Pass |
| TC-026 | Module 2 – ARTA deadlines | Three working days from monday | Pass |
| TC-027 | Module 4 – Duplicates & recurrence | Closed case is not a master | Pass |
| TC-028 | Module 4 – Duplicates & recurrence | Duplicates follow the master status | Pass |
| TC-029 | Module 4 – Duplicates & recurrence | Far away does not link | Pass |
| TC-030 | Module 4 – Duplicates & recurrence | Link and unlink by staff | Pass |
| TC-031 | Module 4 – Duplicates & recurrence | Older than 14 days does not link | Pass |
| TC-032 | Module 4 – Duplicates & recurrence | Other category does not link | Pass |
| TC-033 | Module 4 – Duplicates & recurrence | Same category within 100m links | Pass |
| TC-034 | Module 4 – Duplicates & recurrence | Fix older than 30 days is not a recurrence | Pass |
| TC-035 | Module 4 – Duplicates & recurrence | Problem back after fix is flagged | Pass |
| TC-036 | Module 2 – Proof of work | Complete requires before and after photos | Pass |
| TC-037 | Module 2 – Proof of work | Red flag needs a written reason | Pass |
| TC-038 | Module 2 – Proof of work | Report records crew and is approved | Pass |
| TC-039 | Module 2 – Proof of work | After identical to before is red | Pass |
| TC-040 | Module 2 – Proof of work | After photo taken before routing is red | Pass |
| TC-041 | Module 2 – Proof of work | No gps is amber not red | Pass |
| TC-042 | Module 2 – Proof of work | Old photo is stale | Pass |
| TC-043 | Module 2 – Proof of work | Photo at site is clean | Pass |
| TC-044 | Module 2 – Proof of work | Photo far from site is red | Pass |
| TC-045 | Module 2 – Proof of work | Photo reused from another case is red | Pass |
| TC-046 | Module 2 – Proof of work | Missing hash is maximally different | Pass |
| TC-047 | Module 2 – Proof of work | Same image same hash and different image differs | Pass |
| TC-048 | Module 2 – Field view (check-in, blockers, live photos) | Check in at site counts as first response | Pass |
| TC-049 | Module 2 – Field view (check-in, blockers, live photos) | Check in far from pin is flagged not refused | Pass |
| TC-050 | Module 2 – Field view (check-in, blockers, live photos) | Implausible times are refused | Pass |
| TC-051 | Module 2 – Field view (check-in, blockers, live photos) | Offline check in keeps phone time | Pass |
| TC-052 | Module 2 – Field view (check-in, blockers, live photos) | Second visit does not move first response | Pass |
| TC-053 | Module 2 – Field view (check-in, blockers, live photos) | Blocker alerts office leads and clears on completion | Pass |
| TC-054 | Module 2 – Field view (check-in, blockers, live photos) | Wrong office also tells pacd | Pass |
| TC-055 | Module 2 – Field view (check-in, blockers, live photos) | Assigned to me comes first and payload has location | Pass |
| TC-056 | Module 2 – Field view (check-in, blockers, live photos) | Assigned worker and division mate see the job | Pass |
| TC-057 | Module 2 – Field view (check-in, blockers, live photos) | Job leaves the list once work is reported | Pass |
| TC-058 | Module 2 – Field view (check-in, blockers, live photos) | Other office and desk do not | Pass |
| TC-059 | Module 2 – Field view (check-in, blockers, live photos) | Live claim without location gets no good flag | Pass |
| TC-060 | Module 2 – Field view (check-in, blockers, live photos) | Live photo at site gets good flag | Pass |
| TC-061 | Module 2 – Field view (check-in, blockers, live photos) | Live photo far away stays red | Pass |
| TC-062 | Module 5 – GIS (purok tagging) | Contains | Pass |
| TC-063 | Module 5 – GIS (purok tagging) | Distance outside is positive | Pass |
| TC-064 | Module 5 – GIS (purok tagging) | Chosen barangay wins on the boundary | Pass |
| TC-065 | Module 5 – GIS (purok tagging) | Far point has no purok | Pass |
| TC-066 | Module 5 – GIS (purok tagging) | Point inside | Pass |
| TC-067 | Module 5 – GIS (purok tagging) | Report is tagged from the pin | Pass |
| TC-068 | Module 5 – GIS (purok tagging) | Snaps within 30m | Pass |
| TC-069 | Module 1 – Notifications (SMS/email/alerts) | Closing after citizen confirms sends nothing more | Error |
| TC-070 | Module 1 – Notifications (SMS/email/alerts) | Each duplicate reporter gets their own update | Error |
| TC-071 | Module 1 – Notifications (SMS/email/alerts) | Extension notifies with new date | Error |
| TC-072 | Module 1 – Notifications (SMS/email/alerts) | Muted sends nothing | Pass |
| TC-073 | Module 1 – Notifications (SMS/email/alerts) | No sms for anonymous opted out or synthetic | Pass |
| TC-074 | Module 1 – Notifications (SMS/email/alerts) | One message per milestone through the lifecycle | Error |
| TC-075 | Module 1 – Notifications (SMS/email/alerts) | Received sms and email on submit | Error |
| TC-076 | Module 1 – Notifications (SMS/email/alerts) | Rejection explains why | Error |
| TC-077 | Module 1 – Notifications (SMS/email/alerts) | Same update is never sent twice | Error |
| TC-078 | Module 1 – Notifications (SMS/email/alerts) | Log is masked and role limited | Error |
| TC-079 | Module 1 – Notifications (SMS/email/alerts) | Night report waits then worker sends | Error |
| TC-080 | Module 1 – Notifications (SMS/email/alerts) | Window | Pass |
| TC-081 | Module 1 – Notifications (SMS/email/alerts) | Failed sms is retried with backoff and capped | Pass |
| TC-082 | Module 1 – Notifications (SMS/email/alerts) | Purge blanks old recipients | Error |
| TC-083 | Module 1 – Notifications (SMS/email/alerts) | Reminder after three days once | Error |
| TC-084 | Module 1 – Notifications (SMS/email/alerts) | Missing key never calls out | Pass |
| TC-085 | Module 1 – Notifications (SMS/email/alerts) | Network error is a failure | Pass |
| TC-086 | Module 1 – Notifications (SMS/email/alerts) | Success reply is parsed | Pass |
| TC-087 | Module 1 – Notifications (SMS/email/alerts) | Validation error is a failure | Pass |
| TC-088 | Module 1 – Notifications (SMS/email/alerts) | Every event fits one sms | Pass |
| TC-089 | Module 1 – Notifications (SMS/email/alerts) | Gsm conversion keeps filipino letters | Pass |
| TC-090 | Module 1 – Notifications (SMS/email/alerts) | Normalize ph numbers | Pass |
| TC-091 | Module 1 – Notifications (SMS/email/alerts) | Segments | Pass |
| TC-092 | Module 1 – Notifications (SMS/email/alerts) | Assignment and validation alerts | Pass |
| TC-093 | Module 1 – Notifications (SMS/email/alerts) | Bell api counts and marks read | Pass |
| TC-094 | Module 1 – Notifications (SMS/email/alerts) | Citizen dispute alerts the crew | Pass |
| TC-095 | Module 1 – Notifications (SMS/email/alerts) | Danger report alerts pacd urgently | Pass |
| TC-096 | Module 1 – Notifications (SMS/email/alerts) | New case alerts the office not the router | Pass |
| TC-097 | Module 4 – Priority Scoring | Formula matches hand calculation | Pass |
| TC-098 | Module 4 – Priority Scoring | More people reporting raises priority | Pass |
| TC-099 | Module 4 – Priority Scoring | Same person reporting twice counts once | Pass |
| TC-100 | Module 4 – Priority Scoring | Score is bounded | Pass |
| TC-101 | Module 1 – Citizen Reporting Portal | Anonymous report drops identity | Pass |
| TC-102 | Module 1 – Citizen Reporting Portal | Submit returns reference | Pass |
| TC-103 | Module 1 – Citizen Reporting Portal | Recent fixes show no reference numbers | Pass |
| TC-104 | Module 1 – Citizen Reporting Portal | Tracking page never shows personal data | Pass |
| TC-105 | Security – Role-based access | Pacd routes through api | Pass |
| TC-106 | Security – Role-based access | Field staff cannot route | Pass |
| TC-107 | Security – Role-based access | Field staff sees nothing until accepted | Pass |
| TC-108 | Security – Role-based access | Mayor is read only | Pass |
| TC-109 | Security – Role-based access | Office sees only its own categories | Pass |
| TC-110 | Security – Role-based access | Pacd and executives see everything | Pass |
| TC-111 | Deployment – health, site mode, scheduler | Sample data hidden from public numbers | Pass |
| TC-112 | Deployment – health, site mode, scheduler | Sample data never alerts staff | Pass |
| TC-113 | Deployment – health, site mode, scheduler | Sample data shown and flagged | Pass |
| TC-114 | Deployment – health, site mode, scheduler | Health | Pass |
| TC-115 | Deployment – health, site mode, scheduler | Site mode prototype | Pass |
| TC-116 | Deployment – health, site mode, scheduler | Unknown mode falls back to prototype | Pass |
| TC-117 | Module 1 – Report screening (false reports) | Many anonymous duplicates count as two | Pass |
| TC-118 | Module 1 – Report screening (false reports) | Camera gps far from pin | Pass |
| TC-119 | Module 1 – Report screening (false reports) | Camera gps near pin is clean | Pass |
| TC-120 | Module 1 – Report screening (false reports) | Live capture at the site is a good sign | Pass |
| TC-121 | Module 1 – Report screening (false reports) | Old photo date | Pass |
| TC-122 | Module 1 – Report screening (false reports) | Phone location far away is not called far | Pass |
| TC-123 | Module 1 – Report screening (false reports) | Plain photo without camera data is not flagged | Pass |
| TC-124 | Module 1 – Report screening (false reports) | Same photo for a different place is red | Pass |
| TC-125 | Module 1 – Report screening (false reports) | Same photo shared by neighbours is only info | Pass |
| TC-126 | Module 1 – Report screening (false reports) | Flags reach the staff api | Pass |
| TC-127 | Module 1 – Report screening (false reports) | Photo meta travels with the upload and report stays submitted | Pass |
| TC-128 | Module 1 – Report screening (false reports) | Anonymous reports have no key | Pass |
| TC-129 | Module 1 – Report screening (false reports) | Burst from one network | Pass |
| TC-130 | Module 1 – Report screening (false reports) | Three unfounded then flagged | Pass |
| TC-131 | Module 1 – Report screening (false reports) | Needs a note and tells the reporter | Error |
| TC-132 | Module 1 – Report screening (false reports) | Only the original counts against the reporter | Pass |
| TC-133 | Module 1 – Report screening (false reports) | Report card | Pass |
| TC-134 | Module 2 – Case Management | Answer only once | Pass |
| TC-135 | Module 2 – Case Management | Duplicate reporter can reopen the shared case | Pass |
| TC-136 | Module 2 – Case Management | Not fixed reopens and clears validation | Pass |
| TC-137 | Module 2 – Case Management | Window closes after 30 days | Pass |
| TC-138 | Module 2 – Case Management | Overdue case escalates one level at a time | Pass |
| TC-139 | Module 2 – Case Management | Extension after deadline lapsed is refused | Pass |
| TC-140 | Module 2 – Case Management | One extension only and within limit | Pass |
| TC-141 | Module 2 – Case Management | Changing priority needs a reason | Pass |
| TC-142 | Module 2 – Case Management | Full path submitted to closed | Pass |
| TC-143 | Module 2 – Case Management | Internal steps are hidden from the public timeline | Pass |
| TC-144 | Module 2 – Case Management | Invalid transition is refused | Pass |
| TC-145 | Module 2 – Case Management | Screening questions must be answered | Pass |
| TC-146 | Module 2 – Case Management | Wrong office returns to pacd | Pass |

Scope note: automated tests verify functional correctness (ISO/IEC 25010 functional suitability, security). Usability (SUS), UAT and performance are evaluated separately with users.