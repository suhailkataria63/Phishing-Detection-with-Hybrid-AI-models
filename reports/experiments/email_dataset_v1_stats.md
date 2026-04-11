# Email Dataset v1 Stats

## Summary
- Total rows: **6,992**
- Deduplicated rows removed: **2,299**
- Enron sample target: **1,000**
- Max rows per source+label: **1,500**

## Rows by Source
- enron: 994
- nazario: 2,998
- spamassassin: 3,000

## Rows by Label
- label=0: 3,992
- label=1: 3,000

## Rows by Source+Label
- source=enron, label=0: 994
- source=nazario, label=0: 1,498
- source=nazario, label=1: 1,500
- source=spamassassin, label=0: 1,500
- source=spamassassin, label=1: 1,500

## Nazario Label Polarity Sanity Check
- Assumption used: `label=1` is suspicious/phishing-like, `label=0` is legitimate.
- label=0 sample subjects/snippets:
  - FW: June 29 -- BNA, Inc. Daily Labor Report
  - NGX failover plan.
  - RE: Intranet Site
- label=1 sample subjects/snippets:
  - DON'T DELETE THIS MESSAGE -- FOLDER INTERNAL DATA
  - Verify Your Account
  - Helpdesk Mailbox Alert!!!

## Duplicate Archive Handling
- Skipped duplicate SpamAssassin archives (same file hash): 20030228_easy_ham.tar.bz2

## Parsed Output Examples
- Example 1: source=enron, label=0, sender_domain=enron.com
  - subject: Re-Alignment
  - sender: enron.announcements@enron.com
  - body_preview: Thanks to all of you, Enron North America has had an outstanding year in 2000. Some of the more notable accomplishments include: a) 100% plu
  - urls: []
- Example 2: source=nazario, label=0, sender_domain=issues.apache.org
  - subject: [Bug 5813] [review] several TLDs are not parsed by URI text scanner in PerMsgSta
  - sender: qydlqcws-iacfym@issues.apache.org
  - body_preview: http://issues.apache.org/SpamAssassin/show_bug.cgi?id=5813 ------- Additional Comments From wrzzpv@sidney.com 2008-02-08 02:58 ------- Here 
  - urls: ["http://issues.apache.org/SpamAssassin/show_bug.cgi?id=5813", "http://en.wikipedia.org/wiki/.so_%28domain_name%29"]
- Example 3: source=spamassassin, label=0, sender_domain=egwn.net
  - subject: Re: problems with 'apt-get -f install'
  - sender: Matthias Saou <matthias@egwn.net>
  - body_preview: Once upon a time, Lance wrote : > I have failed dependencies in RPM database to I am unable to use > apt-get. I requests to run 'apt-get -f 
  - urls: ["http://lists.freshrpms.net/mailman/listinfo/rpm-list"]
- Example 4: source=enron, label=0, sender_domain=bayer.com
  - subject: Some Photos of the Addition to the Family
  - sender: todd.johnson.b@bayer.com
  - body_preview: Hi All, Luke Tatsu Johnson arrived at 3:26 AM on 2/5. Tatsu is Japanese for dragon - 2000 is the year of the dragon. He weighed in at 9 lbs.
  - urls: []
- Example 5: source=enron, label=0, sender_domain=enron.com
  - subject: Business Review
  - sender: stanley.horton@enron.com
  - body_preview: After returning home and reviewing the material handed out at the PGE business review, there are two areas that I think I need to understand
  - urls: []

## Assumptions and Limitations
- Enron is treated as legitimate (`label=0`) and sampled instead of full ingestion.
- URL extraction is regex-based and lightweight; hidden links in complex HTML may be missed.
- Sender domain extraction uses header sender field and may be blank on malformed messages.
- SpamAssassin labels are inferred from archive names (`spam` vs `ham`).
- Cross-source deduplication is content-hash based on subject/body/sender/label.
