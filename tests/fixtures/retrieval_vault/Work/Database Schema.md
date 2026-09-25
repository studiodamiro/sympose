---
tags: [backend, billing]
---
# Database Schema

The billing service uses three tables: invoices, customers and payments. Create a new migration for every schema change and never edit a table by hand.

## Indexes

Invoices are indexed by customer and by due date.
