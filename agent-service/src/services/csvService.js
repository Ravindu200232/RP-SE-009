/**
 * CSVService — Loads and samples the SRS training dataset.
 *
 * Provides:
 *  1. Domain-matched example training_text rows for few-shot prompting
 *  2. Domain inference from user description
 *  3. Cached loading (CSV loaded once at startup)
 */

import fs from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';
import dotenv from 'dotenv';
dotenv.config();

const CSV_PATH = process.env.SRS_CSV_PATH || 'C:/Users/ravin/Downloads/srs/srs_training_dataset_4000.csv';

// Domain keyword map for inference
const DOMAIN_KEYWORDS = {
  'Healthcare': ['health', 'patient', 'doctor', 'medical', 'hospital', 'clinic', 'appointment', 'ehr', 'emr', 'pharmacy', 'diagnosis'],
  'Education': ['learn', 'course', 'student', 'teacher', 'lms', 'quiz', 'grade', 'school', 'university', 'training', 'lecture', 'exam'],
  'E-Commerce': ['shop', 'product', 'cart', 'order', 'payment', 'checkout', 'store', 'retail', 'buy', 'sell', 'marketplace', 'inventory'],
  'Finance': ['bank', 'finance', 'payment', 'invoice', 'accounting', 'budget', 'transaction', 'wallet', 'loan', 'insurance'],
  'Task Management': ['task', 'todo', 'project', 'kanban', 'sprint', 'agile', 'board', 'workflow', 'assign', 'deadline', 'milestone'],
  'Social Media': ['post', 'comment', 'like', 'follow', 'feed', 'profile', 'social', 'share', 'message', 'notification', 'friend'],
  'Travel': ['travel', 'hotel', 'flight', 'booking', 'trip', 'destination', 'ticket', 'tour', 'reservation', 'itinerary'],
  'Food & Restaurant': ['food', 'restaurant', 'delivery', 'menu', 'order', 'kitchen', 'chef', 'recipe', 'meal', 'cuisine'],
  'HR & Recruitment': ['hr', 'employee', 'recruit', 'hire', 'payroll', 'attendance', 'leave', 'performance', 'onboard', 'staff'],
  'IoT & Smart': ['iot', 'sensor', 'device', 'smart', 'monitor', 'alert', 'dashboard', 'real-time', 'automation'],
};

class CSVService {
  constructor() {
    this._cache = null;
    this._loaded = false;
  }

  // Load CSV once (lazy)
  _load() {
    if (this._loaded) return;
    try {
      if (!fs.existsSync(CSV_PATH)) {
        console.warn(`[CSV] Training CSV not found at: ${CSV_PATH}`);
        this._cache = [];
        this._loaded = true;
        return;
      }
      const content = fs.readFileSync(CSV_PATH, 'utf8');
      // Parse only first 2000 rows for performance
      const lines = content.split('\n').slice(0, 2001).join('\n');
      this._cache = parse(lines, {
        columns: true,
        skip_empty_lines: true,
        relax_quotes: true,
        trim: true
      });
      console.log(`[CSV] Loaded ${this._cache.length} training records`);
    } catch (err) {
      console.error('[CSV] Failed to load training data:', err.message);
      this._cache = [];
    }
    this._loaded = true;
  }

  /**
   * Infer domain from user description text.
   * @param {string} description
   * @returns {string} Best-matching domain
   */
  inferDomain(description) {
    const lower = description.toLowerCase();
    let bestDomain = 'General';
    let bestScore = 0;

    for (const [domain, keywords] of Object.entries(DOMAIN_KEYWORDS)) {
      const score = keywords.filter(kw => lower.includes(kw)).length;
      if (score > bestScore) {
        bestScore = score;
        bestDomain = domain;
      }
    }
    return bestDomain;
  }

  /**
   * Infer application type from description.
   * @param {string} description
   * @returns {string}
   */
  inferAppType(description) {
    const lower = description.toLowerCase();
    if (lower.includes('mobile') || lower.includes('android') || lower.includes('ios') || lower.includes('app')) return 'Mobile';
    if (lower.includes('desktop') || lower.includes('windows') || lower.includes('macos')) return 'Desktop';
    if (lower.includes('enterprise') || lower.includes('erp') || lower.includes('crm')) return 'Enterprise';
    return 'Web';
  }

  /**
   * Get few-shot examples matching the domain.
   * Returns 2-3 training_text strings for prompt context.
   * @param {string} domain
   * @param {number} count
   * @returns {Array<{training_text, summary}>}
   */
  getFewShotExamples(domain, count = 2) {
    this._load();
    if (!this._cache?.length) return [];

    const domainMatches = this._cache.filter(row =>
      row.domain && row.domain.toLowerCase().includes(domain.toLowerCase())
    );

    const pool = domainMatches.length >= count ? domainMatches : this._cache;
    const selected = [];
    const used = new Set();

    while (selected.length < count && selected.length < pool.length) {
      const idx = Math.floor(Math.random() * pool.length);
      if (!used.has(idx)) {
        used.add(idx);
        const row = pool[idx];
        if (row.training_text && row.summary) {
          selected.push({
            training_text: row.training_text.slice(0, 500),
            summary: row.summary.slice(0, 200),
            domain: row.domain,
            application_type: row.application_type
          });
        }
      }
    }

    return selected;
  }

  /**
   * Get all available domains in the dataset.
   */
  getDomains() {
    this._load();
    const domains = new Set((this._cache || []).map(r => r.domain).filter(Boolean));
    return Array.from(domains);
  }
}

export default new CSVService();
