# Email+URL Joint Synthetic Dataset v2 Summary

- Source baseline rows kept: **56**
- New rows appended: **144**
- Total rows: **200**

## Category Composition

- benign: **80**
- malicious: **80**
- edge_case: **40**

## Expected Label Distribution
- expected_email_label: `{'malicious': 102, 'benign': 98}`
- expected_url_label: `{'benign': 109, 'malicious': 91}`
- expected_joint_label: `{'malicious': 114, 'benign': 86}`

## Added Scenario Coverage (examples)
- Hard-negative benign: password reset legit, sign-in alert official, file invite official, banking/shipping official, benign no-URL internal notices.
- Hard-positive malicious: clean HTTPS impersonation URLs, subtle invoice/payment lures, malicious no-URL credential requests.
- Mixed/conflict: benign text + malicious URL, malicious text + official URL, sender-brand mismatch, mixed trusted/untrusted URL sets, no-URL text-dominant cases.

## Top Scenarios By Count

- brand_impersonation_clean: 28
- benign_no_url_internal_notice: 21
- shared_doc_clean_phish: 12
- mixed_urls_benign_plus_malicious: 10
- malicious_no_url_credential_lure: 10
- sender_brand_domain_mismatch: 8
- malicious_text_with_official_url: 8
- password_reset_legit: 6
- clean_shared_doc_phish: 6
- workspace_notice_official: 5
- banking_alert_official: 5
- meeting_reminder_official: 5
- sign_in_alert_official: 5
- file_invite_official: 5
- shipping_update_official: 5
- no_url_text_dominant_malicious: 3
- no_url_text_dominant_benign: 3
- travel_confirmation: 1
- it_notice_variant: 1
- student_portal: 1
