# 🔬 Constitutional Impact Statement

## Description
<!-- Brief description of the changes in this PR -->

## Type of Change
- [ ] 🆕 New feature
- [ ] 🐛 Bug fix
- [ ] ♻️ Refactor
- [ ] 📝 Documentation
- [ ] 🧪 Test
- [ ] 🔧 Infrastructure/CI
- [ ] ⚡ Performance

## Affected Components
<!-- Check all that apply -->
- [ ] Backend API
- [ ] Desktop UI
- [ ] Mobile App
- [ ] Website/Portal
- [ ] ARGO/AI Copilot
- [ ] OCR/Document Pipeline
- [ ] Dispatch/Operations
- [ ] Invoicing/Financial
- [ ] Database/Schema
- [ ] Tests

## Constitutional Impact (G-01)
<!-- Every feature must declare affected invariants -->

### Affected Golden Workflows
- [ ] 3.1 Full Trip Lifecycle
- [ ] 3.2 Return Load
- [ ] 3.3 OCR Recovery
- [ ] 3.4 Maintenance Blocking
- [ ] 3.5 Invoice Workflow
- [ ] 3.6 Freight Exchange
- [ ] 3.7 Dunning & Receivables
- [ ] 3.8 Document Pipeline
- [ ] 3.9 Tachograph Compliance
- [ ] 3.10 Multi-Platform Sync
- [ ] None (infrastructure only)

### Affected System Invariants
<!-- List T-INV, D-INV, I-INV, P-INV, etc. IDs -->

### Affected State Machines
<!-- List which state machines are modified -->

### Affected Friction Rules (R1-R7, S1-S5)

### Affected Financial Invariants (F1-F10)

### Historical Immutability Impact
- [ ] Yes — this changes historical record behavior
- [ ] No — historical records are unaffected

## Schema Migration
- [ ] This PR includes a database migration
- [ ] Migration has been tested against existing data
- [ ] Backwards compatibility is maintained

## ARGO Tool Changes
- [ ] New ARGO tool added — safety tests included
- [ ] Existing ARGO tool modified — tests updated
- [ ] No ARGO changes

## Mobile Feature Parity
- [ ] New mobile feature — parity tests included
- [ ] Existing mobile feature modified — tests updated
- [ ] No mobile changes

## Governance Checklist
- [ ] All affected golden workflows pass (G-02)
- [ ] New tests added for changed behavior (G-02)
- [ ] Workflow Integrity tests pass locally
- [ ] No hardcoded secrets (G-01)
- [ ] SQL uses parameterized queries (G-02)
- [ ] State machine transitions are validated (G-09)

## Quality Tier Target
- [ ] 🥉 Bronze — Internal Demo
- [ ] 🥈 Silver — Family Pilot
- [ ] 🥇 Gold — Public Launch
- [ ] 💎 Platinum — Enterprise Scale

---

*This PR template enforces the Operion Product Constitution (Section 15).*
*All governance rules must be satisfied before merging.*
