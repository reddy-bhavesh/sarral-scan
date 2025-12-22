import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { useAuth } from './AuthContext';

interface SSEContextType {
    isConnected: boolean;
    lastEvent: { type: string, data: any } | null;
    addEventListener: (type: string, callback: (data: any) => void) => void;
    removeEventListener: (type: string, callback: (data: any) => void) => void;
}

const SSEContext = createContext<SSEContextType | undefined>(undefined);

export const SSEProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isAuthenticated } = useAuth();
    const [isConnected, setIsConnected] = useState(false);
    const [lastEvent, setLastEvent] = useState<{ type: string, data: any } | null>(null);
    const eventSourceRef = useRef<EventSource | null>(null);
    const listenersRef = useRef<Map<string, Set<(data: any) => void>>>(new Map());
    const retryTimeoutRef = useRef<any>(null);

    // Function to notify listeners
    const notifyListeners = (type: string, data: any) => {
        const listeners = listenersRef.current.get(type);
        if (listeners) {
            listeners.forEach(callback => callback(data));
        }
    };

    const connectSSE = () => {
        // Check localStorage first (persistent), then sessionStorage (temporary)
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');
        if (!token) return;

        // Prevent multiple connections
        if (eventSourceRef.current?.readyState === EventSource.OPEN) return;
        if (eventSourceRef.current?.readyState === EventSource.CONNECTING) return;

        const baseUrl = import.meta.env.VITE_API_URL || '';
        const url = `${baseUrl}/events/stream?token=${token}`;
        
        console.log("[SSE] Connecting to:", url);
        const es = new EventSource(url);
        eventSourceRef.current = es;

        es.onopen = () => {
            console.log("[SSE] Connected");
            setIsConnected(true);
        };

        es.onmessage = (event) => {
            // This catches events without a specific type (message)
            console.log("[SSE] Message Received:", event.data);
        };

        es.onerror = (err) => {
            console.error("[SSE] Error:", err);
            es.close();
            setIsConnected(false);
            eventSourceRef.current = null;
            
            // Retry logic
            if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
            retryTimeoutRef.current = setTimeout(() => {
                if (isAuthenticated) connectSSE();
            }, 5000);
        };

        // Listen for specific event types
        // We need to override the default event handling or just add listeners for known types?
        // EventSource API requires adding listeners for specific event names.
        // But since we want to be dynamic, we can't add them all upfront unless we know them.
        // However, standard EventSource doesn't have a "catch-all" for named events.
        // Wait, standard SSE sends `event: type`. If we don't addEventListener for `type`, we miss it.
        // The `onmessage` only handles `event: message` (or no event field).
        
        // WORKAROUND:
        // We know the event types we care about: SCAN_UPDATE, CONNECTED.
        // We can add specific listeners for these.
        // Ideally, the backend updates us. 
        // For a generic solution, we might need a fixed set or a wrapper.
        // Let's add listeners for the known types.
        
        const knownEvents = ["SCAN_UPDATE", "CONNECTED"];
        
        knownEvents.forEach(type => {
            es.addEventListener(type, (event: any) => {
                try {
                    const parsedData = JSON.parse(event.data);
                    console.log(`[SSE] ${type}:`, parsedData);
                    setLastEvent({ type, data: parsedData });
                    notifyListeners(type, parsedData);
                } catch (e) {
                    console.error(`[SSE] Failed to parse ${type} data`, e);
                }
            });
        });
    };

    const cleanup = () => {
        if (eventSourceRef.current) {
            console.log("[SSE] Closing connection");
            eventSourceRef.current.close();
            eventSourceRef.current = null;
            setIsConnected(false);
        }
        if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
    };

    useEffect(() => {
        if (isAuthenticated) {
            connectSSE();
        } else {
            cleanup();
        }

        return cleanup;
    }, [isAuthenticated]);

    const addEventListener = (type: string, callback: (data: any) => void) => {
        if (!listenersRef.current.has(type)) {
            listenersRef.current.set(type, new Set());
        }
        listenersRef.current.get(type)?.add(callback);
    };

    const removeEventListener = (type: string, callback: (data: any) => void) => {
        listenersRef.current.get(type)?.delete(callback);
    };

    return (
        <SSEContext.Provider value={{ isConnected, lastEvent, addEventListener, removeEventListener }}>
            {children}
        </SSEContext.Provider>
    );
};

export const useSSE = () => {
    const context = useContext(SSEContext);
    if (context === undefined) {
        throw new Error('useSSE must be used within a SSEProvider');
    }
    return context;
};
