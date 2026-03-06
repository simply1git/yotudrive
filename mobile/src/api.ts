import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

// For production, use the Render backend. For local dev, you can fallback to localhost.
const API_BASE = 'https://yotudrive.onrender.com';

const TOKEN_KEY = 'yotu_bearer_mobile';

export const api = axios.create({
    baseURL: API_BASE,
    headers: { 'Content-Type': 'application/json' },
});

// Setup interceptors
api.interceptors.request.use(async (config) => {
    const token = await AsyncStorage.getItem(TOKEN_KEY);
    if (token) config.headers['Authorization'] = `Bearer ${token}`;
    return config;
});

export const authApi = {
    devLogin: async (email: string) => {
        const res = await api.post('/api/auth/dev/login', { email });
        await AsyncStorage.setItem(TOKEN_KEY, res.data.session.bearer);
        return res.data;
    },
    logout: async () => {
        try { await api.post('/api/auth/logout'); } catch (e) { }
        await AsyncStorage.removeItem(TOKEN_KEY);
    },
    getSession: async () => {
        const res = await api.get('/api/auth/session');
        return res.data;
    }
};

export const filesApi = {
    list: async () => {
        const res = await api.get('/api/me/files');
        return res.data;
    }
};

export const jobsApi = {
    list: async () => {
        const res = await api.get('/api/me/jobs', { params: { limit: 20 } });
        return res.data;
    }
};
