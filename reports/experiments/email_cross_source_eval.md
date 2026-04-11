# Email Cross-Source Robustness Evaluation

## Setup
- Dataset: `data/processed/email_dataset_v1.csv`
- Model pipeline: `TF-IDF + LogisticRegression`
- Label mapping: `0=legitimate`, `1=suspicious/phishing-like`
- TF-IDF params: max_features=80000, min_df=2, ngram_range=(1,2)

## Experiment A: Train Enron+Nazario, Test SpamAssassin
- Train sources: enron, nazario | Test source: spamassassin
- Train size: 3,992 | Test size: 3,000
- Train label counts: {0: 2492, 1: 1500}
- Test label counts: {0: 1500, 1: 1500}

### Metrics
- Accuracy: **0.5337**
- Precision: **0.9903**
- Recall: **0.0680**
- F1: **0.1273**
- ROC-AUC: **0.9316**

### Confusion Matrix
Rows=true [0,1], Cols=pred [0,1]
```
[[1499, 1], [1398, 102]]
```

### Top 30 Positive Features (push toward label=1)
- `your`: 5.0779
- `account`: 5.0214
- `monkey`: 3.7078
- `your account`: 3.6436
- `monkey org`: 3.5591
- `jose`: 3.5085
- `jose monkey`: 2.9762
- `dear`: 2.8717
- `email`: 2.4438
- `click`: 2.3644
- `payment`: 2.2281
- `utf`: 2.2166
- `security`: 2.1648
- `update`: 2.1615
- `view`: 1.9610
- `org`: 1.8634
- `usaa`: 1.7858
- `customer`: 1.7083
- `kindly`: 1.6771
- `below`: 1.6404
- `bank`: 1.6086
- `verify`: 1.6049
- `click here`: 1.5723
- `mailbox`: 1.5434
- `de`: 1.5155
- `here to`: 1.5147
- `2016`: 1.4630
- `our`: 1.4430
- `upgrade`: 1.4392
- `link`: 1.4256

### Top 30 Negative Features (push toward label=0)
- `enron`: -2.5668
- `the`: -2.3391
- `http`: -2.0743
- `2001`: -1.7403
- `me`: -1.7243
- `at`: -1.6222
- `that`: -1.6072
- `http www`: -1.4527
- `of`: -1.4071
- `list`: -1.3825
- `but`: -1.3107
- `subject`: -1.3020
- `of the`: -1.2354
- `com`: -1.2267
- `know`: -1.2241
- `there`: -1.2083
- `enron com`: -1.1834
- `pm`: -1.1580
- `in the`: -1.1567
- `713`: -1.1251
- `am`: -1.0963
- `they`: -1.0683
- `it`: -1.0486
- `2000`: -1.0460
- `re`: -1.0239
- `is`: -1.0172
- `2007`: -0.9951
- `like`: -0.9834
- `would`: -0.9833
- `www`: -0.9752

## Experiment B: Train Enron+SpamAssassin, Test Nazario
- Train sources: enron, spamassassin | Test source: nazario
- Train size: 3,994 | Test size: 2,998
- Train label counts: {0: 2494, 1: 1500}
- Test label counts: {0: 1498, 1: 1500}

### Metrics
- Accuracy: **0.8289**
- Precision: **0.9394**
- Recall: **0.7033**
- F1: **0.8044**
- ROC-AUC: **0.9565**

### Confusion Matrix
Rows=true [0,1], Cols=pred [0,1]
```
[[1430, 68], [445, 1055]]
```

### Top 30 Positive Features (push toward label=1)
- `your`: 3.7936
- `free`: 3.3876
- `click here`: 3.2419
- `our`: 3.0076
- `click`: 2.9220
- `remove`: 2.5458
- `here`: 2.4659
- `be removed`: 2.0298
- `removed`: 1.9861
- `money`: 1.9274
- `email`: 1.8442
- `spamassassin sightings`: 1.8110
- `sightings`: 1.8011
- `you`: 1.7212
- `receive`: 1.7124
- `000`: 1.6159
- `removed from`: 1.5419
- `offer`: 1.4496
- `business`: 1.4482
- `here to`: 1.4229
- `we`: 1.3557
- `reply`: 1.3525
- `credit`: 1.3345
- `to receive`: 1.2926
- `no`: 1.2708
- `you will`: 1.2447
- `100`: 1.2379
- `to be`: 1.2121
- `please`: 1.2084
- `for you`: 1.2069

### Top 30 Negative Features (push toward label=0)
- `enron`: -3.4240
- `re`: -3.2224
- `the`: -2.5806
- `but`: -1.8621
- `date`: -1.7686
- `wrote`: -1.7562
- `url http`: -1.7267
- `it`: -1.6500
- `that`: -1.6151
- `2002`: -1.5848
- `on`: -1.5693
- `thanks`: -1.5428
- `enron com`: -1.4829
- `pm`: -1.4618
- `url`: -1.4442
- `01`: -1.4148
- `2001`: -1.4057
- `attached`: -1.3677
- `razor`: -1.3517
- `users`: -1.3423
- `713`: -1.3018
- `ect`: -1.2731
- `they`: -1.2292
- `rpm`: -1.1811
- `newsisfree`: -1.1344
- `newsisfree com`: -1.1344
- `www newsisfree`: -1.1344
- `cc`: -1.0967
- `is`: -1.0953
- `gas`: -1.0698

## Experiment C: Train Nazario+SpamAssassin, Test Enron
- Train sources: nazario, spamassassin | Test source: enron
- Train size: 5,998 | Test size: 994
- Train label counts: {0: 2998, 1: 3000}
- Test label counts: {0: 994}

### Metrics
- Accuracy: **0.9135**
- Precision: **0.0000**
- Recall: **0.0000**
- F1: **0.0000**
- ROC-AUC: n/a (single-class test set)

### Confusion Matrix
Rows=true [0,1], Cols=pred [0,1]
```
[[908, 86], [0, 0]]
```

### Top 30 Positive Features (push toward label=1)
- `your`: 5.4529
- `account`: 3.6089
- `our`: 3.2517
- `click`: 3.1265
- `click here`: 3.0844
- `monkey`: 2.8829
- `free`: 2.8429
- `monkey org`: 2.7966
- `you`: 2.7558
- `jose`: 2.7420
- `your account`: 2.4979
- `jose monkey`: 2.3610
- `email`: 2.3441
- `we`: 2.3266
- `here`: 2.1979
- `dear`: 2.1881
- `please`: 2.1766
- `remove`: 2.1287
- `money`: 1.8719
- `spamassassin sightings`: 1.8025
- `below`: 1.7980
- `be removed`: 1.7726
- `sightings`: 1.7486
- `credit`: 1.7275
- `removed`: 1.6593
- `here to`: 1.6345
- `payment`: 1.5908
- `receive`: 1.5401
- `utf`: 1.4906
- `business`: 1.4207

### Top 30 Negative Features (push toward label=0)
- `the`: -3.3865
- `re`: -2.9488
- `but`: -2.6414
- `wrote`: -2.4852
- `that`: -2.4154
- `it`: -2.1946
- `2002`: -2.0335
- `url http`: -2.0278
- `enron`: -1.9816
- `of`: -1.8793
- `there`: -1.7972
- `2007`: -1.7898
- `is`: -1.6922
- `they`: -1.6884
- `url`: -1.6816
- `2001`: -1.6424
- `perl`: -1.5767
- `on`: -1.5394
- `2008`: -1.5057
- `at`: -1.4979
- `mailman`: -1.4531
- `of the`: -1.4407
- `date`: -1.4348
- `july`: -1.4108
- `which`: -1.3897
- `when`: -1.3817
- `users`: -1.3770
- `mailman listinfo`: -1.3730
- `pm`: -1.3595
- `razor`: -1.3155

