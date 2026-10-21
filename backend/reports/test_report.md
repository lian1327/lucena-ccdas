# CCADSS automated test report

Run on October 20, 2026 21:22 · Django test runner · 122 tests in 15.949 s · **122 passed, 0 not passed**

## By area

| Area | Tests | Passed |
|---|---|---|
| Modules 6–7 – Analytics & Decision Support | 17 | 17 |
| Module 3 – AI Classification | 4 | 4 |
| Module 2 – ARTA deadlines | 6 | 6 |
| Module 4 – Duplicates & recurrence | 9 | 9 |
| Module 2 – Proof of work | 12 | 12 |
| Module 5 – GIS (purok tagging) | 7 | 7 |
| Module 1 – Notifications (SMS/email/alerts) | 29 | 29 |
| Module 4 – Priority Scoring | 4 | 4 |
| Module 1 – Citizen Reporting Portal | 10 | 10 |
| Security – Role-based access | 11 | 11 |
| Module 2 – Case Management | 13 | 13 |

## Test cases

| ID | Area | Test | Result |
|---|---|---|---|
| TC-001 | Modules 6–7 – Analytics & Decision Support | Executive endpoints for executives only | Pass |
| TC-002 | Modules 6–7 – Analytics & Decision Support | Accomplished and fair 30 day rate | Pass |
| TC-003 | Modules 6–7 – Analytics & Decision Support | Open case not yet due is neither late nor on time | Pass |
| TC-004 | Modules 6–7 – Analytics & Decision Support | Young cohort has no 30 day rate yet | Pass |
| TC-005 | Modules 6–7 – Analytics & Decision Support | Backtest is mean absolute percentage error | Pass |
| TC-006 | Modules 6–7 – Analytics & Decision Support | Holt follows a trend | Pass |
| TC-007 | Modules 6–7 – Analytics & Decision Support | Naive and mean3 | Pass |
| TC-008 | Modules 6–7 – Analytics & Decision Support | Seasonal needs enough history | Pass |
| TC-009 | Modules 6–7 – Analytics & Decision Support | Seasonal wins on a yearly pattern | Pass |
| TC-010 | Modules 6–7 – Analytics & Decision Support | Selects the method with lowest error | Pass |
| TC-011 | Modules 6–7 – Analytics & Decision Support | Short series falls back to naive | Pass |
| TC-012 | Modules 6–7 – Analytics & Decision Support | Index matches hand calculation | Pass |
| TC-013 | Modules 6–7 – Analytics & Decision Support | Low on time needs attention | Pass |
| TC-014 | Modules 6–7 – Analytics & Decision Support | On time counts against the case deadline | Pass |
| TC-015 | Modules 6–7 – Analytics & Decision Support | Perfect office scores 100 and good | Pass |
| TC-016 | Modules 6–7 – Analytics & Decision Support | Tiny sample is not graded | Pass |
| TC-017 | Modules 6–7 – Analytics & Decision Support | Weights sum to one | Pass |
| TC-018 | Module 3 – AI Classification | Links and numbers removed | Pass |
| TC-019 | Module 3 – AI Classification | Texting style is normalised | Pass |
| TC-020 | Module 3 – AI Classification | Trained pipeline generalises to hand written reports | Pass |
| TC-021 | Module 3 – AI Classification | Without a model reports are still accepted | Pass |
| TC-022 | Module 2 – ARTA deadlines | Routed case gets acceptance and resolution deadlines | Pass |
| TC-023 | Module 2 – ARTA deadlines | Service classes match arta | Pass |
| TC-024 | Module 2 – ARTA deadlines | Seven working days spans a week and more | Pass |
| TC-025 | Module 2 – ARTA deadlines | Skips holiday | Pass |
| TC-026 | Module 2 – ARTA deadlines | Skips weekend | Pass |
| TC-027 | Module 2 – ARTA deadlines | Three working days from monday | Pass |
| TC-028 | Module 4 – Duplicates & recurrence | Closed case is not a master | Pass |
| TC-029 | Module 4 – Duplicates & recurrence | Duplicates follow the master status | Pass |
| TC-030 | Module 4 – Duplicates & recurrence | Far away does not link | Pass |
| TC-031 | Module 4 – Duplicates & recurrence | Link and unlink by staff | Pass |
| TC-032 | Module 4 – Duplicates & recurrence | Older than 14 days does not link | Pass |
| TC-033 | Module 4 – Duplicates & recurrence | Other category does not link | Pass |
| TC-034 | Module 4 – Duplicates & recurrence | Same category within 100m links | Pass |
| TC-035 | Module 4 – Duplicates & recurrence | Fix older than 30 days is not a recurrence | Pass |
| TC-036 | Module 4 – Duplicates & recurrence | Problem back after fix is flagged | Pass |
| TC-037 | Module 2 – Proof of work | Complete requires before and after photos | Pass |
| TC-038 | Module 2 – Proof of work | Red flag needs a written reason | Pass |
| TC-039 | Module 2 – Proof of work | Report records crew and is approved | Pass |
| TC-040 | Module 2 – Proof of work | After identical to before is red | Pass |
| TC-041 | Module 2 – Proof of work | After photo taken before routing is red | Pass |
| TC-042 | Module 2 – Proof of work | No gps is amber not red | Pass |
| TC-043 | Module 2 – Proof of work | Old photo is stale | Pass |
| TC-044 | Module 2 – Proof of work | Photo at site is clean | Pass |
| TC-045 | Module 2 – Proof of work | Photo far from site is red | Pass |
| TC-046 | Module 2 – Proof of work | Photo reused from another case is red | Pass |
| TC-047 | Module 2 – Proof of work | Missing hash is maximally different | Pass |
| TC-048 | Module 2 – Proof of work | Same image same hash and different image differs | Pass |
| TC-049 | Module 5 – GIS (purok tagging) | Contains | Pass |
| TC-050 | Module 5 – GIS (purok tagging) | Distance outside is positive | Pass |
| TC-051 | Module 5 – GIS (purok tagging) | Chosen barangay wins on the boundary | Pass |
| TC-052 | Module 5 – GIS (purok tagging) | Far point has no purok | Pass |
| TC-053 | Module 5 – GIS (purok tagging) | Point inside | Pass |
| TC-054 | Module 5 – GIS (purok tagging) | Report is tagged from the pin | Pass |
| TC-055 | Module 5 – GIS (purok tagging) | Snaps within 30m | Pass |
| TC-056 | Module 1 – Notifications (SMS/email/alerts) | Closing after citizen confirms sends nothing more | Pass |
| TC-057 | Module 1 – Notifications (SMS/email/alerts) | Each duplicate reporter gets their own update | Pass |
| TC-058 | Module 1 – Notifications (SMS/email/alerts) | Extension notifies with new date | Pass |
| TC-059 | Module 1 – Notifications (SMS/email/alerts) | Muted sends nothing | Pass |
| TC-060 | Module 1 – Notifications (SMS/email/alerts) | No sms for anonymous opted out or synthetic | Pass |
| TC-061 | Module 1 – Notifications (SMS/email/alerts) | One message per milestone through the lifecycle | Pass |
| TC-062 | Module 1 – Notifications (SMS/email/alerts) | Received sms and email on submit | Pass |
| TC-063 | Module 1 – Notifications (SMS/email/alerts) | Rejection explains why | Pass |
| TC-064 | Module 1 – Notifications (SMS/email/alerts) | Same update is never sent twice | Pass |
| TC-065 | Module 1 – Notifications (SMS/email/alerts) | Log is masked and role limited | Pass |
| TC-066 | Module 1 – Notifications (SMS/email/alerts) | Night report waits then worker sends | Pass |
| TC-067 | Module 1 – Notifications (SMS/email/alerts) | Window | Pass |
| TC-068 | Module 1 – Notifications (SMS/email/alerts) | Failed sms is retried with backoff and capped | Pass |
| TC-069 | Module 1 – Notifications (SMS/email/alerts) | Purge blanks old recipients | Pass |
| TC-070 | Module 1 – Notifications (SMS/email/alerts) | Reminder after three days once | Pass |
| TC-071 | Module 1 – Notifications (SMS/email/alerts) | Missing key never calls out | Pass |
| TC-072 | Module 1 – Notifications (SMS/email/alerts) | Network error is a failure | Pass |
| TC-073 | Module 1 – Notifications (SMS/email/alerts) | Success reply is parsed | Pass |
| TC-074 | Module 1 – Notifications (SMS/email/alerts) | Validation error is a failure | Pass |
| TC-075 | Module 1 – Notifications (SMS/email/alerts) | Every event fits one sms | Pass |
| TC-076 | Module 1 – Notifications (SMS/email/alerts) | Gsm conversion keeps filipino letters | Pass |
| TC-077 | Module 1 – Notifications (SMS/email/alerts) | Normalize ph numbers | Pass |
| TC-078 | Module 1 – Notifications (SMS/email/alerts) | Segments | Pass |
| TC-079 | Module 1 – Notifications (SMS/email/alerts) | Assignment and validation alerts | Pass |
| TC-080 | Module 1 – Notifications (SMS/email/alerts) | Bell api counts and marks read | Pass |
| TC-081 | Module 1 – Notifications (SMS/email/alerts) | Citizen dispute alerts the crew | Pass |
| TC-082 | Module 1 – Notifications (SMS/email/alerts) | Danger report alerts pacd urgently | Pass |
| TC-083 | Module 1 – Notifications (SMS/email/alerts) | New case alerts the office not the router | Pass |
| TC-084 | Module 1 – Notifications (SMS/email/alerts) | People only see their own alerts | Pass |
| TC-085 | Module 4 – Priority Scoring | Formula matches hand calculation | Pass |
| TC-086 | Module 4 – Priority Scoring | More people reporting raises priority | Pass |
| TC-087 | Module 4 – Priority Scoring | Same person reporting twice counts once | Pass |
| TC-088 | Module 4 – Priority Scoring | Score is bounded | Pass |
| TC-089 | Module 1 – Citizen Reporting Portal | Anonymous report drops identity | Pass |
| TC-090 | Module 1 – Citizen Reporting Portal | Consent is required | Pass |
| TC-091 | Module 1 – Citizen Reporting Portal | Invalid mobile is rejected | Pass |
| TC-092 | Module 1 – Citizen Reporting Portal | Pin outside service area is rejected | Pass |
| TC-093 | Module 1 – Citizen Reporting Portal | Submit returns reference | Pass |
| TC-094 | Module 1 – Citizen Reporting Portal | Confirm needs last four digits | Pass |
| TC-095 | Module 1 – Citizen Reporting Portal | Recent fixes show no reference numbers | Pass |
| TC-096 | Module 1 – Citizen Reporting Portal | Sms opt out | Pass |
| TC-097 | Module 1 – Citizen Reporting Portal | Tracking page never shows personal data | Pass |
| TC-098 | Module 1 – Citizen Reporting Portal | Unknown reference is 404 | Pass |
| TC-099 | Security – Role-based access | Anonymous cannot use staff api | Pass |
| TC-100 | Security – Role-based access | Citizen account is forbidden | Pass |
| TC-101 | Security – Role-based access | Login returns tokens | Pass |
| TC-102 | Security – Role-based access | Mayor cannot route through api | Pass |
| TC-103 | Security – Role-based access | Out of scope case is 404 | Pass |
| TC-104 | Security – Role-based access | Pacd routes through api | Pass |
| TC-105 | Security – Role-based access | Field staff cannot route | Pass |
| TC-106 | Security – Role-based access | Field staff sees nothing until accepted | Pass |
| TC-107 | Security – Role-based access | Mayor is read only | Pass |
| TC-108 | Security – Role-based access | Office sees only its own categories | Pass |
| TC-109 | Security – Role-based access | Pacd and executives see everything | Pass |
| TC-110 | Module 2 – Case Management | Answer only once | Pass |
| TC-111 | Module 2 – Case Management | Duplicate reporter can reopen the shared case | Pass |
| TC-112 | Module 2 – Case Management | Not fixed reopens and clears validation | Pass |
| TC-113 | Module 2 – Case Management | Window closes after 30 days | Pass |
| TC-114 | Module 2 – Case Management | Overdue case escalates one level at a time | Pass |
| TC-115 | Module 2 – Case Management | Extension after deadline lapsed is refused | Pass |
| TC-116 | Module 2 – Case Management | One extension only and within limit | Pass |
| TC-117 | Module 2 – Case Management | Changing priority needs a reason | Pass |
| TC-118 | Module 2 – Case Management | Full path submitted to closed | Pass |
| TC-119 | Module 2 – Case Management | Internal steps are hidden from the public timeline | Pass |
| TC-120 | Module 2 – Case Management | Invalid transition is refused | Pass |
| TC-121 | Module 2 – Case Management | Screening questions must be answered | Pass |
| TC-122 | Module 2 – Case Management | Wrong office returns to pacd | Pass |

## Code coverage (statement)

```
Name                                                           Stmts   Miss  Cover
----------------------------------------------------------------------------------
apps/accounts/admin.py                                            11      0   100%
apps/accounts/apps.py                                              4      0   100%
apps/accounts/models.py                                           20      1    95%
apps/accounts/permissions.py                                      13      0   100%
apps/accounts/serializers.py                                      26      1    96%
apps/accounts/urls.py                                              4      0   100%
apps/accounts/views.py                                            11      1    91%
apps/analytics/accountability.py                                 143    128    10%
apps/analytics/apps.py                                             4      0   100%
apps/analytics/executive.py                                      323     69    79%
apps/analytics/kpis.py                                           176     74    58%
apps/analytics/urls.py                                             3      0   100%
apps/analytics/views.py                                          476     81    83%
apps/cases/admin.py                                               35      0   100%
apps/cases/apps.py                                                 4      0   100%
apps/cases/deadlines.py                                           44      6    86%
apps/cases/evidence.py                                           159     40    75%
apps/cases/management/commands/escalate_overdue.py                 7      7     0%
apps/cases/models.py                                             195     24    88%
apps/cases/scoping.py                                             76     20    74%
apps/cases/serializers_staff.py                                  550     90    84%
apps/cases/services.py                                           488    130    73%
apps/cases/urls_staff.py                                           6      0   100%
apps/cases/views_staff.py                                        299    139    54%
apps/classifier/apps.py                                            5      0   100%
apps/classifier/management/commands/classify_reports.py           29     29     0%
apps/classifier/management/commands/train_classifier.py           64     64     0%
apps/classifier/models.py                                         19      1    95%
apps/classifier/pipeline.py                                      200    153    24%
apps/classifier/services.py                                       52     42    19%
apps/classifier/text.py                                           14      0   100%
apps/classifier/urls.py                                            3      0   100%
apps/classifier/views.py                                         109     30    72%
apps/concerns/admin.py                                            32      0   100%
apps/concerns/apps.py                                              4      0   100%
apps/concerns/management/commands/seed_reference_data.py          67      0   100%
apps/concerns/models.py                                          210      8    96%
apps/concerns/serializers.py                                     243     20    92%
apps/concerns/services.py                                        152     44    71%
apps/concerns/urls_public.py                                       4      0   100%
apps/concerns/views_public.py                                    145     41    72%
apps/geo/admin.py                                                 13      0   100%
apps/geo/apps.py                                                   4      0   100%
apps/geo/geometry.py                                              46      5    89%
apps/geo/hotspots.py                                              31     23    26%
apps/geo/locate.py                                                30     11    63%
apps/geo/management/commands/import_boundaries.py                 57     57     0%
apps/geo/models.py                                                29      2    93%
apps/geo/urls_staff.py                                             3      0   100%
apps/geo/views_staff.py                                          222    106    52%
apps/notifications/admin.py                                       13      0   100%
apps/notifications/apps.py                                         7      0   100%
apps/notifications/conf.py                                        18      0   100%
apps/notifications/management/commands/send_notifications.py      22     22     0%
apps/notifications/management/commands/sms_check.py               20     20     0%
apps/notifications/messages.py                                    76      4    95%
apps/notifications/models.py                                      81      5    94%
apps/notifications/providers.py                                   92     21    77%
apps/notifications/serializers.py                                 43      0   100%
apps/notifications/services.py                                   226     32    86%
apps/notifications/signals.py                                      8      0   100%
apps/notifications/sms.py                                         29      2    93%
apps/notifications/urls.py                                         3      0   100%
apps/notifications/views.py                                       76     19    75%
apps/priority/admin.py                                             7      0   100%
apps/priority/apps.py                                              4      0   100%
apps/priority/models.py                                           13      1    92%
apps/priority/services.py                                         55     10    82%
----------------------------------------------------------------------------------
TOTAL                                                           5657   1583    72%

19 empty files skipped.
```

Scope note: automated tests verify functional correctness (ISO/IEC 25010 functional suitability, security). Usability (SUS), UAT and performance are evaluated separately with users.