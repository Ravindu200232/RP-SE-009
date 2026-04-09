export function getSpeechRecognitionCtor() {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function getSpeechSynthesis() {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.speechSynthesis || null;
}

export function createSpeechRecognition(options = {}) {
  const Ctor = getSpeechRecognitionCtor();
  if (!Ctor) {
    return null;
  }

  const recognition = new Ctor();
  recognition.lang = options.lang || 'en-US';
  recognition.interimResults = options.interimResults ?? true;
  recognition.continuous = options.continuous ?? true;
  recognition.maxAlternatives = 1;
  return recognition;
}

export function stopMediaStream(stream) {
  stream?.getTracks?.().forEach((track) => track.stop());
}

export function cancelSpeech() {
  const synth = getSpeechSynthesis();
  if (!synth) {
    return;
  }
  synth.cancel();
}

function pickVoice(synth, lang = 'en-US') {
  const voices = synth.getVoices?.() || [];
  if (!voices.length) {
    return null;
  }

  const normalizedLang = String(lang).toLowerCase();
  return (
    voices.find((voice) => String(voice.lang || '').toLowerCase() === normalizedLang)
    || voices.find((voice) => String(voice.lang || '').toLowerCase().startsWith(normalizedLang.split('-')[0]))
    || voices.find((voice) => !voice.localService)
    || voices[0]
  );
}

export function speakText(text, options = {}) {
  const synth = getSpeechSynthesis();
  if (!synth || !text) {
    return false;
  }

  try {
    cancelSpeech();
    if (synth.paused) {
      synth.resume();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = options.rate ?? 1;
    utterance.pitch = options.pitch ?? 1;
    utterance.lang = options.lang || 'en-US';

    const selectedVoice = pickVoice(synth, utterance.lang);
    if (selectedVoice) {
      utterance.voice = selectedVoice;
    }

    window.setTimeout(() => {
      try {
        synth.speak(utterance);
      } catch {
        // Some browsers still reject speech after feature detection.
      }
    }, 0);

    return true;
  } catch {
    return false;
  }
}

function normalizeText(value = '') {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const ORDINAL_LOOKUP = {
  first: 0,
  one: 0,
  'option 1': 0,
  second: 1,
  two: 1,
  'option 2': 1,
  third: 2,
  three: 2,
  'option 3': 2,
  fourth: 3,
  four: 3,
  'option 4': 3,
  fifth: 4,
  five: 4,
  'option 5': 4,
};

export function matchSpokenOptions(transcript, options, multi = false) {
  const normalizedTranscript = normalizeText(transcript);
  if (!normalizedTranscript || !Array.isArray(options) || !options.length) {
    return multi ? [] : null;
  }

  const matches = [];

  options.forEach((option, index) => {
    const normalizedOption = normalizeText(option);
    if (!normalizedOption) {
      return;
    }

    if (
      normalizedTranscript.includes(normalizedOption) ||
      normalizedTranscript.includes(`${index + 1}`) ||
      Object.entries(ORDINAL_LOOKUP).some(([phrase, optionIndex]) => optionIndex === index && normalizedTranscript.includes(phrase))
    ) {
      matches.push(option);
    }
  });

  if (multi) {
    return [...new Set(matches)];
  }

  return matches[0] || null;
}
