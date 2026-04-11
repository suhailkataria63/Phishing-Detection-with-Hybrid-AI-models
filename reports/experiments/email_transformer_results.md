# Email Transformer Hybrid Results (TG-5.8)

Generated: 2026-03-27T14:26:56.177635Z

## Dataset Summary
- Dataset: `data/processed/email_dataset_v2_features.csv`
- Rows: 6,992
- Label distribution: {0: 3992, 1: 3000}
- Source distribution: {'enron': 994, 'nazario': 2998, 'spamassassin': 3000}
- Numeric feature count: 9
- Numeric feature columns: ['url_count', 'has_ip_url', 'avg_url_length', 'suspicious_tld_count', 'shortener_count', 'exclamation_count', 'digit_ratio', 'capital_ratio', 'body_length']
- Encoder fine-tuning: disabled (frozen encoder)

## Random Split Results
- Train size: 5,593 | Test size: 1,399
- Train labels: {0: 3193, 1: 2400}
- Test labels: {0: 799, 1: 600}
- Accuracy: **0.9064**
- Precision: **0.9009**
- Recall: **0.8783**
- F1: **0.8895**
- ROC-AUC: **0.9672**
- Confusion matrix (rows=true [0,1], cols=pred [0,1]):
```
[[741, 58], [73, 527]]
```

### Random Split Threshold Analysis
| Threshold | Precision | Recall | F1 | False Positives | False Negatives |
|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.6391 | 0.9917 | 0.7773 | 336 | 5 |
| 0.5 | 0.9009 | 0.8783 | 0.8895 | 58 | 73 |
| 0.8 | 0.9880 | 0.5483 | 0.7053 | 4 | 271 |

### Random Split Sample Misclassifications
- source=spamassassin true=0 pred=1 prob=0.6259 text="Haunted Mansion movie inches forward [SEP] URL: http://boingboing.net/#85497407 Date: Not supplied Disney's put up a little brochureware site about its forthcoming (and very exciti"
- source=spamassassin true=0 pred=1 prob=0.5143 text="Yahoo Finance RSS Beta [SEP] URL: http://jeremy.zawodny.com/blog/archives/000187.html Date: 2002-09-23T11:47:57-08:00 Got a stock ticker for which you'd like to have an RSS news fe"
- source=spamassassin true=1 pred=0 prob=0.1913 text="hi 56281814119876554443333 [SEP] We w ant to help you get lo wer HOUSE pa yments, with no ha ssle Cli ck To st op recie ving this, rem ove from our l ink on the s ite. 562818141198"
- source=nazario true=0 pred=1 prob=0.5259 text="[EDIS] STAGE 1 ELECTRICAL EMERGENCY DECLARED [Urgent: Statewide] [SEP] From: ISO ISO declared STAGE 1 Electrical Emergency for 07/03/2001 11:20 through 07/03/2001 18:00 For more in"
- source=nazario true=1 pred=0 prob=0.4404 text="=?UTF-8?B?5oKo5pyJ77yINO+8ieadoeacqumAgei+vueahOmCruS7tg==?= [SEP] 你好jose@monkey.org 我们检测到您有4封未送达或延迟的邮件未收到您 这是由于系统错误引起的 在下面纠正： 发布延迟消息 此消息来自电子邮件服务器 2020 © Mail Data."

## Cross-Source Results
### Experiment A: Train Enron+Nazario, Test SpamAssassin
- Train size: 3,992 | Test size: 3,000
- Train labels: {0: 2492, 1: 1500}
- Test labels: {0: 1500, 1: 1500}
- Accuracy: **0.6790**
- Precision: **0.9769**
- Recall: **0.3667**
- F1: **0.5332**
- ROC-AUC: **0.9319**
- Confusion matrix (rows=true [0,1], cols=pred [0,1]):
```
[[1487, 13], [950, 550]]
```

#### Threshold Analysis (Experiment A)
| Threshold | Precision | Recall | F1 | False Positives | False Negatives |
|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.7629 | 0.9527 | 0.8473 | 444 | 71 |
| 0.5 | 0.9769 | 0.3667 | 0.5332 | 13 | 950 |
| 0.8 | 1.0000 | 0.0220 | 0.0431 | 0 | 1467 |

#### Sample Misclassifications (Experiment A)
- source=spamassassin true=1 pred=0 prob=0.2422 text="DON'T LET A COMPUTER VIRUS RUIN YOUR DAY! 12879 [SEP] Does Your Computer Need an Oil Change Does Your Computer Need an Oil Change? Norton SystemWorks 2002 Professional Edition Made"
- source=spamassassin true=0 pred=1 prob=0.5449 text="Sneak Peek: NEW HP Products [SEP] Buyers Alert Announce * * * * * * * * SPECIAL ADVERTISER ANNOUNCEMENT * * * * * * * * July 18, 2002 HP Postcard Sign up for more free newsletters "
- source=spamassassin true=1 pred=0 prob=0.1740 text="Behind Every Elite Producer... [SEP] Behind every elite producer...is an elite seminar system! Attention all independent registered representatives: Our reps' business has grown dr"
- source=spamassassin true=1 pred=0 prob=0.4111 text="The best possible mortgage [SEP] HAS YOUR MORTGAGE SEARCH GOT YOU DOWN? Are you frustrated and confused with all the different terms and quotes? Don't know who is telling you the t"
- source=spamassassin true=1 pred=0 prob=0.2528 text="Rates Have Fallen Again! 6.29% Fixed Rate Mortgage 9879 [SEP] <html> <body> <table width="500" align="center"> <tr> <td bgcolor="#FFFF00"> <p align="center"> <b> <font face="webdin"

### Experiment B: Train Enron+SpamAssassin, Test Nazario
- Train size: 3,994 | Test size: 2,998
- Train labels: {0: 2494, 1: 1500}
- Test labels: {0: 1498, 1: 1500}
- Accuracy: **0.9123**
- Precision: **0.9251**
- Recall: **0.8973**
- F1: **0.9110**
- ROC-AUC: **0.9661**
- Confusion matrix (rows=true [0,1], cols=pred [0,1]):
```
[[1389, 109], [154, 1346]]
```

#### Threshold Analysis (Experiment B)
| Threshold | Precision | Recall | F1 | False Positives | False Negatives |
|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.5859 | 1.0000 | 0.7389 | 1060 | 0 |
| 0.5 | 0.9251 | 0.8973 | 0.9110 | 109 | 154 |
| 0.8 | 0.9853 | 0.0893 | 0.1638 | 2 | 1366 |

#### Sample Misclassifications (Experiment B)
- source=nazario true=0 pred=1 prob=0.5155 text="Is mobile really a sure thing for Google? | CNET News.com Alert [SEP] General | CNET News.com Alert Manage your alerts | Create alerts | Send us feedback Is mobile really a sure th"
- source=nazario true=1 pred=0 prob=0.2937 text="having some trouble with your billing information N 8378806 [SEP] 5/29/2022 1:06:27 AM"
- source=nazario true=0 pred=1 prob=0.6682 text="ONEOK Named a Top Performer on CFO Magazine's Annual Capital Spending Scorecard [SEP] ONEOK Inc. ONEOK Named a Top Performer on CFO Magazine's Annual Capital Spending Scorecard htt"
- source=nazario true=1 pred=0 prob=0.3845 text="=?utf-8?b?VkVSSUZMWeS7juS4i+aciOmCrueuseWwhuS8muWPlua2iOa/gOa0u+eriw==?= =?utf-8?b?5Y2z5pu05paw?= [SEP] jose@monkey.org, `A8v84AE{B14D9D]F2nE1 D9SEFFDO1A[FCF4`A8v84AE{B1e459Cb16`A8"
- source=nazario true=1 pred=0 prob=0.3764 text="Identity Confirmation Request from monkey.org [SEP] Hi jose, jose@monkey.org removal from monkey.org server has been approved and initiated, Due to ignorance of last verification w"

### Experiment C: Train Nazario+SpamAssassin, Test Enron
- Train size: 5,998 | Test size: 994
- Train labels: {0: 2998, 1: 3000}
- Test labels: {0: 994}
- Accuracy: **0.6449**
- Precision: **0.0000**
- Recall: **0.0000**
- F1: **0.0000**
- ROC-AUC: n/a (single-class test set)
- Confusion matrix (rows=true [0,1], cols=pred [0,1]):
```
[[641, 353], [0, 0]]
```

#### Threshold Analysis (Experiment C)
| Threshold | Precision | Recall | F1 | False Positives | False Negatives |
|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.0000 | 0.0000 | 0.0000 | 944 | 0 |
| 0.5 | 0.0000 | 0.0000 | 0.0000 | 353 | 0 |
| 0.8 | 0.0000 | 0.0000 | 0.0000 | 43 | 0 |

#### Sample Misclassifications (Experiment C)
- source=enron true=0 pred=1 prob=0.7545 text="Some Photos of the Addition to the Family [SEP] Hi All, Luke Tatsu Johnson arrived at 3:26 AM on 2/5. Tatsu is Japanese for dragon - 2000 is the year of the dragon. He weighed in a"
- source=enron true=0 pred=1 prob=0.7283 text="Academic Advising [SEP] Hi Everyone, If you would like to make an appointment for academic advising or program planning, please feel free to contact me or Shawn. We prefer to do th"
- source=enron true=0 pred=1 prob=0.8125 text="Houston All-Employee Meeting Notice [SEP] Please join us at an all-employee meeting at 10 a.m. Wednesday, Aug. 9, in the Hyatt Regency's Imperial Ballroom. We will review our secon"
- source=enron true=0 pred=1 prob=0.5036 text="FW: Crude 24X7 WTI Marketing Effort [SEP] Crude 24X7 WTI Marketing Effort Trade Count: 214 Trades 10.3 Millions of Barrels 12 Counterparties Transacting Today 29 Counterparties Tra"
- source=enron true=0 pred=1 prob=0.7428 text="iBuyit [SEP] eProcurement Today marks the launch of the iBuyit eProcurement tool within Enron Transportation Services. While many employees are using eProcurement through the B2B p"

## Key Findings
- Random split vs text-only baseline F1: 0.9635 -> 0.8895 (delta -0.0740).
- Experiment A vs text-only F1: 0.1273 -> 0.5332; recall: 0.0680 -> 0.3667.
- Experiment A vs hybrid baseline F1: 0.1980 -> 0.5332; recall: 0.1100 -> 0.3667.
- Experiment B vs text-only F1: 0.8044 -> 0.9110; recall: 0.7033 -> 0.8973.
- Experiment B vs hybrid baseline F1: 0.7349 -> 0.9110; recall: 0.6100 -> 0.8973.
- Experiment C vs text-only F1: 0.0000 -> 0.0000; recall: 0.0000 -> 0.0000.
- Experiment C vs hybrid baseline F1: 0.0000 -> 0.0000; recall: 0.0000 -> 0.0000.
- Lower thresholds (0.2) consistently raise recall while increasing false positives.
- Cross-source generalization remains the hardest setting and should drive next iterations.

## Conclusion
- Transformer+numeric fusion is now trained end-to-end and reproducible via saved artifacts.
- Next steps: calibration, source-aware regularization, and stronger domain generalization strategies before production rollout.
- Total runtime: 910.3 seconds
