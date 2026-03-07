import React, { useState, useEffect } from 'react';
import {
  StyleSheet, Text, View, TextInput, TouchableOpacity,
  FlatList, SafeAreaView, StatusBar, ActivityIndicator,
  Platform
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { authApi, filesApi, jobsApi } from './src/api';

// Theme constants
const COLORS = {
  bg: '#02040a',
  surface: '#050814',
  card: '#0a0f1f',
  accent1: '#4f46e5', // Indigo
  accent2: '#06b6d4', // Cyan
  text1: '#f8fafc',
  text2: '#94a3b8',
  border: 'rgba(255,255,255,0.06)',
  borderGlow: 'rgba(79,70,229,0.1)',
  success: '#10b981',
  error: '#f87171',
  warning: '#fbbf24',
};

export default function App() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);
  const [tab, setTab] = useState('library'); 

  useEffect(() => {
    authApi.getSession().then(res => {
      setUser(res.user);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <View style={[styles.container, styles.center]}>
      <ActivityIndicator color={COLORS.accent2} size="large" />
    </View>
  );

  if (!user) return <LoginScreen onLogin={setUser} />

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={COLORS.bg} />

      <View style={styles.header}>
        <View style={styles.headerTitleGroup}>
           <Text style={styles.headerTitle}>YOTU</Text>
           <Text style={[styles.headerTitle, { color: COLORS.accent2 }]}>DRIVE</Text>
        </View>
        <TouchableOpacity style={styles.headerIcon}>
           <Ionicons name="notifications-outline" size={20} color={COLORS.text2} />
        </TouchableOpacity>
      </View>

      <View style={styles.content}>
        {tab === 'library' && <LibraryScreen />}
        {tab === 'jobs' && <JobsScreen />}
        {tab === 'profile' && <ProfileScreen user={user} onLogout={() => setUser(null)} />}
      </View>

      {/* Glass Tab Bar */}
      <View style={styles.tabBar}>
        <TabButton icon="grid-outline" label="Vault" active={tab === 'library'} onPress={() => setTab('library')} />
        <TabButton icon="swap-horizontal-outline" label="Transfers" active={tab === 'jobs'} onPress={() => setTab('jobs')} />
        <TabButton icon="finger-print-outline" label="Account" active={tab === 'profile'} onPress={() => setTab('profile')} />
      </View>
    </SafeAreaView>
  );
}

// -----------------------------------------------------------------------------
// Screens
// -----------------------------------------------------------------------------
function LoginScreen({ onLogin }: { onLogin: (u: any) => void }) {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email) return;
    setLoading(true);
    try {
      const res = await authApi.devLogin(email);
      onLogin(res.user);
    } catch (e: any) {
      alert('Authentication failure: ' + (e.response?.data?.error?.message || e.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, styles.center, { padding: 30 }]}>
      <View style={styles.loginGlow} />
      <View style={styles.card}>
        <View style={styles.iconCircle}>
           <Ionicons name="flash" size={32} color={COLORS.accent2} />
        </View>
        <Text style={styles.title}>Cosmos Uplink</Text>
        <Text style={styles.subtitle}>Enter credentials to establish secure connection.</Text>

        <TextInput
          style={styles.input}
          placeholder="identity@yotudrive.com"
          placeholderTextColor="rgba(148,163,184,0.4)"
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />

        <TouchableOpacity 
          style={[styles.button, !email && { opacity: 0.5 }]} 
          onPress={handleLogin} 
          disabled={loading || !email}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={styles.buttonText}>Engage Portal</Text>
              <Ionicons name="arrow-forward" size={18} color="#fff" />
            </View>
          )}
        </TouchableOpacity>
      </View>
      <Text style={[styles.emptyText, { marginTop: 40 }]}>SYSTEM v2.0 • ENCRYPTED</Text>
    </View>
  );
}

function LibraryScreen() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    filesApi.list().then(res => { setFiles(res.files); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator color={COLORS.accent2} /></View>

  return (
    <FlatList
      data={files}
      keyExtractor={(item: any) => item.id}
      contentContainerStyle={{ padding: 20 }}
      ListEmptyComponent={<Text style={styles.emptyText}>Vault is empty. Synchronize files from workstation.</Text>}
      renderItem={({ item }) => (
        <TouchableOpacity style={styles.listItem}>
          <View style={[styles.listIcon, { backgroundColor: 'rgba(6,182,212,0.1)' }]}>
             <Ionicons name="document-text-outline" size={24} color={COLORS.accent2} />
          </View>
          <View style={{ marginLeft: 16, flex: 1 }}>
            <Text style={styles.listTitle} numberOfLines={1}>{item.file_name}</Text>
            <Text style={styles.listSubtitle}>{item.video_id === 'pending' ? 'Indexing...' : item.video_id}</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={COLORS.border} />
        </TouchableOpacity>
      )}
    />
  );
}

function JobsScreen() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchJobs = () => jobsApi.list().then(res => { setJobs(res.jobs); setLoading(false); }).catch(() => setLoading(false));
    fetchJobs();
    const int = setInterval(fetchJobs, 3000);
    return () => clearInterval(int);
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator color={COLORS.accent2} /></View>

  return (
    <FlatList
      data={jobs}
      keyExtractor={(item: any) => item.id}
      contentContainerStyle={{ padding: 20 }}
      ListEmptyComponent={<Text style={styles.emptyText}>No active transmissions.</Text>}
      renderItem={({ item }) => (
        <View style={styles.listItem}>
          <View style={styles.listIcon}>
             <Ionicons 
               name={item.status === 'done' ? "shield-checkmark" : item.status === 'failed' ? "alert-circle" : "sync"} 
               size={24} 
               color={item.status === 'done' ? COLORS.success : item.status === 'failed' ? COLORS.error : COLORS.accent1} 
             />
          </View>
          <View style={{ marginLeft: 16, flex: 1 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
               <Text style={styles.listTitle} numberOfLines={1}>{item.kind.replace('_', ' ').toUpperCase()}</Text>
               <Text style={[styles.listTitle, { fontSize: 13, color: COLORS.accent1 }]}>{item.progress}%</Text>
            </View>
            <View style={styles.progressBarBg}>
               <View style={[styles.progressBar, { width: `${item.progress}%`, backgroundColor: item.status === 'done' ? COLORS.success : COLORS.accent1 }]} />
            </View>
            <Text style={styles.listSubtitle} numberOfLines={1}>{item.message}</Text>
          </View>
        </View>
      )}
    />
  );
}

function ProfileScreen({ user, onLogout }: { user: any, onLogout: () => void }) {
  return (
    <View style={[styles.center, { padding: 30 }]}>
      <View style={styles.profileGlow} />
      <View style={[styles.iconCircle, { width: 100, height: 100, borderRadius: 50, marginBottom: 20, borderColor: COLORS.accent1 }]}>
         <Ionicons name="person" size={50} color={COLORS.accent1} />
      </View>
      <Text style={styles.title}>{user.email}</Text>
      <View style={[styles.badge, { backgroundColor: COLORS.accent1 + '20' }]}>
         <Text style={[styles.badgeText, { color: COLORS.accent1 }]}>{user.role.toUpperCase()}</Text>
      </View>

      <View style={styles.profileMeta}>
         <View style={styles.metaRow}>
            <Text style={styles.metaLabel}>System Access</Text>
            <Text style={[styles.metaValue, { color: COLORS.success }]}>Authorized</Text>
         </View>
         <View style={styles.metaRow}>
            <Text style={styles.metaLabel}>Encryption</Text>
            <Text style={styles.metaValue}>AES-256</Text>
         </View>
      </View>

      <TouchableOpacity 
        style={[styles.button, { marginTop: 40, backgroundColor: 'rgba(248,113,113,0.1)', borderColor: 'rgba(248,113,113,0.2)', borderWidth: 1 }]} 
        onPress={async () => {
          await authApi.logout();
          onLogout();
        }}
      >
        <Text style={[styles.buttonText, { color: COLORS.error }]}>Terminate Connection</Text>
      </TouchableOpacity>
    </View>
  );
}

// -----------------------------------------------------------------------------
// Component & Styles
// -----------------------------------------------------------------------------
function TabButton({ icon, label, active, onPress }: any) {
  return (
    <TouchableOpacity style={styles.tabBtn} onPress={onPress}>
      <Ionicons name={icon} size={22} color={active ? COLORS.accent2 : COLORS.text2} />
      <Text style={[styles.tabLabel, { color: active ? COLORS.accent2 : COLORS.text2, fontWeight: active ? '700' : '500' }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 24, paddingTop: 20, paddingBottom: 20 },
  headerTitleGroup: { flexDirection: 'row', alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: '900', color: COLORS.text1, letterSpacing: 2 },
  headerIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: COLORS.surface, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  content: { flex: 1 },
  
  // Login card
  card: { width: '100%', backgroundColor: COLORS.card, padding: 30, borderRadius: 32, borderWidth: 1, borderColor: COLORS.border, shadowColor: COLORS.accent1, shadowOffset: { width: 0, height: 10 }, shadowOpacity: 0.1, shadowRadius: 20, elevation: 5 },
  loginGlow: { position: 'absolute', top: '20%', width: 300, height: 300, backgroundColor: COLORS.accent1, borderRadius: 150, opacity: 0.05, transform: [{ scale: 2 }] },
  iconCircle: { width: 64, height: 64, borderRadius: 24, backgroundColor: COLORS.surface, justifyContent: 'center', alignItems: 'center', alignSelf: 'center', marginBottom: 24, borderWidth: 1, borderColor: COLORS.border },
  title: { fontSize: 26, fontWeight: '800', color: COLORS.text1, textAlign: 'center', marginBottom: 10, letterSpacing: -0.5 },
  subtitle: { fontSize: 14, color: COLORS.text2, textAlign: 'center', marginBottom: 30, lineHeight: 20 },
  input: { backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: 16, padding: 18, color: COLORS.text1, fontSize: 16, marginBottom: 20, borderWidth: 1, borderColor: COLORS.border },
  button: { backgroundColor: COLORS.accent1, borderRadius: 16, padding: 18, alignItems: 'center', shadowColor: COLORS.accent1, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  
  // Tab Bar
  tabBar: { 
    flexDirection: 'row', 
    backgroundColor: COLORS.surface, 
    borderTopWidth: 1, 
    borderColor: COLORS.border, 
    paddingBottom: Platform.OS === 'ios' ? 30 : 10, 
    paddingTop: 10 
  },
  tabBtn: { flex: 1, alignItems: 'center', gap: 4 },
  tabLabel: { fontSize: 10, textTransform: 'uppercase', tracking: 1 },
  
  // List
  listItem: { flexDirection: 'row', backgroundColor: COLORS.card, padding: 16, borderRadius: 24, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  listIcon: { width: 48, height: 48, borderRadius: 16, backgroundColor: COLORS.surface, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  listTitle: { color: COLORS.text1, fontSize: 15, fontWeight: '700', marginBottom: 2 },
  listSubtitle: { color: COLORS.text2, fontSize: 12, opacity: 0.7 },
  emptyText: { color: COLORS.text2, textAlign: 'center', marginTop: 60, fontSize: 14, fontWeight: '600', opacity: 0.5, letterSpacing: 1 },
  
  // Profile
  profileGlow: { position: 'absolute', top: '10%', width: 200, height: 200, backgroundColor: COLORS.accent1, borderRadius: 100, opacity: 0.1, transform: [{ scale: 3 }] },
  badge: { paddingHorizontal: 16, paddingVertical: 6, borderRadius: 100, marginTop: 12 },
  badgeText: { fontSize: 10, fontWeight: '900', letterSpacing: 2 },
  profileMeta: { width: '100%', marginTop: 40, gap: 12 },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', padding: 20, backgroundColor: COLORS.surface, borderRadius: 20, borderWidth: 1, borderColor: COLORS.border },
  metaLabel: { color: COLORS.text2, fontSize: 14, fontWeight: '600' },
  metaValue: { color: COLORS.text1, fontSize: 14, fontWeight: '700' },
  
  // Progress
  progressBarBg: { height: 4, backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: 2, marginVertical: 8, overflow: 'hidden' },
  progressBar: { height: '100%', borderRadius: 2 }
});
