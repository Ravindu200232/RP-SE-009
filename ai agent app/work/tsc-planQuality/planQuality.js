const REQUIRED_HEADINGS = [
    '# Implementation Plan -',
    '## Project Overview & Design Philosophy',
    '## Requirement Summary',
    '## Architecture & Folder Strategy',
    '## Database Schema Summary',
    '## Page/Module List',
    '## API Routes List',
    '## UI and Component Strategy',
    '## Page-by-Page Build Blueprint',
    '## Development Phases',
    '## Quality & Acceptance Checklist',
];
const STOP_WORDS = new Set([
    'api',
    'apis',
    'app',
    'array',
    'auth',
    'backend',
    'build',
    'collection',
    'collections',
    'component',
    'components',
    'crud',
    'data',
    'database',
    'db',
    'enum',
    'field',
    'fields',
    'frontend',
    'index',
    'indexes',
    'model',
    'models',
    'mongodb',
    'mongoose',
    'next',
    'optional',
    'page',
    'pages',
    'positive',
    'negative',
    'ref',
    'refs',
    'required',
    'route',
    'routes',
    'schema',
    'schemas',
    'status',
    'timestamps',
    'type',
    'unique',
    'workflow',
    'workflows',
].map((word) => word.toLowerCase()));
const FIELD_STOP_WORDS = new Set([
    'active',
    'array',
    'boolean',
    'cancelled',
    'card',
    'cash',
    'compound',
    'created',
    'createdby',
    'date',
    'default',
    'draft',
    'enum',
    'false',
    'inactive',
    'index',
    'number',
    'objectid',
    'optional',
    'ordered',
    'positive',
    'received',
    'ref',
    'required',
    'string',
    'timestamps',
    'true',
    'unique',
    'updated',
].map((word) => word.toLowerCase()));
function unique(items) {
    return Array.from(new Set(items));
}
function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
function toPascalName(raw) {
    const cleaned = raw
        .replace(/[`*_()[\]{}]/g, ' ')
        .replace(/\b(collection|model|entity|schema|table)s?\b/gi, ' ')
        .replace(/[^A-Za-z0-9]+/g, ' ')
        .trim();
    if (!cleaned)
        return '';
    return cleaned
        .split(/\s+/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join('');
}
function looksLikeModelName(name) {
    if (!name || name.length < 3 || name.length > 40)
        return false;
    if (!/^[A-Z][A-Za-z0-9]*$/.test(name))
        return false;
    if (STOP_WORDS.has(name.toLowerCase()))
        return false;
    return true;
}
function addModelCandidate(out, raw) {
    const candidate = toPascalName(raw);
    if (looksLikeModelName(candidate))
        out.push(candidate);
}
export function extractExpectedModels(srs) {
    const lines = (srs || '').replace(/\r\n/g, '\n').split('\n');
    const out = [];
    let inSchemaSection = false;
    let schemaBudget = 0;
    for (const originalLine of lines) {
        const line = originalLine.trim();
        if (!line) {
            if (inSchemaSection)
                schemaBudget -= 1;
            if (schemaBudget <= 0)
                inSchemaSection = false;
            continue;
        }
        const sectionStart = line.match(/^(?:#+\s*)?(?:database\s+collections?|database\s+schema|data\s+models?|models?|entities|collections?)\s*:?\s*(.*)$/i);
        if (sectionStart) {
            inSchemaSection = true;
            schemaBudget = 40;
            if (sectionStart[1]) {
                for (const part of sectionStart[1].split(/[,;|]/)) {
                    addModelCandidate(out, part.replace(/:.*/, ''));
                }
            }
            continue;
        }
        if (inSchemaSection &&
            /^(?:expected\s+apis?|api\s+routes?|pages?|public\s+pages?|dashboard\s+pages?|build\s+quality|quality|roles?|auth|goal|tech\s+stack)\s*:/i.test(line)) {
            inSchemaSection = false;
            schemaBudget = 0;
        }
        if (!inSchemaSection)
            continue;
        schemaBudget -= 1;
        const cleaned = line.replace(/^[-*]\s*/, '').replace(/^\d+\.\s*/, '');
        const namedLine = cleaned.match(/^([A-Z][A-Za-z0-9 _/-]{1,45})(?=\s*[:(-])/);
        if (namedLine) {
            addModelCandidate(out, namedLine[1]);
            continue;
        }
        for (const part of cleaned.split(/[,;|]/)) {
            const beforeDetails = part.replace(/[:(-].*$/, '').trim();
            if (/^[A-Z][A-Za-z0-9 _/-]{1,45}$/.test(beforeDetails)) {
                addModelCandidate(out, beforeDetails);
            }
        }
    }
    return unique(out);
}
function titleCase(value) {
    return value
        .replace(/[-_/]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/\b\w/g, (char) => char.toUpperCase());
}
function slugify(value) {
    const slug = value
        .toLowerCase()
        .replace(/\b(page|screen|module|management|manage)\b/g, ' ')
        .replace(/&/g, ' and ')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
    return slug || 'page';
}
function compactPagePhrase(raw) {
    return raw
        .replace(/\([^)]*\)/g, ' ')
        .replace(/\bwith\b[\s\S]*$/i, ' ')
        .replace(/\bfor\b[\s\S]*$/i, ' ')
        .replace(/\bsupport\b[\s\S]*$/i, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}
function splitPageItems(raw) {
    const text = raw.trim().replace(/\.$/, '');
    const semicolonParts = text.split(';').map((part) => part.trim()).filter(Boolean);
    const parts = semicolonParts.length > 1 ? semicolonParts : text.split(',').map((part) => part.trim());
    return parts
        .map(compactPagePhrase)
        .map((part) => part.replace(/^(and|or)\s+/i, '').trim())
        .filter((part) => part.length > 2);
}
function routeForPagePhrase(phrase, scope) {
    const lower = phrase.toLowerCase();
    if (/\blogin\b|sign in/.test(lower))
        return '/login';
    if (/\bregister\b|sign up/.test(lower))
        return '/register';
    if (/\bhome\b|landing/.test(lower))
        return '/';
    if (/product\s+details?|item\s+details?/.test(lower))
        return '/products/[slug]';
    if (/product\s+listing|products?\s+list|catalog/.test(lower))
        return '/products';
    if (/\bcart\b/.test(lower))
        return '/cart';
    if (/\bcheckout\b/.test(lower))
        return '/checkout';
    if (/order\s+success|success/.test(lower))
        return '/order-success';
    if (/\babout\b/.test(lower))
        return '/about';
    if (/\bcontact\b/.test(lower))
        return '/contact';
    const isDashboard = scope === 'dashboard' || /dashboard|admin|manager|staff|reports?/i.test(phrase);
    if (isDashboard && /overview|dashboard/.test(lower))
        return '/dashboard';
    if (isDashboard && /\bpos\b|billing|cashier/.test(lower))
        return '/dashboard/pos';
    if (isDashboard && /stock\s+adjust/.test(lower))
        return '/dashboard/stock-adjustments';
    if (isDashboard && /\bgrn\b|receiving|goods\s+received/.test(lower))
        return '/dashboard/grn';
    if (isDashboard && /online\s+orders?|orders?/.test(lower))
        return '/dashboard/orders';
    if (isDashboard && /invoice|sales?\s+history|sales?/.test(lower))
        return '/dashboard/sales';
    if (isDashboard && /reports?/.test(lower))
        return '/dashboard/reports';
    if (isDashboard && /settings?/.test(lower))
        return '/dashboard/settings';
    if (isDashboard && /staff|users?|roles?/.test(lower))
        return '/dashboard/users';
    const slugSource = lower.includes('/') ? lower.split('/')[0] : phrase;
    const slug = slugify(slugSource);
    return isDashboard ? `/dashboard/${slug}` : `/${slug}`;
}
function pageFromPhrase(phrase, scope) {
    const route = routeForPagePhrase(phrase, scope);
    const type = scope === 'auth'
        ? 'Auth'
        : route.startsWith('/dashboard')
            ? 'Dashboard'
            : route === '/login' || route === '/register'
                ? 'Auth'
                : 'Public';
    const cleanTitle = titleCase(compactPagePhrase(phrase) || route.split('/').filter(Boolean).pop() || 'Home');
    const title = route === '/'
        ? 'Home Page'
        : cleanTitle.toLowerCase().endsWith('page')
            ? cleanTitle
            : `${cleanTitle} Page`;
    const access = type === 'Public' || type === 'Auth'
        ? 'Public'
        : route.includes('/reports') || route.includes('/settings') || route.includes('/users')
            ? 'Admin / Super Admin'
            : 'Role-based';
    return {
        route,
        title,
        type,
        access,
        purpose: `Implement ${title} required by the user input.`,
    };
}
export function extractExpectedPages(srs) {
    const out = [];
    for (const line of (srs || '').replace(/\r\n/g, '\n').split('\n')) {
        const match = line
            .trim()
            .match(/^(public\s+pages?|dashboard\s+pages?|admin\s+pages?|app\s+pages?|pages?|routes?)\s*:\s*(.+)$/i);
        if (!match)
            continue;
        const label = match[1].toLowerCase();
        const scope = label.includes('dashboard') || label.includes('admin') ? 'dashboard' : 'public';
        for (const item of splitPageItems(match[2]))
            out.push(pageFromPhrase(item, scope));
    }
    const lower = srs.toLowerCase();
    if (/\blogin page\b|\blogin\b/.test(lower))
        out.push(pageFromPhrase('login', 'auth'));
    if (/\bregister page\b|\bregister\b|sign up/.test(lower)) {
        out.push(pageFromPhrase('register', 'auth'));
    }
    const seen = new Set();
    return out.filter((page) => {
        if (seen.has(page.route))
            return false;
        seen.add(page.route);
        return true;
    });
}
function routeRowsFromPlan(plan) {
    const rows = [];
    for (const match of plan.matchAll(/^\|\s*`?(\/[^|` ]*)`?\s*\|\s*([^|]+)\|(?:\s*([^|]+)\|){0,3}\s*([^|]*)\|?$/gm)) {
        const route = match[1].trim();
        if (route === '/---' || route.toLowerCase() === '/route')
            continue;
        rows.push({
            route,
            page: match[2].replace(/`/g, '').trim() || route,
            purpose: (match[4] || '').replace(/`/g, '').trim(),
        });
    }
    return rows;
}
function pageBlueprintRoutesFromPlan(plan) {
    return unique([...plan.matchAll(/^###\s+`?(\/[^`\s]*)`?\s+-\s+([^\n]+)$/gm)]
        .map((match) => match[1].trim())
        .filter((route) => !route.startsWith('/api')));
}
function documentedModelsFromPlan(plan) {
    return unique([...plan.matchAll(/^###\s+([A-Z][A-Za-z0-9]+)\s*\((?:lib\/models\/|models\/)[^)]+\.ts\)/gm)].map((match) => match[1]));
}
function apiRoutesFromPlan(plan) {
    return unique([...plan.matchAll(/\b(GET|POST|PUT|PATCH|DELETE)\s+(\/api\/[A-Za-z0-9_\-/:[\]\{\}]+)/g)].map((match) => `${match[1]} ${match[2]}`));
}
function expectedApiMinimum(srs, hasBackend, expectedModels) {
    if (!hasBackend)
        return 0;
    const lower = srs.toLowerCase();
    if (!/(api|crud|database|mongodb|mongoose|auth|login|register|backend)/.test(lower))
        return 0;
    if (expectedModels.length >= 5)
        return 10;
    if (expectedModels.length >= 2)
        return Math.min(6, expectedModels.length * 2);
    return 2;
}
export function analyzeImplementationPlan(plan, srs, hasBackend) {
    const missingHeadings = REQUIRED_HEADINGS.filter((heading) => !plan.includes(heading));
    const routeHeaderOk = /\|\s*Route\s*\|\s*Page\s*\|\s*Type\s*\|\s*Access\s*\|\s*Purpose\s*\|/.test(plan);
    const rows = routeRowsFromPlan(plan);
    const pageRows = rows.filter((row) => !row.route.startsWith('/api'));
    const apiRowsInPageTable = rows
        .filter((row) => row.route.startsWith('/api'))
        .map((row) => row.route);
    const pageRoutes = unique(pageRows.map((row) => row.route));
    const expectedPages = extractExpectedPages(srs);
    const expectedPageRoutes = expectedPages.map((page) => page.route);
    const missingExpectedPageRoutes = expectedPageRoutes.filter((route) => !pageRoutes.includes(route));
    const pageBlueprintRoutes = pageBlueprintRoutesFromPlan(plan);
    const missingPageBlueprintRoutes = pageRoutes.filter((route) => !pageBlueprintRoutes.includes(route));
    const expectedModels = extractExpectedModels(srs);
    const documentedModels = documentedModelsFromPlan(plan);
    const missingModels = expectedModels.filter((model) => !documentedModels.includes(model));
    const labels = ['**Sections**:', '**Functions**:', '**Data**:', '**Design**:'];
    const missingPageBlueprintLabels = labels.filter((label) => !plan.includes(label));
    const codeFenceCount = (plan.match(/```/g) || []).length;
    const hasTypeScriptInterfaces = /\binterface\s+[A-Z]/.test(plan);
    const apiRoutes = apiRoutesFromPlan(plan);
    const apiMinimum = expectedApiMinimum(srs, hasBackend, expectedModels);
    const issues = [];
    if (missingHeadings.length)
        issues.push(`Missing headings: ${missingHeadings.join(', ')}`);
    if (!routeHeaderOk)
        issues.push('Page/Module List table header is not exact.');
    if (apiRowsInPageTable.length) {
        issues.push(`Page/Module List contains API routes: ${apiRowsInPageTable.join(', ')}`);
    }
    if (missingExpectedPageRoutes.length) {
        issues.push(`Missing page routes from input: ${missingExpectedPageRoutes.join(', ')}`);
    }
    if (missingPageBlueprintRoutes.length) {
        issues.push(`Missing page blueprint blocks: ${missingPageBlueprintRoutes.join(', ')}`);
    }
    if (hasBackend && missingModels.length) {
        issues.push(`Missing model schema sections: ${missingModels.join(', ')}`);
    }
    if (apiMinimum > 0 && apiRoutes.length < apiMinimum) {
        issues.push(`Only ${apiRoutes.length} API endpoints found; expected at least ${apiMinimum}.`);
    }
    if (missingPageBlueprintLabels.length) {
        issues.push(`Missing page blueprint labels: ${missingPageBlueprintLabels.join(', ')}`);
    }
    if (codeFenceCount)
        issues.push('Markdown code fences are present.');
    if (hasTypeScriptInterfaces)
        issues.push('TypeScript interfaces/code snippets are present.');
    return {
        valid: issues.length === 0,
        issues,
        missingHeadings,
        routeHeaderOk,
        pageRoutes,
        apiRowsInPageTable,
        apiRoutes,
        pageBlueprintRoutes,
        missingPageBlueprintRoutes,
        expectedPageRoutes,
        missingExpectedPageRoutes,
        expectedModels,
        documentedModels,
        missingModels,
        missingPageBlueprintLabels,
        codeFenceCount,
        hasTypeScriptInterfaces,
        apiMinimum,
    };
}
export function formatPlanDiagnosticsForPrompt(diagnostics) {
    const lines = diagnostics.issues.length
        ? diagnostics.issues.map((issue) => `- ${issue}`)
        : ['- No structural issues found.'];
    if (diagnostics.expectedModels.length) {
        lines.push(`- Expected models from input: ${diagnostics.expectedModels.join(', ')}`);
    }
    if (diagnostics.pageRoutes.length) {
        lines.push(`- Page routes in table: ${diagnostics.pageRoutes.join(', ')}`);
    }
    if (diagnostics.expectedPageRoutes.length) {
        lines.push(`- Expected page routes from input: ${diagnostics.expectedPageRoutes.join(', ')}`);
    }
    if (diagnostics.apiMinimum > 0) {
        lines.push(`- Minimum API endpoint count for this spec: ${diagnostics.apiMinimum}`);
    }
    return lines.join('\n');
}
function sectionInsertBefore(plan, heading, addition) {
    const index = plan.indexOf(heading);
    if (index < 0)
        return `${plan.trim()}\n\n${addition.trim()}\n`;
    return `${plan.slice(0, index).trimEnd()}\n\n${addition.trim()}\n\n${plan.slice(index).trimStart()}`;
}
function sourceLineForModel(srs, model) {
    const pattern = new RegExp(`^\\s*(?:[-*]\\s*)?${escapeRegExp(model)}\\s*[:(-]\\s*(.*)$`, 'im');
    const match = srs.match(pattern);
    return match?.[1]?.trim() || '';
}
function fieldsForModel(srs, model) {
    const line = sourceLineForModel(srs, model);
    const source = line || 'name, status, createdAt, updatedAt';
    const fields = [...source.matchAll(/\b[A-Za-z_][A-Za-z0-9_]*\b/g)]
        .map((match) => match[0])
        .filter((word) => {
        const lower = word.toLowerCase();
        if (FIELD_STOP_WORDS.has(lower))
            return false;
        if (lower === model.toLowerCase())
            return false;
        return !/^[A-Z][A-Za-z0-9]+$/.test(word) || /Id$/.test(word);
    });
    const normalized = unique(fields).slice(0, 16);
    if (normalized.length)
        return normalized;
    return ['name', 'status', 'createdAt', 'updatedAt'];
}
function typeForField(field) {
    const lower = field.toLowerCase();
    if (lower.endsWith('id') || lower === 'id')
        return 'ObjectId';
    if (/(price|amount|total|quantity|points|tax|discount|level|subtotal|grandtotal)/.test(lower)) {
        return 'Number';
    }
    if (/(images|items|roles|permissions)/.test(lower))
        return 'Array';
    if (/(createdat|updatedat|receivedat|date|expiresat)/.test(lower))
        return 'Date';
    if (/(active|enabled|verified)/.test(lower))
        return 'Boolean';
    return 'String';
}
function modelBlock(model, srs) {
    const rows = fieldsForModel(srs, model)
        .map((field) => {
        const required = /(optional|nullable)/i.test(sourceLineForModel(srs, model)) ? 'Conditional' : 'Yes';
        return `| ${field} | ${typeForField(field)} | ${required} | From user input; preserve validation, unique, enum, and ref notes where specified. |`;
    })
        .join('\n');
    return `### ${model} (lib/models/${model}.ts)\n\n| Field | Type | Required | Notes |\n| --- | --- | --- | --- |\n${rows}`;
}
function kebabModelRoute(model) {
    const words = model.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
    if (words.endsWith('y'))
        return `${words.slice(0, -1)}ies`;
    if (words.endsWith('s'))
        return words;
    return `${words}s`;
}
function apiLinesForModels(models, existingApis) {
    const existing = new Set(existingApis.map((api) => api.toLowerCase()));
    const lines = [];
    for (const model of models) {
        const route = `/api/${kebabModelRoute(model)}`;
        const itemRoute = `${route}/:id`;
        const candidates = [
            `GET ${route} - list/search ${model} records - access(role-based)`,
            `POST ${route} - create ${model} record with validation - access(role-based)`,
            `GET ${itemRoute} - fetch one ${model} record - access(role-based)`,
            `PUT ${itemRoute} - update ${model} record - access(role-based)`,
            `DELETE ${itemRoute} - delete or deactivate ${model} record - access(role-based)`,
        ];
        for (const line of candidates) {
            const key = line.match(/^(GET|POST|PUT|PATCH|DELETE)\s+(\S+)/)?.[0].toLowerCase();
            if (!key || existing.has(key))
                continue;
            existing.add(key);
            lines.push(`- ${line}`);
        }
    }
    return lines;
}
function pageRow(page) {
    return `| ${page.route} | ${page.title} | ${page.type} | ${page.access} | ${page.purpose} |`;
}
function insertPageRows(plan, pages) {
    if (!pages.length)
        return plan;
    const heading = '## Page/Module List';
    const nextHeading = '## API Routes List';
    const headingIndex = plan.indexOf(heading);
    const nextIndex = headingIndex >= 0 ? plan.indexOf(nextHeading, headingIndex) : -1;
    const tableHeader = '| Route | Page | Type | Access | Purpose |\n| --- | --- | --- | --- | --- |';
    const additions = pages.map(pageRow);
    if (headingIndex < 0 || nextIndex < 0) {
        return sectionInsertBefore(plan, nextHeading, `${heading}\n\n${tableHeader}\n${additions.join('\n')}`);
    }
    const before = plan.slice(0, headingIndex);
    const section = plan.slice(headingIndex, nextIndex);
    const after = plan.slice(nextIndex);
    let lines = section.split('\n');
    let headerIndex = lines.findIndex((line) => /\|\s*Route\s*\|\s*Page\s*\|\s*Type\s*\|\s*Access\s*\|\s*Purpose\s*\|/.test(line));
    if (headerIndex < 0) {
        lines = [heading, '', tableHeader, ...additions];
    }
    else {
        let insertAt = headerIndex + 1;
        if (lines[insertAt]?.trim().startsWith('|'))
            insertAt += 1;
        while (insertAt < lines.length && lines[insertAt].trim().startsWith('|'))
            insertAt += 1;
        lines.splice(insertAt, 0, ...additions);
    }
    return `${before}${lines.join('\n').trimEnd()}\n\n${after.trimStart()}`;
}
function pageBlock(route, title, purpose) {
    return `### ${route} - ${title}\n\n**Sections**:\n- Header, primary content area, and contextual actions for ${title}.\n\n**Functions**:\n- Load required data, validate user actions, and support the interactions implied by this route.\n\n**Data**:\n- Use the models, API routes, or local state needed for ${purpose || title}.\n\n**Design**:\n- Responsive Tailwind layout with shadcn/ui controls, clear empty/loading/error states, and accessible labels.`;
}
export function normalizeImplementationPlanCoverage(plan, srs, hasBackend) {
    let out = (plan || '')
        .replace(/^```[a-zA-Z]*\s*$/gm, '')
        .replace(/^```\s*$/gm, '')
        .replace(/shadcs\/ui/gi, 'shadcn/ui')
        .replace(/^###\s+`(\/[^`\n]+)`\s+-/gm, '### $1 -');
    let diagnostics = analyzeImplementationPlan(out, srs, hasBackend);
    if (hasBackend && diagnostics.missingModels.length) {
        const addition = diagnostics.missingModels
            .map((model) => modelBlock(model, srs))
            .join('\n\n');
        out = sectionInsertBefore(out, '## Page/Module List', addition);
    }
    diagnostics = analyzeImplementationPlan(out, srs, hasBackend);
    if (diagnostics.missingExpectedPageRoutes.length) {
        const pageRoutes = new Set(diagnostics.pageRoutes);
        const missingPages = extractExpectedPages(srs).filter((page) => !pageRoutes.has(page.route));
        out = insertPageRows(out, missingPages);
    }
    diagnostics = analyzeImplementationPlan(out, srs, hasBackend);
    const needsApis = diagnostics.apiMinimum > 0 && diagnostics.apiRoutes.length < diagnostics.apiMinimum;
    if (needsApis || diagnostics.apiRowsInPageTable.length) {
        const apiModels = diagnostics.expectedModels.length
            ? diagnostics.expectedModels
            : diagnostics.documentedModels;
        const addition = apiLinesForModels(apiModels, diagnostics.apiRoutes).join('\n');
        if (addition)
            out = sectionInsertBefore(out, '## UI and Component Strategy', addition);
    }
    diagnostics = analyzeImplementationPlan(out, srs, hasBackend);
    if (diagnostics.missingPageBlueprintRoutes.length) {
        const rows = routeRowsFromPlan(out);
        const rowByRoute = new Map(rows.map((row) => [row.route, row]));
        const addition = diagnostics.missingPageBlueprintRoutes
            .map((route) => {
            const row = rowByRoute.get(route);
            return pageBlock(route, row?.page || route, row?.purpose || row?.page || route);
        })
            .join('\n\n');
        out = sectionInsertBefore(out, '## Development Phases', addition);
    }
    return out.trim() + '\n';
}
