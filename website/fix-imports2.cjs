const fs = require('fs');
const path = require('path');

const src = 'C:/Users/Bonjo/source/repos/operion-website/src';

// Each entry: [filePath, importPlacement (text to insert after), hookPlacement (text to insert after)]
const files = [
  ['pages/admin/waitlist/overview-tab.tsx', 'import { extractApiError } from "@/api/client"',
   null],  // import only, hook manual

  ['pages/admin/waitlist/entries-tab.tsx', null, null], // check existing
  ['pages/dashboard/documentation.tsx', 'lucide-react"', 'export default function'],
  ['pages/dashboard/downloads.tsx', 'from "@/i18n/locale-context"', null],  // already has import
  ['pages/dashboard/licenses.tsx', 'from "@/i18n/locale-context"', null],   // already has import
  ['pages/public/blog-category.tsx', 'from "react-router"', 'export default function BlogCategoryPage'],
  ['pages/public/integrations-explorer.tsx', 'from "@/components/seo/structured-data"', 'export default function IntegrationsExplorerPage'],
  ['pages/public/tutorials-list.tsx', 'from "@/components/seo/structured-data"', 'export default function TutorialsListPage'],
];

const importStr = '\nimport { useLocale } from "@/i18n/locale-context"';

for (const [file, importAfter, hookAfter] of files) {
  const fullPath = path.join(src, file);
  if (!fs.existsSync(fullPath)) { console.log('SKIP: ' + file); continue; }
  let content = fs.readFileSync(fullPath, 'utf8');
  let changed = false;

  // Check if useLocale already imported
  if (!content.includes('import { useLocale }')) {
    const idx = content.indexOf(importAfter);
    if (idx > 0) {
      const lineEnd = content.indexOf('\n', idx) + 1;
      content = content.slice(0, lineEnd) + importStr + '\n' + content.slice(lineEnd);
      changed = true;
      console.log('+ import ' + path.basename(file));
    } else {
      console.log('? no import anchor for ' + path.basename(file) + ': "' + (importAfter||'').slice(0,30) + '"');
    }
  }

  // Check if t() hook exists
  if (!content.includes('const { t } = useLocale()')) {
    if (hookAfter) {
      const idx = content.indexOf(hookAfter);
      if (idx > 0) {
        const lineEnd = content.indexOf('\n', idx) + 1;
        content = content.slice(0, lineEnd) + '  const { t } = useLocale()\n' + content.slice(lineEnd);
        changed = true;
        console.log('+ hook ' + path.basename(file));
      }
    }
  }

  if (changed) fs.writeFileSync(fullPath, content, 'utf8');
}

// Manual fix for entries-tab: has import but t used in wrong scope
// Check if t is defined inside EntriesTab function
const entriesPath = path.join(src, 'pages/admin/waitlist/entries-tab.tsx');
let entriesContent = fs.readFileSync(entriesPath, 'utf8');
if (entriesContent.includes('const { t } = useLocale()') && entriesContent.match(/placeholder=\{t\(/)) {
  console.log('entries-tab: t hook exists and used');
}

// Check docs-layout
const dlPath = path.join(src, 'pages/docs/docs-layout.tsx');
let dlContent = fs.readFileSync(dlPath, 'utf8');
if (!dlContent.includes('import { useLocale }')) {
  dlContent = dlContent.replace('import { useLocation }', 'import { useLocation }\nimport { useLocale } from "@/i18n/locale-context"');
  fs.writeFileSync(dlPath, dlContent, 'utf8');
  console.log('+ import docs-layout');
}

console.log('Done');
