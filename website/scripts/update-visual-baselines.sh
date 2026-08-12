#!/bin/bash
# Run this after intentional design changes to update visual regression baselines
npx playwright test e2e/visual-regression.spec.ts --update-snapshots
