/**
 * Human-Like Fix Strategy Router
 *
 * When one fix method doesn't work for a bug, the system learns that and
 * automatically tries a different approach — just like a human developer who
 * thinks "that didn't work, let me try something completely different."
 *
 * Strategies escalate from targeted patches → root-cause analysis → full rewrites.
 * ChromaDB memory is used to skip methods that are known not to work for similar bugs.
 */

// ── Strategy definitions ──────────────────────────────────────────────────────
// Each strategy gives the AI a different mental model for approaching the fix.

const FIX_STRATEGIES = [
    {
        name: 'standard',
        description: 'Targeted patch — fix only the exact failing code in the affected files',
        hint: [
            'Fix the specific errors precisely. Patch only the affected files.',
            'Do not touch files that are already working correctly.',
            'Read the error message carefully and fix exactly what it says.',
        ].join(' '),
    },
    {
        name: 'root-cause',
        description: 'Root-cause analysis — find the single shared source of all failures',
        hint: [
            'Instead of fixing symptoms, trace ALL failures back to their single root cause.',
            'These errors likely share one common origin — a wrong import, a missing middleware, a type mismatch.',
            'Fix the root once and all symptoms will clear. Do not patch each symptom separately.',
        ].join(' '),
    },
    {
        name: 'full-rewrite',
        description: 'Full file rewrite — regenerate the entire owning file from scratch',
        hint: [
            'The previous patches are not working. Do NOT make small patches this time.',
            'Identify which file(s) OWNS these failures and REWRITE the entire file(s) from scratch.',
            'Output complete, production-ready file content — not fragments or diffs.',
        ].join(' '),
    },
    {
        name: 'service-isolation',
        description: 'Service isolation — fix one service completely before moving to the next',
        hint: [
            'Fix ONLY the first failing service in this round. Ignore all other services.',
            'Fully repair every file in that single service: index.js, models, routes, middleware.',
            'Other services will be addressed in subsequent rounds.',
        ].join(' '),
    },
    {
        name: 'gateway-first',
        description: 'Gateway-first — fix the API gateway proxy configuration before touching services',
        hint: [
            'Many route failures are caused by incorrect gateway proxy configuration.',
            'Fix the gateway (api-gateway/index.js) completely first.',
            'Verify: correct proxy targets, fixRequestBody, proxyTimeout, onError handler, path prefixes.',
            'Only after the gateway is fully correct should you touch service files.',
        ].join(' '),
    },
    {
        name: 'schema-aligned',
        description: 'Schema-aligned fix — sync model types, route validation, and responses together',
        hint: [
            'Fix all three layers together in one pass:',
            '1. Mongoose schema — ensure every field has explicit type + required flags.',
            '2. Route handlers — validate incoming body fields match schema types before save/update.',
            '3. Response format — every route returns { success: true/false, data/error }.',
            'These three layers must be perfectly aligned for routes to work end-to-end.',
        ].join(' '),
    },
    {
        name: 'dependency-audit',
        description: 'Dependency audit — check all require() paths, package.json, and missing files',
        hint: [
            'All the runtime errors may come from missing files or wrong require() paths.',
            'Audit every require() in every failing file:',
            '  - Does the required file actually exist?',
            '  - Is it listed in package.json dependencies?',
            '  - Are relative paths correct (../models/User vs ./models/User)?',
            'Generate any missing files (middleware/auth.js, missing models, missing routes).',
        ].join(' '),
    },
    {
        name: 'clean-rebuild',
        description: 'Clean rebuild — discard all patches, regenerate all failing services completely',
        hint: [
            'All previous fix strategies have failed. This is a complete clean rebuild.',
            'Discard all accumulated patches. Start completely fresh for the failing service(s).',
            'Regenerate every file: package.json, index.js, models/, routes/, middleware/ — everything.',
            'Write production-quality, complete files. No shortcuts, no TODOs, no placeholders.',
        ].join(' '),
    },
];

// ── Per-request strategy state ────────────────────────────────────────────────
// Tracks what strategies have been tried in the current generation request.
// Keyed by a unique session key generated per POST request.

const _strategyState = new Map();

function getState(key) {
    if (!_strategyState.has(key)) {
        _strategyState.set(key, { triedInSession: new Set(), round: 0 });
    }
    return _strategyState.get(key);
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Pick the next fix strategy for a round.
 *
 * Considers:
 * 1. Strategies already tried this session
 * 2. Strategies known to fail for similar bugs (from ChromaDB memory)
 * 3. Round number — escalates to more drastic approaches as rounds increase
 *
 * @param {string}   sessionKey    - unique key per generation request
 * @param {string[]} failedMethods - methods known to fail for similar bugs (from ChromaDB)
 * @param {number}   round         - current round number (1-based)
 * @returns {{ name: string, description: string, hint: string }}
 */
export function pickStrategy(sessionKey, failedMethods = [], round = 1) {
    const state = getState(sessionKey);
    state.round = round;

    const blocked = new Set([...state.triedInSession, ...failedMethods]);

    // Filter to strategies not yet blocked
    const available = FIX_STRATEGIES.filter(s => !blocked.has(s.name));

    let chosen;
    if (available.length > 0) {
        // Escalate: early rounds use gentle strategies (index 0-1), later rounds use drastic ones
        const escalationIndex = Math.min(Math.floor((round - 1) * 0.7), available.length - 1);
        chosen = available[escalationIndex];
    } else {
        // All strategies exhausted — force clean-rebuild as ultimate fallback
        chosen = FIX_STRATEGIES.find(s => s.name === 'clean-rebuild') || FIX_STRATEGIES[FIX_STRATEGIES.length - 1];
    }

    state.triedInSession.add(chosen.name);
    return chosen;
}

/**
 * Explicitly mark a strategy as failed for this session.
 * Call this when the fix round produced no improvement.
 */
export function markStrategyFailed(sessionKey, strategyName) {
    getState(sessionKey).triedInSession.add(strategyName);
}

/**
 * Clean up session state after generation is complete.
 */
export function clearStrategyState(sessionKey) {
    _strategyState.delete(sessionKey);
}

/**
 * Build a human-like round instruction that combines:
 * - ChromaDB memory context (what worked/failed before)
 * - Strategy hint (how to think about this fix)
 * - Escalation note if many rounds have passed
 * - Current errors to fix
 *
 * This replaces the static "Recovery round X" instructions with
 * dynamic, contextual guidance that changes approach each round.
 *
 * @param {object} opts
 * @param {{ name, description, hint }} opts.strategy
 * @param {string}   opts.memoryContext  - from buildMemoryContext()
 * @param {number}   opts.round
 * @param {number}   opts.errorCount
 * @param {string[]} [opts.currentErrors]
 * @returns {string}
 */
export function buildHumanLikeInstruction({ strategy, memoryContext, round, errorCount, currentErrors = [] }) {
    const parts = [];

    // Inject ChromaDB memory at the top
    if (memoryContext) {
        parts.push(memoryContext);
        parts.push('');
    }

    // Strategy heading
    parts.push(`── ROUND ${round} STRATEGY: "${strategy.name.toUpperCase()}" ──`);
    parts.push(`Approach: ${strategy.description}`);
    parts.push('');
    parts.push(`Instructions: ${strategy.hint}`);
    parts.push('');

    // Escalation pressure
    if (round === 1) {
        parts.push('This is round 1. Focus on the highest-impact root-cause group. Fix it completely in one pass.');
    } else if (round === 2) {
        parts.push(`Round ${round}: The round-1 approach did not fully resolve all issues. Apply the strategy above — do NOT repeat the same patches from round 1.`);
    } else {
        parts.push(`Round ${round}: ${errorCount} error(s) still remain after ${round - 1} previous attempts. The previous approach(es) did not work. This strategy ("${strategy.name}") is deliberately different — commit to it fully.`);
    }

    // Current errors summary
    if (currentErrors.length) {
        parts.push('');
        parts.push(`ERRORS STILL REMAINING (${errorCount} total):`);
        currentErrors.slice(0, 6).forEach(e => parts.push(`  • ${e}`));
        if (errorCount > 6) parts.push(`  ... and ${errorCount - 6} more`);
    }

    return parts.join('\n');
}

export { FIX_STRATEGIES };
