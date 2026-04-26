import sqlite3
import secrets
from datetime import datetime


def get_db(db_path):
    """Get a database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path):
    """Initialize the database schema."""
    conn = get_db(db_path)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER DEFAULT NULL,
            share_token TEXT UNIQUE,
            is_public INTEGER DEFAULT 0,
            password_hash TEXT,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            folder_id INTEGER DEFAULT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type TEXT DEFAULT 'application/octet-stream',
            share_token TEXT UNIQUE,
            is_public INTEGER DEFAULT 0,
            password_hash TEXT,
            expires_at TIMESTAMP,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            download_count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
        CREATE INDEX IF NOT EXISTS idx_files_folder_id ON files(folder_id);
        CREATE INDEX IF NOT EXISTS idx_files_share_token ON files(share_token);
        CREATE INDEX IF NOT EXISTS idx_users_api_token ON users(api_token);
        CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders(user_id);
        CREATE INDEX IF NOT EXISTS idx_folders_parent_id ON folders(parent_id);

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    ''')
    
    # Default settings
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('registration_enabled', '1')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('max_quota_bytes', '1073741824')")
    
    # Migration for files and folders
    for table in ['files', 'folders']:
        try: conn.execute(f'ALTER TABLE {table} ADD COLUMN share_token TEXT UNIQUE')
        except sqlite3.OperationalError: pass
        try: conn.execute(f'ALTER TABLE {table} ADD COLUMN is_public INTEGER DEFAULT 0')
        except sqlite3.OperationalError: pass
        try: conn.execute(f'ALTER TABLE {table} ADD COLUMN password_hash TEXT')
        except sqlite3.OperationalError: pass
        try: conn.execute(f'ALTER TABLE {table} ADD COLUMN expires_at TIMESTAMP')
        except sqlite3.OperationalError: pass

    conn.commit()
    conn.close()


def generate_token():
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)


def generate_share_token():
    """Generate a shorter share token for URLs."""
    return secrets.token_urlsafe(16)


# ─── Settings operations ────────────────────────────────────

def get_setting(db_path, key, default=None):
    """Get a global setting value."""
    conn = get_db(db_path)
    result = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    if result:
        return result['value']
    return default

def set_setting(db_path, key, value):
    """Set a global setting value."""
    conn = get_db(db_path)
    conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()


# ─── User operations ────────────────────────────────────────

def create_user(db_path, username, email, password_hash):
    """Create a new user and return the user row."""
    conn = get_db(db_path)
    api_token = generate_token()
    try:
        conn.execute(
            'INSERT INTO users (username, email, password_hash, api_token) VALUES (?, ?, ?, ?)',
            (username, email, password_hash, api_token)
        )
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return user
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_username(db_path, username):
    conn = get_db(db_path)
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user


def get_user_by_id(db_path, user_id):
    conn = get_db(db_path)
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user


def get_user_by_token(db_path, token):
    conn = get_db(db_path)
    user = conn.execute('SELECT * FROM users WHERE api_token = ?', (token,)).fetchone()
    conn.close()
    return user


# ─── File operations ────────────────────────────────────────

def create_file(db_path, user_id, filename, original_name, file_size, mime_type, folder_id=None):
    """Create a file record and return it."""
    conn = get_db(db_path)
    share_token = generate_share_token()
    conn.execute(
        '''INSERT INTO files (user_id, folder_id, filename, original_name, file_size, mime_type, share_token)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user_id, folder_id, filename, original_name, file_size, mime_type, share_token)
    )
    conn.commit()
    file = conn.execute('SELECT * FROM files WHERE share_token = ?', (share_token,)).fetchone()
    conn.close()
    return file


def get_files_by_user(db_path, user_id, folder_id=None):
    conn = get_db(db_path)
    if folder_id is None:
        files = conn.execute(
            'SELECT * FROM files WHERE user_id = ? AND folder_id IS NULL ORDER BY upload_date DESC',
            (user_id,)
        ).fetchall()
    else:
        files = conn.execute(
            'SELECT * FROM files WHERE user_id = ? AND folder_id = ? ORDER BY upload_date DESC',
            (user_id, folder_id)
        ).fetchall()
    conn.close()
    return files


def move_file(db_path, file_id, folder_id):
    """Move a file to a folder (or root if folder_id is None)."""
    conn = get_db(db_path)
    conn.execute('UPDATE files SET folder_id = ? WHERE id = ?', (folder_id, file_id))
    conn.commit()
    conn.close()


def get_file_by_id(db_path, file_id):
    conn = get_db(db_path)
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    return file


def get_file_by_share_token(db_path, share_token):
    conn = get_db(db_path)
    file = conn.execute('SELECT * FROM files WHERE share_token = ?', (share_token,)).fetchone()
    conn.close()
    return file


def delete_file(db_path, file_id):
    conn = get_db(db_path)
    conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()


def toggle_file_public(db_path, file_id):
    conn = get_db(db_path)
    conn.execute('UPDATE files SET is_public = NOT is_public WHERE id = ?', (file_id,))
    conn.commit()
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    return file


def rename_file(db_path, file_id, new_name):
    conn = get_db(db_path)
    conn.execute('UPDATE files SET original_name = ? WHERE id = ?', (new_name, file_id))
    conn.commit()
    conn.close()





def get_user_storage_used(db_path, user_id):
    """Get total storage used by a user in bytes."""
    conn = get_db(db_path)
    result = conn.execute(
        'SELECT COALESCE(SUM(file_size), 0) as total FROM files WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    conn.close()
    return result['total']


# ─── Folder operations ──────────────────────────────────────

def create_folder(db_path, user_id, name, parent_id=None):
    conn = get_db(db_path)
    share_token = generate_share_token()
    conn.execute(
        'INSERT INTO folders (user_id, name, parent_id, share_token) VALUES (?, ?, ?, ?)',
        (user_id, name, parent_id, share_token)
    )
    conn.commit()
    folder = conn.execute(
        'SELECT * FROM folders WHERE user_id = ? AND name = ? AND parent_id IS ? ORDER BY id DESC LIMIT 1',
        (user_id, name, parent_id)
    ).fetchone()
    conn.close()
    return folder


def get_folders_by_user(db_path, user_id, parent_id=None):
    conn = get_db(db_path)
    if parent_id is None:
        folders = conn.execute(
            'SELECT * FROM folders WHERE user_id = ? AND parent_id IS NULL ORDER BY name',
            (user_id,)
        ).fetchall()
    else:
        folders = conn.execute(
            'SELECT * FROM folders WHERE user_id = ? AND parent_id = ? ORDER BY name',
            (user_id, parent_id)
        ).fetchall()
    conn.close()
    return folders


def get_folder_by_id(db_path, folder_id):
    conn = get_db(db_path)
    folder = conn.execute('SELECT * FROM folders WHERE id = ?', (folder_id,)).fetchone()
    conn.close()
    return folder


def rename_folder(db_path, folder_id, new_name):
    conn = get_db(db_path)
    conn.execute('UPDATE folders SET name = ? WHERE id = ?', (new_name, folder_id))
    conn.commit()
    conn.close()


def toggle_folder_public(db_path, folder_id):
    conn = get_db(db_path)
    # If it doesn't have a share token yet, generate one (for legacy folders)
    folder = conn.execute('SELECT share_token FROM folders WHERE id = ?', (folder_id,)).fetchone()
    if not folder['share_token']:
        conn.execute('UPDATE folders SET share_token = ? WHERE id = ?', (generate_share_token(), folder_id))
    
    conn.execute('UPDATE folders SET is_public = NOT is_public WHERE id = ?', (folder_id,))
    conn.commit()
    folder = conn.execute('SELECT * FROM folders WHERE id = ?', (folder_id,)).fetchone()
    conn.close()
    return folder


def get_folder_by_share_token(db_path, share_token):
    conn = get_db(db_path)
    folder = conn.execute('SELECT * FROM folders WHERE share_token = ?', (share_token,)).fetchone()
    conn.close()
    return folder


def get_all_files_in_folder_recursive(db_path, folder_id):
    conn = get_db(db_path)
    def get_subfolders(fid):
        fids = [fid]
        rows = conn.execute('SELECT id FROM folders WHERE parent_id = ?', (fid,)).fetchall()
        for r in rows:
            fids.extend(get_subfolders(r['id']))
        return fids
    folder_ids = get_subfolders(folder_id)
    placeholders = ','.join('?' * len(folder_ids))
    files = conn.execute(f'SELECT * FROM files WHERE folder_id IN ({placeholders})', folder_ids).fetchall()
    conn.close()
    return files


def delete_folder(db_path, folder_id):
    """Delete a folder and all its contents (files and subfolders)."""
    conn = get_db(db_path)
    def get_subfolders(fid):
        fids = [fid]
        rows = conn.execute('SELECT id FROM folders WHERE parent_id = ?', (fid,)).fetchall()
        for r in rows:
            fids.extend(get_subfolders(r['id']))
        return fids
    folder_ids = get_subfolders(folder_id)
    placeholders = ','.join('?' * len(folder_ids))
    conn.execute(f'DELETE FROM files WHERE folder_id IN ({placeholders})', folder_ids)
    conn.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
    conn.commit()
    conn.close()


def get_folder_breadcrumbs(db_path, folder_id):
    """Get the breadcrumb path for a folder."""
    crumbs = []
    conn = get_db(db_path)
    current = folder_id
    while current is not None:
        folder = conn.execute('SELECT * FROM folders WHERE id = ?', (current,)).fetchone()
        if not folder:
            break
        crumbs.insert(0, {'id': folder['id'], 'name': folder['name']})
        current = folder['parent_id']
    conn.close()
    return crumbs


# ─── Duplicate name helpers ─────────────────────────────────

def _deduplicate_name(base_name, existing_names):
    """Generate a unique name by appending (1), (2), etc. if base_name exists."""
    if base_name not in existing_names:
        return base_name
    # Split name and extension for files
    if '.' in base_name:
        stem, ext = base_name.rsplit('.', 1)
        ext = '.' + ext
    else:
        stem = base_name
        ext = ''
    counter = 1
    while True:
        candidate = f"{stem} ({counter}){ext}"
        if candidate not in existing_names:
            return candidate
        counter += 1


def get_unique_file_name(db_path, original_name, folder_id, user_id):
    """Return a unique original_name in the target folder."""
    conn = get_db(db_path)
    if folder_id is None:
        existing = conn.execute(
            'SELECT original_name FROM files WHERE user_id = ? AND folder_id IS NULL',
            (user_id,)
        ).fetchall()
    else:
        existing = conn.execute(
            'SELECT original_name FROM files WHERE user_id = ? AND folder_id = ?',
            (user_id, folder_id)
        ).fetchall()
    conn.close()
    names = {r['original_name'] for r in existing}
    return _deduplicate_name(original_name, names)


def get_unique_folder_name(db_path, name, parent_id, user_id):
    """Return a unique folder name in the target parent."""
    conn = get_db(db_path)
    if parent_id is None:
        existing = conn.execute(
            'SELECT name FROM folders WHERE user_id = ? AND parent_id IS NULL',
            (user_id,)
        ).fetchall()
    else:
        existing = conn.execute(
            'SELECT name FROM folders WHERE user_id = ? AND parent_id = ?',
            (user_id, parent_id)
        ).fetchall()
    conn.close()
    names = {r['name'] for r in existing}
    return _deduplicate_name(name, names)


def copy_file_record(db_path, file_id, target_folder_id, user_id, upload_folder):
    """Copy a file: duplicate on disk + create new DB record with deduped name."""
    import os, uuid, shutil
    conn = get_db(db_path)
    src = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    if not src:
        return None

    # Deduplicate name in target folder
    new_name = get_unique_file_name(db_path, src['original_name'], target_folder_id, user_id)

    # Copy physical file
    ext = src['filename'].rsplit('.', 1)[1] if '.' in src['filename'] else ''
    new_disk_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    src_path = os.path.join(upload_folder, src['filename'])
    dst_path = os.path.join(upload_folder, new_disk_name)
    if os.path.exists(src_path):
        shutil.copy2(src_path, dst_path)
    else:
        return None

    file_size = os.path.getsize(dst_path)
    return create_file(db_path, user_id, new_disk_name, new_name, file_size, src['mime_type'], target_folder_id)

def move_folder(db_path, folder_id, new_parent_id):
    """Move a folder to a new parent folder (or root if new_parent_id is None)."""
    if folder_id == new_parent_id:
        return False
        
    conn = get_db(db_path)
    current = new_parent_id
    while current is not None:
        if current == folder_id:
            conn.close()
            return False
        folder = conn.execute('SELECT parent_id FROM folders WHERE id = ?', (current,)).fetchone()
        if not folder:
            break
        current = folder['parent_id']
        
    conn.execute('UPDATE folders SET parent_id = ? WHERE id = ?', (new_parent_id, folder_id))
    conn.commit()
    conn.close()
    return True


def copy_folder_record(db_path, folder_id, target_parent_id, user_id, upload_folder):
    """Recursively copy a folder and its contents."""
    conn = get_db(db_path)
    src_folder = conn.execute('SELECT * FROM folders WHERE id = ?', (folder_id,)).fetchone()
    conn.close()
    if not src_folder:
        return None

    new_name = get_unique_folder_name(db_path, src_folder['name'], target_parent_id, user_id)
    new_folder = create_folder(db_path, user_id, new_name, target_parent_id)
    if not new_folder:
        return None

    conn = get_db(db_path)
    files = conn.execute('SELECT id FROM files WHERE folder_id = ?', (folder_id,)).fetchall()
    conn.close()
    for f in files:
        copy_file_record(db_path, f['id'], new_folder['id'], user_id, upload_folder)

    conn = get_db(db_path)
    subfolders = conn.execute('SELECT id FROM folders WHERE parent_id = ?', (folder_id,)).fetchall()
    conn.close()
    for sf in subfolders:
        copy_folder_record(db_path, sf['id'], new_folder['id'], user_id, upload_folder)

    return new_folder

def set_folder_public_recursive(db_path, folder_id, user_id, is_public):
    """Recursively set public status for all files and subfolders."""
    conn = get_db(db_path)
    # Set public status for all files in this folder
    conn.execute('UPDATE files SET is_public = ? WHERE folder_id = ? AND user_id = ?', 
                 (1 if is_public else 0, folder_id, user_id))
    
    # Get subfolders
    subfolders = conn.execute('SELECT id FROM folders WHERE parent_id = ? AND user_id = ?', 
                             (folder_id, user_id)).fetchall()
    conn.commit()
    conn.close()
    
    # Recurse
    for sf in subfolders:
        set_folder_public_recursive(db_path, sf['id'], user_id, is_public)

def update_file_share_config(db_path, file_id, is_public, share_token=None, password_hash=None, expires_at=None):
    conn = get_db(db_path)
    if not share_token:
        res = conn.execute('SELECT share_token FROM files WHERE id = ?', (file_id,)).fetchone()
        share_token = res['share_token'] or generate_share_token()
    conn.execute('''
        UPDATE files SET is_public = ?, share_token = ?, password_hash = ?, expires_at = ?
        WHERE id = ?
    ''', (1 if is_public else 0, share_token, password_hash, expires_at, file_id))
    conn.commit()
    file = conn.execute('SELECT * FROM files WHERE id = ?', (file_id,)).fetchone()
    conn.close()
    return file

def update_folder_share_config(db_path, folder_id, is_public, share_token=None, password_hash=None, expires_at=None):
    conn = get_db(db_path)
    if not share_token:
        res = conn.execute('SELECT share_token FROM folders WHERE id = ?', (folder_id,)).fetchone()
        share_token = res['share_token'] or generate_share_token()
    conn.execute('''
        UPDATE folders SET is_public = ?, share_token = ?, password_hash = ?, expires_at = ?
        WHERE id = ?
    ''', (1 if is_public else 0, share_token, password_hash, expires_at, folder_id))
    conn.commit()
    folder = conn.execute('SELECT * FROM folders WHERE id = ?', (folder_id,)).fetchone()
    conn.close()
    return folder

def is_slug_available(db_path, slug, current_type, current_id):
    conn = get_db(db_path)
    try:
        current_id = int(current_id)
    except: pass
    # Check files
    f = conn.execute('SELECT id FROM files WHERE share_token = ?', (slug,)).fetchone()
    if f and (current_type != 'file' or f['id'] != current_id):
        conn.close()
        return False
    # Check folders
    fol = conn.execute('SELECT id FROM folders WHERE share_token = ?', (slug,)).fetchone()
    conn.close()
    if fol and (current_type != 'folder' or fol['id'] != current_id):
        return False
    return True

def is_share_expired(expires_at_str):
    if not expires_at_str:
        return False
    try:
        # SQLite storage format for timestamps can vary, but usually ISO
        # Handle 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DDTHH:MM'
        fmt = '%Y-%m-%dT%H:%M' if 'T' in expires_at_str else '%Y-%m-%d %H:%M:%S'
        exp = datetime.strptime(expires_at_str[:16], fmt)
        return datetime.now() > exp
    except Exception:
        return False
