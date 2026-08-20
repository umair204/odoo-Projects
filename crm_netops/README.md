# CRM and NetOps (`crm_netops`)

Odoo 19 module managing the **end-to-end ISP B2B sales process** for KK Networks (PVT) LTD. — from Lead Qualification through Technical Surveys, ROI Approval, and Post-Sale Provisioning.

> **Note:** This repository contains **documentation only** for this module (process flowchart). The source code is proprietary to KK Networks (PVT) LTD. and is **not published** in this public repository.

## Overview

The module drives the full lifecycle of a corporate/carrier ISP sale in Odoo CRM, connecting Sales, Technical Survey, Sales Operations, CEO Approval, and NetOps/Deployment teams into a single tracked pipeline — from a new lead to a live, billed customer subscription.

See [`CRM_NETOPS_Flow.pdf`](./CRM_NETOPS_Flow.pdf) for the full process diagram.

## Process Flow

### 1. Opportunity
- Lead/Opportunity created in CRM Pipeline (Stage: Opportunity).
- Mandatory lead details captured: Customer, Product, Qty, Requested Medium (Fiber/Wireless/Both/3rd Party), and Installation POC (Contact + Address + GPS).
- Moves to Feasibility with a snapshot of the POC address.

### 2. Feasibility
- Branches by Medium Type — **Fiber Survey** and/or **Wireless Survey** (POP location, hardware, feasibility).
- Each survey is submitted independently (`fiber_status` / `wireless_status`).
- A lead cannot be marked Won unless at least one medium (Fiber or Wireless) is feasible when both are requested.
- Notifies the NOC/Technical Team by email on survey submission.

### 3. Solution Finalize
- Sales Operations reviews survey results, sets the Approved Medium, and adds notes.
- Can reset the survey and send the lead back to Feasibility if needed.
- Once surveys are OK, moves to the Proposal stage (notifies proposal custodians).

### 4. Proposal and Negotiation
- ROI is computed from Price Offered, Business Cost, Deployment Cost, Bandwidth, and MRC Profit — expressed as months-to-breakeven.
- If ROI ≤ 5, the deal proceeds directly to Progression with **no approval required**.
- If ROI > 5, it's routed to the CEO Approval stage.

### 5. Approval
- CEO reviews and decides (email notification to CEO).
- If approved, moves to Progression.
- If rejected, returns to Negotiation/Proposal for revision.

### 6. Progression → Review → Won
- Billing POC added; final checks performed (Review Stage).
- Lead marked as Won: feasibility validated, USID sequence generated.
- Draft Quotation and Customer Location (with stock location tied to Customer — USID) are created.
- Deployment records are created per medium (Fiber, Wireless, 3rd Party, Testing).
- Ends with **Lead Won — Customer Live**, notifying the Accounts Department.

### 7. NetOps Phase
- Draft entry created in NetOps for the won deal.
- **Fiber Deployment** and **Wireless Deployment** tracks run in parallel, each starting with a NOC Survey/Feasibility check.
- If hardware was added on the CRM lead, a stock transfer is created and validated before deployment; otherwise deployment is created directly.

### 8. Testing & Activation
- Deployment is approved and completed.
- Sale Order is confirmed (auto-confirms the quotation).
- Subscription is created, closing the process.

## Departments / Roles Involved

- **Inventory / Logistics** — KK Networks (PVT) LTD.
- **Technical Team (NOC)** — KK Networks (PVT) LTD.
- **Corporate / Carrier Sales Manager** — KK Networks (PVT) LTD.
- **Chief Executive Officer** — KK Networks (PVT) LTD.

## Notifications

The process sends automated email notifications at key checkpoints to ANO Department, CNO Department, the CEO, KAM, and the Accounts Department, keeping all stakeholders synced as a deal moves through the pipeline.

## Repository Contents

```
crm_netops/
└── CRM_NETOPS_Flow.pdf   # Full process flowchart (source of truth for this document)
```

Source code (models, views, wizards, automations implementing this flow) is maintained privately and is not part of this public repository.

## Author

KK Networks Team — KK Networks (PVT) LTD.
