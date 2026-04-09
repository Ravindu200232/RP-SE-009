'use client';

import { useEffect, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  RiCloseLine,
  RiFilePdf2Line,
  RiImageLine,
  RiMicLine,
  RiSendPlane2Line,
  RiStopLine,
} from 'react-icons/ri';
import { HiPaperClip } from 'react-icons/hi2';
import VoiceQuestionCard from './VoiceQuestionCard';
import { createSpeechRecognition, getSpeechRecognitionCtor, stopMediaStream } from '../lib/speech';

const MAX_FILES = 5;
const ACCEPTED_DROPZONE_TYPES = {
  'image/*': [],
  'application/pdf': [],
  'audio/*': [],
  'text/plain': [],
  'text/markdown': [],
  'application/json': [],
  'text/csv': [],
};
const FILE_INPUT_ACCEPT = 'image/*,application/pdf,audio/*,text/plain,text/markdown,application/json,text/csv';

function joinPrompt(baseText, transcript) {
  if (!transcript) {
    return baseText;
  }
  if (!baseText) {
    return transcript;
  }
  return `${baseText}\n\nVoice note:\n${transcript}`;
}

export default function VoiceChatInterface({
  phase,
  messages,
  questions,
  knownInfo = {},
  onStart,
  onAnswers,
  idle = false,
  srsTokens = '',
}) {
  const [prompt, setPrompt] = useState('');
  const [files, setFiles] = useState([]);
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const [liveTranscript, setLiveTranscript] = useState('');
  const endRef = useRef(null);
  const recognitionRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const isRecordingRef = useRef(false);
  const promptBeforeRecordingRef = useRef('');
  const finalTranscriptRef = useRef('');

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, srsTokens]);

  useEffect(() => {
    setAnswers({});
    setSubmitted(false);
  }, [questions]);

  useEffect(() => () => {
    recognitionRef.current?.stop?.();
    if (mediaRecorderRef.current?.state !== 'inactive') {
      mediaRecorderRef.current?.stop?.();
    }
    stopMediaStream(streamRef.current);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: ACCEPTED_DROPZONE_TYPES,
    onDrop: (acceptedFiles) => setFiles((previous) => [...previous, ...acceptedFiles].slice(0, MAX_FILES)),
    noClick: true,
  });

  const busy = ['processing', 'generating'].includes(phase);

  const removeFile = (index) => {
    setFiles((previous) => previous.filter((_, fileIndex) => fileIndex !== index));
  };

  const stopRecording = () => {
    isRecordingRef.current = false;
    setIsRecording(false);
    recognitionRef.current?.stop?.();
    recognitionRef.current = null;

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      return;
    }

    stopMediaStream(streamRef.current);
    streamRef.current = null;
  };

  const startRecording = async () => {
    if (busy) {
      return;
    }

    if (!navigator?.mediaDevices?.getUserMedia) {
      setVoiceError('Live recording is not available in this browser.');
      return;
    }
    if (typeof MediaRecorder === 'undefined') {
      setVoiceError('Audio recording is not available in this browser.');
      return;
    }

    try {
      setVoiceError('');
      promptBeforeRecordingRef.current = prompt.trim();
      finalTranscriptRef.current = '';
      setLiveTranscript('');

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const preferredMimeType = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/ogg',
      ].find((mimeType) => MediaRecorder.isTypeSupported?.(mimeType));

      const recorder = new MediaRecorder(stream, preferredMimeType ? { mimeType: preferredMimeType } : undefined);
      audioChunksRef.current = [];
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data?.size) {
          audioChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const mimeType = recorder.mimeType || 'audio/webm';
        const extension = mimeType.includes('ogg') ? 'ogg' : mimeType.includes('mp4') ? 'm4a' : 'webm';
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        if (blob.size) {
          const file = new File([blob], `voice-note-${Date.now()}.${extension}`, { type: mimeType });
          setFiles((previous) => [...previous, file].slice(0, MAX_FILES));
        }
        audioChunksRef.current = [];
        mediaRecorderRef.current = null;
        stopMediaStream(streamRef.current);
        streamRef.current = null;
      };
      recorder.start();

      const recognitionSupported = !!getSpeechRecognitionCtor();
      if (!recognitionSupported) {
        setVoiceError('Live transcription is not available here. The audio note will still be attached when you stop recording.');
      }

      const recognition = recognitionSupported
        ? createSpeechRecognition({ continuous: true, interimResults: true })
        : null;
      recognitionRef.current = recognition;
      recognition?.addEventListener('result', (event) => {
        let finalTranscript = finalTranscriptRef.current;
        let interimTranscript = '';

        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const transcript = event.results[index][0]?.transcript?.trim();
          if (!transcript) {
            continue;
          }
          if (event.results[index].isFinal) {
            finalTranscript = `${finalTranscript} ${transcript}`.trim();
          } else {
            interimTranscript = `${interimTranscript} ${transcript}`.trim();
          }
        }

        finalTranscriptRef.current = finalTranscript;
        const combinedTranscript = [finalTranscript, interimTranscript].filter(Boolean).join(' ').trim();
        setLiveTranscript(combinedTranscript);
        setPrompt(joinPrompt(promptBeforeRecordingRef.current, combinedTranscript));
      });
      recognition?.addEventListener('error', (event) => {
        setVoiceError(event.error === 'not-allowed' ? 'Microphone permission was denied.' : 'Voice recognition failed. The audio file will still be attached.');
      });
      recognition?.addEventListener('end', () => {
        if (isRecordingRef.current) {
          try {
            recognition.start();
          } catch {
            // Browser may already be stopping the recognition session.
          }
        }
      });
      recognition?.start();

      isRecordingRef.current = true;
      setIsRecording(true);
    } catch (error) {
      setVoiceError(error.message || 'Could not start recording.');
      stopRecording();
    }
  };

  const send = () => {
    if (!prompt.trim() && files.length === 0) {
      return;
    }
    onStart(prompt.trim(), files);
    setPrompt('');
    setFiles([]);
    setAnswers({});
    setSubmitted(false);
    setVoiceError('');
    setLiveTranscript('');
  };

  const onKey = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  const fileIcon = (file) => {
    if (file.type?.startsWith('image/')) {
      return <RiImageLine className="text-cyan-400" />;
    }
    if (file.type === 'application/pdf') {
      return <RiFilePdf2Line className="text-red-400" />;
    }
    if (file.type?.startsWith('audio/')) {
      return <RiMicLine className="text-green-400" />;
    }
    return <HiPaperClip className="text-slate-400" />;
  };

  return (
    <div className="flex flex-col h-full relative" {...getRootProps()}>
      <input {...getInputProps()} />

      {isDragActive && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-purple-900/80 backdrop-blur-sm border-2 border-dashed border-purple-400 rounded-xl m-2">
          <div className="text-center">
            <div className="text-5xl mb-2">Files</div>
            <p className="text-purple-200 font-semibold">Drop files here</p>
            <p className="text-purple-400 text-sm">Images, PDFs, audio, and text</p>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4">
        {idle && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 opacity-40">
            <div className="text-4xl mb-2 animate-float">SRS</div>
            <p className="text-slate-400 text-sm">Describe your idea, drop a file, or record your voice below</p>
          </div>
        )}

        {messages.map((message) => {
          if (message.role === 'question' && message.questions) {
            return (
              <div key={message.id} className="animate-slide-up">
                <VoiceQuestionCard
                  questions={message.questions}
                  knownInfo={knownInfo}
                  answers={answers}
                  setAnswers={setAnswers}
                  onSubmit={() => {
                    setSubmitted(true);
                    onAnswers({ ...knownInfo, ...answers });
                  }}
                  submitted={submitted}
                />
              </div>
            );
          }

          return (
            <div key={message.id} className={`flex gap-2.5 animate-slide-up ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {message.role !== 'user' && (
                <div className="w-7 h-7 rounded-lg btn-primary flex-shrink-0 flex items-center justify-center text-xs mt-0.5">AI</div>
              )}
              <div className={`max-w-[80%] px-4 py-3 text-sm leading-relaxed ${message.role === 'user' ? 'bubble-user text-white' : 'bubble-agent text-slate-200'} ${message.isError ? '!border-red-500/30 !bg-red-900/10' : ''}`}>
                {message.files?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {message.files.map((fileName, index) => (
                      <span key={`${fileName}-${index}`} className="px-2 py-0.5 rounded-full bg-white/10 text-xs">
                        File {fileName}
                      </span>
                    ))}
                  </div>
                )}
                <MessageText text={message.content} />
              </div>
              {message.role === 'user' && (
                <div className="w-7 h-7 rounded-lg bg-slate-700 flex-shrink-0 flex items-center justify-center text-xs mt-0.5">You</div>
              )}
            </div>
          );
        })}

        {phase === 'generating' && !srsTokens && (
          <div className="flex gap-2.5 justify-start animate-slide-up">
            <div className="w-7 h-7 rounded-lg btn-primary flex-shrink-0 flex items-center justify-center text-xs">AI</div>
            <div className="bubble-agent px-4 py-3">
              <span className="flex items-center gap-2 text-sm text-slate-400">
                <span className="flex gap-1">
                  {[0, 150, 300].map((delay) => (
                    <span key={delay} className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: `${delay}ms` }} />
                  ))}
                </span>
                DeepSeek generating IEEE SRS...
              </span>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div className="p-3 border-t border-white/5 shrink-0">
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {files.map((file, index) => (
              <div key={`${file.name}-${index}`} className="flex items-center gap-1.5 px-2 py-1 rounded-lg glass border border-white/10 text-xs">
                {fileIcon(file)}
                <span className="text-slate-300 max-w-[120px] truncate">{file.name}</span>
                <button onClick={() => removeFile(index)} className="text-slate-500 hover:text-red-400">
                  <RiCloseLine />
                </button>
              </div>
            ))}
          </div>
        )}

        {(isRecording || liveTranscript || voiceError) && (
          <div className="mb-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
            {isRecording && <p className="text-emerald-300">Live voice recording is on. Speak now, then press stop to attach the audio.</p>}
            {liveTranscript && <p className="mt-1 text-slate-400">Live transcript: {liveTranscript}</p>}
            {voiceError && <p className="mt-1 text-amber-300">{voiceError}</p>}
          </div>
        )}

        <div className="flex gap-2 items-end">
          <label className="w-8 h-8 rounded-xl glass glass-hover flex items-center justify-center cursor-pointer text-slate-400 hover:text-purple-400 transition-colors border border-white/5 shrink-0">
            <HiPaperClip />
            <input
              type="file"
              className="hidden"
              multiple
              accept={FILE_INPUT_ACCEPT}
              onChange={(event) => setFiles((previous) => [...previous, ...Array.from(event.target.files || [])].slice(0, MAX_FILES))}
            />
          </label>

          <button
            type="button"
            onClick={isRecording ? stopRecording : startRecording}
            disabled={busy}
            className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 border transition-all ${
              isRecording
                ? 'border-emerald-400 bg-emerald-500/15 text-emerald-200'
                : 'glass glass-hover text-slate-400 hover:text-emerald-300 border-white/5'
            } ${busy ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isRecording ? <RiStopLine /> : <RiMicLine />}
          </button>

          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={onKey}
            placeholder={idle ? 'Describe your product idea, or use the mic to say it out loud...' : 'Type anything...'}
            disabled={busy || submitted || isRecording}
            rows={1}
            className="flex-1 cosmic-input rounded-xl px-3 py-2 text-sm resize-none min-h-[36px] max-h-28"
          />

          <button
            onClick={send}
            disabled={busy || isRecording || (!prompt.trim() && files.length === 0)}
            className="w-8 h-8 rounded-xl btn-primary flex items-center justify-center shrink-0 disabled:opacity-40"
          >
            {busy
              ? <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              : <RiSendPlane2Line />}
          </button>
        </div>

        <p className="text-center text-slate-700 text-[10px] mt-1.5">
          You can type, upload an image or PDF, or record a live voice note from the browser
        </p>
      </div>
    </div>
  );
}

function MessageText({ text }) {
  if (!text) {
    return null;
  }

  return (
    <span>
      {text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => (
        part.startsWith('**') && part.endsWith('**')
          ? <strong key={index} className="text-white font-semibold">{part.slice(2, -2)}</strong>
          : <span key={index}>{part}</span>
      ))}
    </span>
  );
}
