'use client';
import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';

const AGENT_SERVICE_URL = 'http://localhost:5000';

export function useSocket(jobId: string | null) {
  const socketRef = useRef<Socket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const socket = io(AGENT_SERVICE_URL, { transports: ['websocket', 'polling'] });
    socketRef.current = socket;

    socket.on('connect', () => {
      setConnected(true);
      if (jobId) socket.emit('join:job', jobId);
    });

    socket.on('disconnect', () => setConnected(false));

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, []);

  // Re-join room when jobId changes
  useEffect(() => {
    if (jobId && socketRef.current?.connected) {
      socketRef.current.emit('join:job', jobId);
    }
  }, [jobId]);

  const on = (event: string, handler: (...args: any[]) => void) => {
    socketRef.current?.on(event, handler);
    return () => { socketRef.current?.off(event, handler); };
  };

  const off = (event: string, handler: (...args: any[]) => void) => {
    socketRef.current?.off(event, handler);
  };

  return { socket: socketRef.current, connected, on, off };
}
