---
tags: [security]
---
# Vault Security Policy

The company secrets vault rotates API keys every ninety days. Access to the vault needs two approvers, and every read is logged.

## Break glass

In an outage the on-call engineer may open the vault alone; the access is reviewed the next morning.
