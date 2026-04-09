/**
 * SRSBuilderAgent — Main orchestrator for the SRS generation pipeline.
 *
 * Session-based flow:
 *  Step 1: Process multimodal inputs (MiniCPM-O)
 *  Step 2: Analyze gaps in description (DeepSeek)
 *  Step 3: Ask user targeted questions
 *  Step 4: Generate complete IEEE SRS JSON (DeepSeek)
 *  Step 5: Return JSON + prepare for PDF export
 */

import { v4 as uuidv4 } from 'uuid';
import miniCPMService from './miniCPMService.js';
import deepSeekService from './deepSeekEnhancedService.js';
import csvService from './csvService.js';
import sessionArtifactService from './sessionArtifactService.js';
import srsValidationService from './srsValidationService.js';

// In-memory session store (replace with Redis/DB in production)
const sessions = new Map();

class SRSBuilderAgent {
  /**
   * Create a new session.
   */
  createSession() {
    const sessionId = uuidv4();
    sessions.set(sessionId, {
      id: sessionId,
      status: 'created',
      projectDescription: '',
      knownInfo: {},
      pendingQuestions: [],
      answeredQuestions: [],
      questionPlanPath: null,
      srsJson: null,
      srsJsonPath: null,
      validationReport: null,
      validationReportPath: null,
      logs: [],
      createdAt: Date.now()
    });
    return sessionId;
  }

  /**
   * Step 1 & 2: Process initial input and analyze gaps.
   * Emits live logs via Socket.IO.
   */
  async processInitialInput(sessionId, textPrompt, files, io) {
    const session = sessions.get(sessionId);
    if (!session) throw new Error('Session not found');

    session.status = 'processing';
    const log = (message, level = 'info') => {
      const entry = { message, level, timestamp: new Date().toISOString() };
      session.logs.push(entry);
      io.to(sessionId).emit('log', entry);
    };

    try {
      // ── Step 1: MiniCPM processes all inputs ──────────────────────────────
      log('🚀 Starting up...', 'info');
      log('📡 Reading everything you shared...', 'info');

      const projectDescription = await miniCPMService.processInputs(textPrompt, files, log);
      session.projectDescription = projectDescription;

      log(`💡 Got it! Understanding your idea...`, 'success');

      // ── Infer domain and app type from CSV service ─────────────────────────
      const inferredDomain = csvService.inferDomain(projectDescription);
      log(`🌐 This looks like a ${inferredDomain} type of app`, 'info');

      // ── Get few-shot examples from training CSV ────────────────────────────
      log('📚 Finding similar app examples to help build your plan...', 'info');
      const fewShot = csvService.getFewShotExamples(inferredDomain, 2);
      log(`📚 Found ${fewShot.length} similar app example${fewShot.length !== 1 ? 's' : ''}`, 'success');
      session.fewShot = fewShot;

      // ── Step 2: DeepSeek analyzes gaps ────────────────────────────────────
      log('🔬 Checking what other details we need from you...', 'info');
      const gapAnalysis = await deepSeekService.analyzeGaps(projectDescription, fewShot, log);

      // Merge inferred values with gap analysis — always Web/MERN
      const knownInfo = {
        domain: inferredDomain,
        application_type: 'Web',
        database_type: 'MongoDB',
        performance_target: '< 2 seconds',
        ...gapAnalysis.known
      };
      session.knownInfo = knownInfo;

      // ── Step 3: Determine what questions to ask ────────────────────────────
      const questions = deepSeekService.getUnansweredQuestions(knownInfo, gapAnalysis.questions || []);
      session.pendingQuestions = questions;
      const questionPlan = {
        sessionId,
        createdAt: new Date().toISOString(),
        planner: 'deepseek-template-interview',
        skills: ['human-srs-interviewer', 'ieee-srs-writer'],
        projectDescription,
        summary: gapAnalysis.summary || projectDescription.slice(0, 200),
        knownInfo,
        templateSummary: deepSeekService.getTemplateSummary(1600),
        questions,
        selectedQuestionKeys: questions.map((question) => question.key),
        selectedAnswers: [],
      };
      session.questionPlanPath = await sessionArtifactService.writeQuestionPlan(sessionId, questionPlan);

      log(`❓ ${questions.length} quick question${questions.length !== 1 ? 's' : ''} needed to complete your plan`, 'info');

      log(`Ordered question plan saved to temp file: ${session.questionPlanPath}`, 'info');

      session.status = 'awaiting_answers';

      return {
        sessionId,
        summary: gapAnalysis.summary || projectDescription.slice(0, 200),
        knownInfo,
        questions,
        questionPlanPath: session.questionPlanPath,
        logs: session.logs
      };

    } catch (err) {
      log(`❌ Error in initial processing: ${err.message}`, 'error');
      session.status = 'error';
      throw err;
    }
  }

  /**
   * Step 4: User has answered questions. Generate full SRS.
   */
  async generateWithAnswers(sessionId, answers, io) {
    const session = sessions.get(sessionId);
    if (!session) throw new Error('Session not found');

    session.status = 'generating';
    const log = (message, level = 'info') => {
      const entry = { message, level, timestamp: new Date().toISOString() };
      session.logs.push(entry);
      io.to(sessionId).emit('log', entry);
    };

    try {
      // Merge answers with known info
      const collectedInfo = { ...session.knownInfo, ...answers };
      session.knownInfo = collectedInfo;
      const storedQuestionPlan = await sessionArtifactService.readQuestionPlan(sessionId);
      const orderedQuestions = storedQuestionPlan?.questions?.length
        ? storedQuestionPlan.questions
        : session.pendingQuestions;
      session.answeredQuestions = orderedQuestions.map((question) => ({
        key: question.key,
        question: question.question,
        answer: answers[question.key] ?? null,
      }));

      if (storedQuestionPlan) {
        await sessionArtifactService.writeQuestionPlan(sessionId, {
          ...storedQuestionPlan,
          answeredAt: new Date().toISOString(),
          selectedQuestionKeys: orderedQuestions.map((question) => question.key),
          selectedAnswers: session.answeredQuestions,
        });
      }

      log('✅ All answers collected — building your app plan now!', 'success');
      log(`🏗️ Creating full specification for: ${collectedInfo.project_name || 'your app'}`, 'info');
      log(`   Type: ${collectedInfo.domain || 'Web'} app | Stack: MERN + Microservices`, 'info');
      log(`   Features: ${collectedInfo.core_features?.slice(0, 80) || 'Multiple features'}`, 'info');

      // Generate SRS with live token streaming
      let srsTokens = '';
      const srs = await deepSeekService.generateSRS(
        session.projectDescription,
        collectedInfo,
        session.fewShot || [],
        log,
        (token) => {
          srsTokens += token;
          io.to(sessionId).emit('srs:token', { token });
        }
      );

      const validated = await srsValidationService.validateAndRepair({
        srs,
        projectDescription: session.projectDescription,
        collectedInfo,
        sessionId,
        logFn: log,
      });

      session.srsJson = validated.srs;
      session.validationReport = validated.report;
      session.srsJsonPath = await sessionArtifactService.writeSrsJson(sessionId, validated.srs);
      session.validationReportPath = await sessionArtifactService.writeValidationReport(sessionId, validated.report);
      if (storedQuestionPlan) {
        await sessionArtifactService.writeQuestionPlan(sessionId, {
          ...storedQuestionPlan,
          completedAt: new Date().toISOString(),
          srsJsonPath: session.srsJsonPath,
          validationReportPath: session.validationReportPath,
          validationStatus: validated.report.status,
        });
      }
      session.status = 'complete';

      log('🎉 IEEE SRS JSON generation complete!', 'success');
      log(`📊 Generated: ${JSON.stringify(srs).length} chars | ${srs.sections?.system_features?.length || 0} features`, 'success');

      log(`Validation status: ${validated.report.status} | completeness ${validated.report.completeness_score}`, 'success');
      log(`Final rechecked SRS size: ${JSON.stringify(validated.srs).length} chars`, 'success');

      // Emit completion event
      io.to(sessionId).emit('srs:complete', { srs: validated.srs });

      return { srs: validated.srs, logs: session.logs, validation: validated.report };

    } catch (err) {
      log(`❌ SRS generation error: ${err.message}`, 'error');
      session.status = 'error';
      throw err;
    }
  }

  /**
   * Get session data.
   */
  getSession(sessionId) {
    return sessions.get(sessionId);
  }

  /**
   * Get SRS JSON for a session.
   */
  getSRS(sessionId) {
    return sessions.get(sessionId)?.srsJson;
  }

  /**
   * Clear old sessions (cleanup).
   */
  cleanupOldSessions() {
    const TTL = 2 * 60 * 60 * 1000; // 2 hours
    const now = Date.now();
    for (const [id, session] of sessions.entries()) {
      if (now - session.createdAt > TTL) sessions.delete(id);
    }
  }
}

export default new SRSBuilderAgent();
