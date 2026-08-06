#!/bin/bash
# Run mutation testing and save score
npx stryker run src/__tests__/mutation/stryker.conf.json
