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
  bg: '#050508',
  surface: '#0d0d14',
  card: '#13131e',
  accent1: '#6366f1',
  accent2: '#8b5cf6',
  text1: '#f1f0fd',
  text2: '#a8a5c5',
  border: 'rgba(255,255,255,0.07)',
  success: '#10b981',
  error: '#ef4444'
};

export default function App() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);
  const [tab, setTab] = useState('library'); // 'library', 'jobs', 'profile'

  useEffect(() => {
    authApi.getSession().then(res => {
      setUser(res.user);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator color={COLORS.accent1} /></View>

  if (!user) return <LoginScreen onLogin={setUser} />

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={COLORS.bg} />

      <View style={styles.header}>
        <Text style={styles.headerTitle}>YotuDrive</Text>
        <Ionicons name="flash-outline" size={24} color={COLORS.accent1} />
      </View>

      <View style={styles.content}>
        {tab === 'library' && <LibraryScreen />}
        {tab === 'jobs' && <JobsScreen />}
        {tab === 'profile' && <ProfileScreen user={user} onLogout={() => setUser(null)} />}
      </View>

      {/* Custom Tab Bar */}
      <View style={styles.tabBar}>
        <TabButton icon="folder-outline" label="Library" active={tab === 'library'} onPress={() => setTab('library')} />
        <TabButton icon="pulse-outline" label="Transfers" active={tab === 'jobs'} onPress={() => setTab('jobs')} />
        <TabButton icon="person-outline" label="Profile" active={tab === 'profile'} onPress={() => setTab('profile')} />
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
    setLoading(true);
    try {
      const res = await authApi.devLogin(email);
      onLogin(res.user);
    } catch (e: any) {
      alert('Login failed: ' + (e.response?.data?.error?.message || e.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={[styles.container, styles.center]}>
      <View style={styles.card}>
        <Ionicons name="flash" size={48} color={COLORS.accent1} style={{ alignSelf: 'center', marginBottom: 20 }} />
        <Text style={styles.title}>Welcome Back</Text>
        <Text style={styles.subtitle}>Enter your development email to connect.</Text>

        <TextInput
          style={styles.input}
          placeholder="admin@test.yotu"
          placeholderTextColor={COLORS.text2}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />

        <TouchableOpacity style={styles.button} onPress={handleLogin} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Authenticate via API</Text>}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

function LibraryScreen() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    filesApi.list().then(res => { setFiles(res.files); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <View style={styles.center}><ActivityIndicator color={COLORS.accent1} /></View>

  return (
    <FlatList
      data={files}
      keyExtractor={(item: any) => item.id}
      contentContainerStyle={{ padding: 16 }}
      ListEmptyComponent={<Text style={styles.emptyText}>No files archived yet.</Text>}
      renderItem={({ item }) => (
        <View style={styles.listItem}>
          <Ionicons name="videocam-outline" size={32} color={COLORS.text2} />
          <View style={{ marginLeft: 16, flex: 1 }}>
            <Text style={styles.listTitle} numberOfLines={1}>{item.file_name}</Text>
            <Text style={styles.listSubtitle}>{item.video_id === 'pending' ? 'Processing...' : item.video_id}</Text>
          </View>
        </View>
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

  if (loading) return <View style={styles.center}><ActivityIndicator color={COLORS.accent1} /></View>

  return (
    <FlatList
      data={jobs}
      keyExtractor={(item: any) => item.id}
      contentContainerStyle={{ padding: 16 }}
      ListEmptyComponent={<Text style={styles.emptyText}>No active pipelines.</Text>}
      renderItem={({ item }) => (
        <View style={styles.listItem}>
          <Ionicons name={item.status === 'done' ? "checkmark-circle" : "pulse"} size={32} color={item.status === 'done' ? COLORS.success : COLORS.accent1} />
          <View style={{ marginLeft: 16, flex: 1 }}>
            <Text style={styles.listTitle} numberOfLines={1}>{item.kind} • {item.progress}%</Text>
            <Text style={styles.listSubtitle}>{item.message}</Text>
          </View>
        </View>
      )}
    />
  );
}

function ProfileScreen({ user, onLogout }: { user: any, onLogout: () => void }) {
  return (
    <View style={[styles.center, { padding: 20 }]}>
      <Ionicons name="person-circle-outline" size={80} color={COLORS.accent1} />
      <Text style={[styles.title, { marginTop: 20 }]}>{user.email}</Text>
      <Text style={styles.badge}>{user.role.toUpperCase()}</Text>

      <TouchableOpacity style={[styles.button, { marginTop: 40, backgroundColor: 'transparent', borderColor: COLORS.border, borderWidth: 1 }]} onPress={async () => {
        await authApi.logout();
        onLogout();
      }}>
        <Text style={[styles.buttonText, { color: COLORS.error }]}>Disconnect Session</Text>
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
      <Ionicons name={icon} size={24} color={active ? COLORS.accent1 : COLORS.text2} />
      <Text style={[styles.tabLabel, { color: active ? COLORS.accent1 : COLORS.text2 }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20, borderBottomWidth: 1, borderColor: COLORS.border },
  headerTitle: { fontSize: 24, fontWeight: '700', color: COLORS.text1, letterSpacing: -0.5 },
  content: { flex: 1 },
  // Login card
  card: { width: '85%', backgroundColor: COLORS.card, padding: 24, borderRadius: 20, borderWidth: 1, borderColor: COLORS.border },
  title: { fontSize: 22, fontWeight: 'bold', color: COLORS.text1, textAlign: 'center', marginBottom: 8 },
  subtitle: { fontSize: 14, color: COLORS.text2, textAlign: 'center', marginBottom: 24 },
  input: { backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: 10, padding: 14, color: COLORS.text1, fontSize: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  button: { backgroundColor: COLORS.accent1, borderRadius: 10, padding: 16, alignItems: 'center' },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  // Tab Bar
  tabBar: { flexDirection: 'row', backgroundColor: COLORS.surface, borderTopWidth: 1, borderColor: COLORS.border, paddingBottom: Platform.OS === 'ios' ? 20 : 0 },
  tabBtn: { flex: 1, padding: 12, alignItems: 'center' },
  tabLabel: { fontSize: 12, marginTop: 4, fontWeight: '500' },
  // List
  listItem: { flexDirection: 'row', backgroundColor: COLORS.card, padding: 16, borderRadius: 16, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  listTitle: { color: COLORS.text1, fontSize: 16, fontWeight: '600', marginBottom: 4 },
  listSubtitle: { color: COLORS.text2, fontSize: 13 },
  emptyText: { color: COLORS.text2, textAlign: 'center', marginTop: 40, fontSize: 15 },
  badge: { backgroundColor: 'rgba(99,102,241,0.15)', color: COLORS.accent1, paddingHorizontal: 12, paddingVertical: 4, borderRadius: 100, fontSize: 12, fontWeight: 'bold', overflow: 'hidden', marginTop: 12 }
});
