"use client"
import { MessagesContext } from '@/context/MessagesContext';
import { Loader2Icon, Send, Bot, User } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useContext, useEffect, useState, useCallback, memo } from 'react';
import Prompt from '@/data/Prompt';
import ReactMarkdown from 'react-markdown';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

const MessageItem = memo(({ msg }) => (
    <div className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
        {msg.role !== 'user' && (
            <div className="w-8 h-8 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center shrink-0 mt-1">
                <Bot className="h-4 w-4 text-purple-400" />
            </div>
        )}
        <div className={`max-w-[85%] p-3 rounded-xl text-sm leading-relaxed ${
            msg.role === 'user'
                ? 'bg-blue-600/20 border border-blue-500/30 text-blue-100'
                : 'bg-gray-800/60 border border-gray-700/50 text-gray-200'
        }`}>
            <ReactMarkdown className="prose prose-invert prose-sm max-w-none">
                {msg.content}
            </ReactMarkdown>
        </div>
        {msg.role === 'user' && (
            <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-500/30 flex items-center justify-center shrink-0 mt-1">
                <User className="h-4 w-4 text-blue-400" />
            </div>
        )}
    </div>
));

MessageItem.displayName = 'MessageItem';

function ChatView() {
    const { id } = useParams();
    const { messages, setMessages } = useContext(MessagesContext);
    const [userInput, setUserInput] = useState('');
    const [loading, setLoading] = useState(false);

    // Load workspace on mount
    const loadWorkspace = useCallback(async () => {
        if (!id) return;
        try {
            const response = await fetch(`${BACKEND_URL}/api/workspaces/${id}`);
            if (!response.ok) return;
            const data = await response.json();
            if (data.messages?.length > 0) {
                setMessages(data.messages);
            }
        } catch (err) {
            console.error('Error loading workspace:', err);
        }
    }, [id, setMessages]);

    useEffect(() => {
        loadWorkspace();
    }, [loadWorkspace]);

    // Save messages to backend
    const saveMessages = useCallback(async (msgs) => {
        if (!id) return;
        try {
            await fetch(`${BACKEND_URL}/api/workspaces/${id}/messages`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: msgs })
            });
        } catch (err) {
            console.error('Error saving messages:', err);
        }
    }, [id]);

    // Get AI response
    const getAiResponse = useCallback(async () => {
        if (!messages || messages.length === 0) return;
        setLoading(true);
        const PROMPT = JSON.stringify(messages) + Prompt.CHAT_PROMPT;

        try {
            const response = await fetch('/api/ai-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: PROMPT }),
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = '';
            const aiIdx = messages.length;

            setMessages(prev => [...(Array.isArray(prev) ? prev : [prev]), { role: 'ai', content: '' }]);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                for (const line of chunk.split('\n')) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.chunk) {
                                fullText += data.chunk;
                                setMessages(prev => {
                                    const updated = Array.isArray(prev) ? [...prev] : [prev];
                                    updated[aiIdx] = { role: 'ai', content: fullText };
                                    return updated;
                                });
                            }
                            if (data.done && data.result) {
                                fullText = data.result;
                                setMessages(prev => {
                                    const updated = Array.isArray(prev) ? [...prev] : [prev];
                                    updated[aiIdx] = { role: 'ai', content: fullText };
                                    return updated;
                                });
                            }
                        } catch (e) {}
                    }
                }
            }

            const finalMessages = [
                ...(Array.isArray(messages) ? messages : [messages]),
                { role: 'ai', content: fullText }
            ];
            await saveMessages(finalMessages);
        } catch (error) {
            console.error('Error getting AI response:', error);
        } finally {
            setLoading(false);
        }
    }, [messages, saveMessages, setMessages]);

    useEffect(() => {
        if (!messages) return;
        const msgArray = Array.isArray(messages) ? messages : [messages];
        if (msgArray.length > 0 && msgArray[msgArray.length - 1]?.role === 'user') {
            getAiResponse();
        }
    }, [messages]); // eslint-disable-line react-hooks/exhaustive-deps

    const onSend = useCallback(() => {
        if (!userInput.trim() || loading) return;
        setMessages(prev => {
            const arr = Array.isArray(prev) ? prev : (prev ? [prev] : []);
            return [...arr, { role: 'user', content: userInput.trim() }];
        });
        setUserInput('');
    }, [userInput, loading, setMessages]);

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSend();
        }
    };

    const messageList = Array.isArray(messages) ? messages : (messages ? [messages] : []);

    return (
        <div className="relative h-[85vh] flex flex-col bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-sm font-medium text-gray-300">AI Chat</span>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto scrollbar-hide p-4 space-y-4">
                {messageList.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <Bot className="h-10 w-10 text-gray-600 mb-3" />
                        <p className="text-gray-500 text-sm">Your AI assistant is ready.<br />Ask anything about your project.</p>
                    </div>
                )}
                {messageList.map((msg, index) => (
                    <MessageItem key={index} msg={msg} />
                ))}
                {loading && (
                    <div className="flex gap-3 justify-start">
                        <div className="w-8 h-8 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center shrink-0">
                            <Bot className="h-4 w-4 text-purple-400" />
                        </div>
                        <div className="bg-gray-800/60 border border-gray-700/50 rounded-xl px-4 py-3">
                            <div className="flex items-center gap-2 text-gray-400 text-sm">
                                <Loader2Icon className="animate-spin h-4 w-4" />
                                <span>Thinking...</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Input */}
            <div className="border-t border-gray-800 p-3 bg-gray-900/80">
                <div className="flex gap-2 items-end">
                    <textarea
                        placeholder="Ask about your project..."
                        value={userInput}
                        onChange={(e) => setUserInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        rows={2}
                        className="flex-1 bg-gray-800/60 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 text-sm outline-none focus:border-blue-500/50 transition-colors resize-none"
                    />
                    <button
                        onClick={onSend}
                        disabled={!userInput.trim() || loading}
                        className="flex items-center justify-center bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white p-3 rounded-xl transition-colors shrink-0"
                    >
                        <Send className="h-4 w-4" />
                    </button>
                </div>
            </div>
        </div>
    );
}

export default ChatView;
