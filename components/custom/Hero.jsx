"use client"
import Lookup from '@/data/Lookup';
import { MessagesContext } from '@/context/MessagesContext';
import { ArrowRight, Sparkles, Send, Wand2, Loader2, Zap } from 'lucide-react';
import React, { useContext, useState } from 'react';
import { useRouter } from 'next/navigation';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

function Hero() {
    const [userInput, setUserInput] = useState('');
    const [isEnhancing, setIsEnhancing] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const { setMessages } = useContext(MessagesContext);
    const router = useRouter();

    const onGenerate = async (input) => {
        if (!input.trim() || isCreating || isEnhancing) return;
        setIsCreating(true);
        const msg = { role: 'user', content: input.trim() };
        setMessages(msg);
        try {
            const response = await fetch(`${BACKEND_URL}/api/workspaces`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: [msg] })
            });
            if (!response.ok) throw new Error('Failed to create workspace');
            const data = await response.json();
            router.push('/workspace/' + data.workspaceId);
        } catch (error) {
            console.error('Error creating workspace:', error);
            alert('Failed to connect to server. Make sure the backend is running on port 5000.');
        } finally {
            setIsCreating(false);
        }
    };

    const enhancePrompt = async () => {
        if (!userInput.trim() || isEnhancing) return;
        setIsEnhancing(true);
        try {
            const response = await fetch('/api/enhance-prompt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: userInput }),
            });
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let enhancedText = '';
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.chunk) { enhancedText += data.chunk; setUserInput(enhancedText); }
                            if (data.done && data.enhancedPrompt) setUserInput(data.enhancedPrompt);
                        } catch (e) {}
                    }
                }
            }
        } catch (error) {
            console.error('Error enhancing prompt:', error);
        } finally {
            setIsEnhancing(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            onGenerate(userInput);
        }
    };

    return (
        <div className="min-h-screen bg-gray-950 relative overflow-hidden flex flex-col">
            {/* Animated background */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:14px_24px]">
                <div className="absolute left-1/2 top-0 h-[500px] w-[1000px] -translate-x-1/2 bg-[radial-gradient(circle_400px_at_50%_300px,#3b82f625,transparent)]" />
            </div>

            <div className="container mx-auto px-4 py-16 relative z-10 flex flex-col items-center gap-12">
                {/* Header */}
                <div className="text-center space-y-5">
                    <div className="inline-flex items-center gap-2 bg-blue-500/15 rounded-full px-5 py-2 border border-blue-500/25">
                        <Zap className="h-4 w-4 text-blue-400" />
                        <span className="text-blue-400 text-sm font-semibold tracking-widest uppercase">AI Website Builder</span>
                    </div>
                    <h1 className="text-5xl md:text-7xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 leading-tight">
                        Build Any App<br />with AI
                    </h1>
                    <p className="text-lg text-gray-400 max-w-xl mx-auto">
                        Describe your app → Get a fully working <strong className="text-gray-300">React + Vite</strong> project with live preview
                    </p>
                </div>

                {/* Prompt Input Box */}
                <div className="w-full max-w-3xl">
                    <div className="bg-gray-900/70 backdrop-blur-xl rounded-2xl border border-gray-700/60 shadow-[0_0_60px_rgba(59,130,246,0.08)] overflow-hidden">
                        {/* Top bar */}
                        <div className="px-5 pt-4 pb-2 flex items-center gap-2 border-b border-gray-800">
                            <Sparkles className="h-4 w-4 text-blue-400" />
                            <span className="text-sm text-gray-400 font-medium">Describe your app idea</span>
                        </div>

                        <div className="p-4">
                            <textarea
                                placeholder="e.g. Create a task manager app with drag & drop, categories, due dates, and dark mode..."
                                value={userInput}
                                onChange={(e) => setUserInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                rows={5}
                                className="w-full bg-transparent text-gray-100 placeholder-gray-600 outline-none resize-none text-base font-mono leading-relaxed"
                                disabled={isEnhancing || isCreating}
                            />
                            <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-800">
                                <span className="text-xs text-gray-600">Press Ctrl+Enter to generate</span>
                                <div className="flex gap-2">
                                    {userInput.trim() && (
                                        <button
                                            onClick={enhancePrompt}
                                            disabled={isEnhancing || isCreating}
                                            title="Improve prompt with AI"
                                            className="flex items-center gap-2 bg-emerald-600/15 hover:bg-emerald-600/25 border border-emerald-600/30 text-emerald-400 px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
                                        >
                                            {isEnhancing
                                                ? <><Loader2 className="h-4 w-4 animate-spin" /> Enhancing...</>
                                                : <><Wand2 className="h-4 w-4" /> Enhance</>
                                            }
                                        </button>
                                    )}
                                    <button
                                        onClick={() => onGenerate(userInput)}
                                        disabled={!userInput.trim() || isEnhancing || isCreating}
                                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white px-5 py-2 rounded-lg text-sm font-semibold transition-all"
                                    >
                                        {isCreating
                                            ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating...</>
                                            : <><Send className="h-4 w-4" /> Generate App</>
                                        }
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Example Suggestions */}
                <div className="w-full max-w-4xl">
                    <p className="text-xs text-gray-600 text-center mb-4 uppercase tracking-widest">Quick examples</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {Lookup?.SUGGSTIONS.map((suggestion, index) => (
                            <button
                                key={index}
                                onClick={() => setUserInput(suggestion)}
                                disabled={isCreating || isEnhancing}
                                className="group flex items-start justify-between p-4 bg-gray-900/50 hover:bg-gray-800/70 border border-gray-800 hover:border-blue-500/40 rounded-xl text-left transition-all duration-200 disabled:opacity-50"
                            >
                                <span className="text-gray-400 group-hover:text-gray-200 text-sm leading-relaxed">{suggestion}</span>
                                <ArrowRight className="h-3.5 w-3.5 text-gray-600 group-hover:text-blue-400 mt-0.5 ml-2 shrink-0 transition-colors" />
                            </button>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Hero;
