"""
YotuDrive 2.0 - Collaborative Features
Real-time collaboration, sharing, and team management
"""

import os
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

@dataclass
class User:
    """User account with enhanced features"""
    id: str
    username: str
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    role: str = "user"  # admin, editor, viewer, user
    storage_quota: int = 10 * 1024 * 1024 * 1024  # 10GB default
    storage_used: int = 0
    created_at: float = None
    last_active: float = None
    preferences: Dict[str, Any] = None
    permissions: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.last_active is None:
            self.last_active = time.time()
        if self.preferences is None:
            self.preferences = {
                'theme': 'dark',
                'language': 'en',
                'notifications': True,
                'auto_share': False
            }
        if self.permissions is None:
            self.permissions = ['read', 'write', 'delete']

@dataclass
class Workspace:
    """Collaborative workspace"""
    id: str
    name: str
    description: str
    owner_id: str
    members: List[str]  # User IDs
    created_at: float = None
    settings: Dict[str, Any] = None
    storage_quota: int = 100 * 1024 * 1024 * 1024  # 100GB default
    storage_used: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.settings is None:
            self.settings = {
                'public': False,
                'allow_guests': False,
                'require_approval': True,
                'default_permissions': ['read', 'write']
            }

@dataclass
class ShareLink:
    """Secure sharing link with permissions"""
    id: str
    file_id: str
    workspace_id: Optional[str]
    created_by: str
    token: str
    permissions: List[str]
    expires_at: Optional[float] = None
    download_limit: Optional[int] = None
    downloads_used: int = 0
    password: Optional[str] = None
    allowed_emails: List[str] = None
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.allowed_emails is None:
            self.allowed_emails = []

@dataclass
class Activity:
    """Activity tracking for collaboration"""
    id: str
    user_id: str
    action: str  # upload, download, share, delete, rename, etc.
    target_type: str  # file, folder, workspace, user
    target_id: str
    details: Dict[str, Any]
    timestamp: float = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class CollaborationManager:
    """Advanced collaboration and sharing system"""
    
    def __init__(self, data_dir: str = "collaboration_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Data files
        self.users_file = self.data_dir / "users.json"
        self.workspaces_file = self.data_dir / "workspaces.json"
        self.shares_file = self.data_dir / "shares.json"
        self.activities_file = self.data_dir / "activities.json"
        self.sessions_file = self.data_dir / "sessions.json"
        
        # In-memory data
        self.users: Dict[str, User] = {}
        self.workspaces: Dict[str, Workspace] = {}
        self.shares: Dict[str, ShareLink] = {}
        self.activities: List[Activity] = []
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Encryption key for sensitive data
        self.encryption_key = self._generate_encryption_key()
        
        # Load data
        self.load_data()
    
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key for sensitive data"""
        password = "yotudrive_collaboration_key".encode()
        salt = b"yotudrive_salt_value"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def _encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        f = Fernet(self.encryption_key)
        encrypted_data = f.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        f = Fernet(self.encryption_key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted_data = f.decrypt(encrypted_bytes)
        return decrypted_data.decode()
    
    def load_data(self):
        """Load collaboration data from files"""
        try:
            # Load users
            if self.users_file.exists():
                with open(self.users_file, 'r') as f:
                    users_data = json.load(f)
                self.users = {uid: User(**user_data) for uid, user_data in users_data.items()}
            
            # Load workspaces
            if self.workspaces_file.exists():
                with open(self.workspaces_file, 'r') as f:
                    workspaces_data = json.load(f)
                self.workspaces = {wid: Workspace(**ws_data) for wid, ws_data in workspaces_data.items()}
            
            # Load shares
            if self.shares_file.exists():
                with open(self.shares_file, 'r') as f:
                    shares_data = json.load(f)
                self.shares = {sid: ShareLink(**share_data) for sid, share_data in shares_data.items()}
            
            # Load activities
            if self.activities_file.exists():
                with open(self.activities_file, 'r') as f:
                    activities_data = json.load(f)
                self.activities = [Activity(**activity) for activity in activities_data]
            
            # Load sessions
            if self.sessions_file.exists():
                with open(self.sessions_file, 'r') as f:
                    self.active_sessions = json.load(f)
            
        except Exception as e:
            print(f"Error loading collaboration data: {e}")
    
    def save_data(self):
        """Save collaboration data to files"""
        try:
            # Save users
            users_data = {uid: asdict(user) for uid, user in self.users.items()}
            with open(self.users_file, 'w') as f:
                json.dump(users_data, f, indent=2)
            
            # Save workspaces
            workspaces_data = {wid: asdict(workspace) for wid, workspace in self.workspaces.items()}
            with open(self.workspaces_file, 'w') as f:
                json.dump(workspaces_data, f, indent=2)
            
            # Save shares
            shares_data = {sid: asdict(share) for sid, share in self.shares.items()}
            with open(self.shares_file, 'w') as f:
                json.dump(shares_data, f, indent=2)
            
            # Save activities
            activities_data = [asdict(activity) for activity in self.activities]
            with open(self.activities_file, 'w') as f:
                json.dump(activities_data, f, indent=2)
            
            # Save sessions
            with open(self.sessions_file, 'w') as f:
                json.dump(self.active_sessions, f, indent=2)
            
        except Exception as e:
            print(f"Error saving collaboration data: {e}")
    
    def create_user(self, username: str, email: str, display_name: str, role: str = "user") -> User:
        """Create new user account"""
        user_id = str(uuid.uuid4())
        
        user = User(
            id=user_id,
            username=username,
            email=email,
            display_name=display_name,
            role=role
        )
        
        self.users[user_id] = user
        self.save_data()
        
        # Log activity
        self.log_activity(user_id, "user_created", "user", user_id, {
            "username": username,
            "email": email,
            "role": role
        })
        
        return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user (simplified for demo)"""
        # In real implementation, this would verify password hash
        for user in self.users.values():
            if user.username == username:
                user.last_active = time.time()
                self.save_data()
                return user
        return None
    
    def create_workspace(self, name: str, description: str, owner_id: str) -> Workspace:
        """Create new workspace"""
        workspace_id = str(uuid.uuid4())
        
        workspace = Workspace(
            id=workspace_id,
            name=name,
            description=description,
            owner_id=owner_id,
            members=[owner_id]
        )
        
        self.workspaces[workspace_id] = workspace
        self.save_data()
        
        # Log activity
        self.log_activity(owner_id, "workspace_created", "workspace", workspace_id, {
            "name": name,
            "description": description
        })
        
        return workspace
    
    def invite_to_workspace(self, workspace_id: str, user_id: str, inviter_id: str) -> bool:
        """Invite user to workspace"""
        if workspace_id not in self.workspaces or user_id not in self.users:
            return False
        
        workspace = self.workspaces[workspace_id]
        
        if user_id not in workspace.members:
            workspace.members.append(user_id)
            self.save_data()
            
            # Log activity
            self.log_activity(inviter_id, "user_invited", "workspace", workspace_id, {
                "invited_user": user_id
            })
            
            return True
        
        return False
    
    def create_share_link(self, file_id: str, created_by: str, permissions: List[str], 
                         expires_in_days: Optional[int] = None, 
                         download_limit: Optional[int] = None,
                         password: Optional[str] = None) -> ShareLink:
        """Create secure share link"""
        share_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        
        expires_at = None
        if expires_in_days:
            expires_at = time.time() + (expires_in_days * 24 * 60 * 60)
        
        share_link = ShareLink(
            id=share_id,
            file_id=file_id,
            workspace_id=None,
            created_by=created_by,
            token=token,
            permissions=permissions,
            expires_at=expires_at,
            download_limit=download_limit,
            password=self._encrypt_data(password) if password else None
        )
        
        self.shares[share_id] = share_link
        self.save_data()
        
        # Log activity
        self.log_activity(created_by, "link_created", "file", file_id, {
            "share_id": share_id,
            "permissions": permissions,
            "expires_at": expires_at
        })
        
        return share_link
    
    def validate_share_link(self, token: str, password: Optional[str] = None) -> Optional[ShareLink]:
        """Validate share link token"""
        for share in self.shares.values():
            if share.token == token:
                # Check expiration
                if share.expires_at and time.time() > share.expires_at:
                    return None
                
                # Check download limit
                if share.download_limit and share.downloads_used >= share.download_limit:
                    return None
                
                # Check password
                if share.password:
                    if not password:
                        return None
                    try:
                        decrypted_password = self._decrypt_data(share.password)
                        if password != decrypted_password:
                            return None
                    except:
                        return None
                
                return share
        
        return None
    
    def access_shared_file(self, share_id: str, ip_address: str = None) -> bool:
        """Record access to shared file"""
        if share_id not in self.shares:
            return False
        
        share = self.shares[share_id]
        share.downloads_used += 1
        self.save_data()
        
        # Log activity
        self.log_activity("anonymous", "file_accessed", "file", share.file_id, {
            "share_id": share_id,
            "ip_address": ip_address
        })
        
        return True
    
    def log_activity(self, user_id: str, action: str, target_type: str, target_id: str, 
                    details: Dict[str, Any] = None, ip_address: str = None, 
                    user_agent: str = None):
        """Log user activity"""
        activity = Activity(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.activities.append(activity)
        
        # Keep only last 10000 activities
        if len(self.activities) > 10000:
            self.activities = self.activities[-10000:]
        
        self.save_data()
    
    def get_user_activities(self, user_id: str, limit: int = 50) -> List[Activity]:
        """Get user's recent activities"""
        user_activities = [a for a in self.activities if a.user_id == user_id]
        user_activities.sort(key=lambda x: x.timestamp, reverse=True)
        return user_activities[:limit]
    
    def get_workspace_activities(self, workspace_id: str, limit: int = 100) -> List[Activity]:
        """Get workspace activities"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return []
        
        member_activities = []
        for activity in self.activities:
            if activity.user_id in workspace.members:
                member_activities.append(activity)
        
        member_activities.sort(key=lambda x: x.timestamp, reverse=True)
        return member_activities[:limit]
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        user = self.users.get(user_id)
        if not user:
            return {}
        
        # Calculate storage usage
        storage_used = 0
        files_count = 0
        
        # This would integrate with the main database
        # For now, return placeholder data
        
        # Calculate activity stats
        user_activities = self.get_user_activities(user_id, limit=1000)
        
        action_counts = {}
        for activity in user_activities:
            action_counts[activity.action] = action_counts.get(activity.action, 0) + 1
        
        # Get workspaces
        user_workspaces = []
        for workspace in self.workspaces.values():
            if user_id in workspace.members:
                user_workspaces.append({
                    'id': workspace.id,
                    'name': workspace.name,
                    'role': 'owner' if workspace.owner_id == user_id else 'member'
                })
        
        return {
            'user': asdict(user),
            'storage_used': storage_used,
            'storage_quota': user.storage_quota,
            'storage_percentage': (storage_used / user.storage_quota) * 100,
            'files_count': files_count,
            'workspaces_count': len(user_workspaces),
            'workspaces': user_workspaces,
            'activities_count': len(user_activities),
            'action_counts': action_counts,
            'last_active': user.last_active
        }
    
    def get_workspace_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Get workspace statistics"""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return {}
        
        # Get member details
        members = []
        for member_id in workspace.members:
            member = self.users.get(member_id)
            if member:
                members.append({
                    'id': member.id,
                    'username': member.username,
                    'display_name': member.display_name,
                    'role': 'owner' if member_id == workspace.owner_id else 'member',
                    'last_active': member.last_active
                })
        
        # Get activities
        activities = self.get_workspace_activities(workspace_id, limit=1000)
        
        # Calculate activity stats
        action_counts = {}
        for activity in activities:
            action_counts[activity.action] = action_counts.get(activity.action, 0) + 1
        
        return {
            'workspace': asdict(workspace),
            'members': members,
            'members_count': len(members),
            'storage_used': workspace.storage_used,
            'storage_quota': workspace.storage_quota,
            'storage_percentage': (workspace.storage_used / workspace.storage_quota) * 100,
            'activities_count': len(activities),
            'action_counts': action_counts,
            'created_at': workspace.created_at
        }
    
    def search_users(self, query: str, limit: int = 20) -> List[User]:
        """Search users by username, email, or display name"""
        query_lower = query.lower()
        results = []
        
        for user in self.users.values():
            if (query_lower in user.username.lower() or 
                query_lower in user.email.lower() or 
                query_lower in user.display_name.lower()):
                results.append(user)
        
        # Sort by last active
        results.sort(key=lambda x: x.last_active, reverse=True)
        return results[:limit]
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get currently active user sessions"""
        active_sessions = []
        current_time = time.time()
        
        for session_id, session_data in self.active_sessions.items():
            if current_time - session_data.get('last_activity', 0) < 30 * 60:  # 30 minutes
                user = self.users.get(session_data.get('user_id'))
                if user:
                    active_sessions.append({
                        'session_id': session_id,
                        'user': asdict(user),
                        'last_activity': session_data.get('last_activity'),
                        'ip_address': session_data.get('ip_address'),
                        'user_agent': session_data.get('user_agent')
                    })
        
        return active_sessions
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions and shares"""
        current_time = time.time()
        
        # Clean up expired sessions
        expired_sessions = []
        for session_id, session_data in self.active_sessions.items():
            if current_time - session_data.get('last_activity', 0) > 30 * 60:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        # Clean up expired shares
        expired_shares = []
        for share_id, share in self.shares.items():
            if share.expires_at and current_time > share.expires_at:
                expired_shares.append(share_id)
        
        for share_id in expired_shares:
            del self.shares[share_id]
        
        if expired_sessions or expired_shares:
            self.save_data()
        
        return len(expired_sessions), len(expired_shares)

class RealTimeCollaboration:
    """Real-time collaboration features using WebSockets"""
    
    def __init__(self, collaboration_manager: CollaborationManager):
        self.collab_manager = collaboration_manager
        self.connected_users = {}  # session_id -> user_id
        self.file_locks = {}  # file_id -> user_id
        self.active_editors = {}  # file_id -> set of user_ids
        self.typing_indicators = {}  # file_id -> {user_id: timestamp}
    
    def user_connected(self, session_id: str, user_id: str):
        """Handle user connection"""
        self.connected_users[session_id] = user_id
        
        # Update user last active
        user = self.collab_manager.users.get(user_id)
        if user:
            user.last_active = time.time()
            self.collab_manager.save_data()
    
    def user_disconnected(self, session_id: str):
        """Handle user disconnection"""
        if session_id in self.connected_users:
            user_id = self.connected_users[session_id]
            del self.connected_users[session_id]
            
            # Remove user from active editors
            for file_id, editors in self.active_editors.items():
                editors.discard(user_id)
            
            # Remove typing indicators
            for file_id, typing_users in self.typing_indicators.items():
                typing_users.pop(user_id, None)
            
            # Release file locks
            locked_files = [fid for fid, uid in self.file_locks.items() if uid == user_id]
            for file_id in locked_files:
                del self.file_locks[file_id]
    
    def lock_file(self, file_id: str, user_id: str) -> bool:
        """Lock file for editing"""
        if file_id in self.file_locks:
            return False  # Already locked by someone else
        
        self.file_locks[file_id] = user_id
        return True
    
    def unlock_file(self, file_id: str, user_id: str) -> bool:
        """Unlock file"""
        if self.file_locks.get(file_id) != user_id:
            return False  # Not locked by this user
        
        del self.file_locks[file_id]
        return True
    
    def start_editing(self, file_id: str, user_id: str):
        """User starts editing file"""
        if file_id not in self.active_editors:
            self.active_editors[file_id] = set()
        
        self.active_editors[file_id].add(user_id)
    
    def stop_editing(self, file_id: str, user_id: str):
        """User stops editing file"""
        if file_id in self.active_editors:
            self.active_editors[file_id].discard(user_id)
    
    def set_typing_indicator(self, file_id: str, user_id: str):
        """Set typing indicator"""
        if file_id not in self.typing_indicators:
            self.typing_indicators[file_id] = {}
        
        self.typing_indicators[file_id][user_id] = time.time()
    
    def clear_typing_indicator(self, file_id: str, user_id: str):
        """Clear typing indicator"""
        if file_id in self.typing_indicators:
            self.typing_indicators[file_id].pop(user_id, None)
    
    def get_file_collaboration_state(self, file_id: str) -> Dict[str, Any]:
        """Get collaboration state for a file"""
        current_time = time.time()
        
        # Clean up old typing indicators (older than 5 seconds)
        if file_id in self.typing_indicators:
            self.typing_indicators[file_id] = {
                uid: timestamp for uid, timestamp in self.typing_indicators[file_id].items()
                if current_time - timestamp < 5
            }
        
        return {
            'locked_by': self.file_locks.get(file_id),
            'active_editors': list(self.active_editors.get(file_id, set())),
            'typing_users': list(self.typing_indicators.get(file_id, {}).keys()),
            'connected_users': len(self.connected_users)
        }
    
    def broadcast_file_update(self, file_id: str, update_data: Dict[str, Any], exclude_user: str = None):
        """Broadcast file update to all connected users"""
        # This would integrate with WebSocket broadcasting
        # For now, return the data that would be broadcast
        return {
            'type': 'file_update',
            'file_id': file_id,
            'data': update_data,
            'exclude_user': exclude_user,
            'timestamp': time.time()
        }
    
    def broadcast_user_presence(self, file_id: str):
        """Broadcast user presence updates"""
        collaboration_state = self.get_file_collaboration_state(file_id)
        
        return {
            'type': 'presence_update',
            'file_id': file_id,
            'state': collaboration_state,
            'timestamp': time.time()
        }

# Global collaboration instances
collaboration_manager = CollaborationManager()
realtime_collab = RealTimeCollaboration(collaboration_manager)
