import React from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from './components/ui/provider.jsx';
import './index.css';
import { App } from './App.jsx';
createRoot(document.getElementById('root')).render(<React.StrictMode><Provider><App /></Provider></React.StrictMode>);
