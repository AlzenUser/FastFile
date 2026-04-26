import os
import uuid
import mimetypes
from flask import (
    render_template, request, redirect, url_for,
    session, jsonify, g, send_from_directory, flash, abort
)
from werkzeug.utils import secure_filename
from api import models
from api.auth import hash_password, verify_password, login_required, require_auth

def register_routes(app):
    
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

    def human_size(size_bytes):
        """Convert bytes to human readable string (Mo/Go version)."""
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} To"

    def get_file_icon(mime_type):
        """Return an emoji icon based on file MIME type."""
        if not mime_type: return '📄'
        if mime_type.startswith('image/'): return '🖼️'
        if mime_type.startswith('video/'): return '🎬'
        if mime_type.startswith('audio/'): return '🎵'
        if 'pdf' in mime_type: return '📕'
        if any(x in mime_type for x in ['zip', 'rar', 'tar', '7z']): return '📦'
        if any(x in mime_type for x in ['json', 'xml', 'javascript', 'python']): return '💻'
        if any(x in mime_type for x in ['font', 'woff']): return '🔤'
        if any(x in mime_type for x in ['text', 'document', 'spreadsheet']): return '📝'
        return '📄'

    # Register template filters
    app.jinja_env.filters['human_size'] = human_size
    app.jinja_env.filters['file_icon'] = get_file_icon

    # ─── Web Routes ──────────────────────────────────────────────

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            if not username or not password:
                flash('Veuillez remplir tous les champs.', 'error')
                return render_template('login.html')
            user = models.get_user_by_username(app.config['DATABASE'], username)
            if user and verify_password(user['password_hash'], password):
                session['user_id'] = user['id']
                session['api_token'] = user['api_token']
                session['username'] = user['username']
                return redirect(url_for('dashboard'))
            else:
                flash('Identifiants incorrects.', 'error')
        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        registration_enabled = models.get_setting(app.config['DATABASE'], 'registration_enabled', '1')
        if registration_enabled != '1':
            flash('Les inscriptions sont actuellement fermées par l\'administrateur.', 'error')
            return render_template('register.html', registration_disabled=True)
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')
            errors = []
            if not username or not email or not password:
                errors.append('Tous les champs sont obligatoires.')
            if len(username) < 3:
                errors.append('Le nom d\'utilisateur doit faire au moins 3 caractères.')
            if len(password) < 6:
                errors.append('Le mot de passe doit faire au moins 6 caractères.')
            if password != confirm:
                errors.append('Les mots de passe ne correspondent pas.')
            if errors:
                for e in errors: flash(e, 'error')
                return render_template('register.html')
            pw_hash = hash_password(password)
            user = models.create_user(app.config['DATABASE'], username, email, pw_hash)
            if user:
                session['user_id'] = user['id']
                session['api_token'] = user['api_token']
                session['username'] = user['username']
                flash('Compte créé avec succès !', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Ce nom d\'utilisateur ou email est déjà pris.', 'error')
        return render_template('register.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @app.route('/dashboard/folder/<int:folder_id>')
    @login_required
    def dashboard(folder_id=None):
        if folder_id is not None:
            folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
            if not folder or folder['user_id'] != g.user['id']:
                abort(404)
        files = models.get_files_by_user(app.config['DATABASE'], g.user['id'], folder_id)
        folders = models.get_folders_by_user(app.config['DATABASE'], g.user['id'], folder_id)
        breadcrumbs = models.get_folder_breadcrumbs(app.config['DATABASE'], folder_id)
        storage_used = models.get_user_storage_used(app.config['DATABASE'], g.user['id'])
        max_quota = int(models.get_setting(app.config['DATABASE'], 'max_quota_bytes', 1073741824))
        return render_template('dashboard.html', files=files, folders=folders, breadcrumbs=breadcrumbs,
                               current_folder_id=folder_id, storage_used=storage_used, max_quota=max_quota, user=g.user)

    @app.route('/share/<token>', methods=['GET', 'POST'])
    def share_page(token):
        file = models.get_file_by_share_token(app.config['DATABASE'], token)
        if not file or not file['is_public']: abort(404)
        
        # Check expiration
        if models.is_share_expired(file['expires_at']):
            return render_template('base.html', error_code="Lien expiré", error_message="Ce lien de partage n'est plus valide."), 410

        # Check password
        if file['password_hash']:
            # Check if password already in session for this share
            if session.get(f'share_unlocked_{token}'):
                pass # Already unlocked
            elif request.method == 'POST':
                if verify_password(file['password_hash'], request.form.get('share_password', '')):
                    session[f'share_unlocked_{token}'] = True
                else:
                    flash('Mot de passe incorrect.', 'error')
                    return render_template('share_password.html')
            else:
                return render_template('share_password.html')

        owner = models.get_user_by_id(app.config['DATABASE'], file['user_id'])
        return render_template('share.html', file=file, owner=owner)

    @app.route('/share/folder/<token>', methods=['GET', 'POST'])
    def share_folder_page(token):
        folder = models.get_folder_by_share_token(app.config['DATABASE'], token)
        if not folder or not folder['is_public']: abort(404)
        
        # Check expiration
        if models.is_share_expired(folder['expires_at']):
            return render_template('base.html', error_code="Lien expiré", error_message="Ce lien de partage n'est plus valide."), 410

        # Check password
        if folder['password_hash']:
            if session.get(f'share_unlocked_{token}'):
                pass
            elif request.method == 'POST':
                if verify_password(folder['password_hash'], request.form.get('share_password', '')):
                    session[f'share_unlocked_{token}'] = True
                else:
                    flash('Mot de passe incorrect.', 'error')
                    return render_template('share_password.html')
            else:
                return render_template('share_password.html')

        files = models.get_files_by_user(app.config['DATABASE'], folder['user_id'], folder['id'])
        subfolders = models.get_folders_by_user(app.config['DATABASE'], folder['user_id'], folder['id'])
        owner = models.get_user_by_id(app.config['DATABASE'], folder['user_id'])
        return render_template('share_folder.html', folder=folder, files=files, subfolders=subfolders, owner=owner)

    # ─── API Routes ──────────────────────────────────────────────

    @app.route('/api/upload', methods=['POST'])
    @require_auth
    def api_upload():
        if 'file' not in request.files: return jsonify({'error': 'Aucun fichier envoyé'}), 400
        file = request.files['file']
        if file.filename == '': return jsonify({'error': 'Nom de fichier vide'}), 400
        if not allowed_file(file.filename): return jsonify({'error': 'Type de fichier non autorisé'}), 400
        original_name = secure_filename(file.filename)
        ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''
        unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        max_quota = int(models.get_setting(app.config['DATABASE'], 'max_quota_bytes', 1073741824))
        storage_used = models.get_user_storage_used(app.config['DATABASE'], g.user['id'])
        if storage_used + file_size > max_quota:
            os.remove(filepath)
            q_val, q_unit = max_quota, 'o'
            for unit in ['o', 'Ko', 'Mo', 'Go', 'To']:
                if q_val < 1024: q_unit = unit; break
                if unit == 'To': break
                q_val /= 1024
            return jsonify({'error': f'Quota de stockage insuffisant ({q_val:.1f} {q_unit} max)'}), 403
        mime_type = mimetypes.guess_type(original_name)[0] or 'application/octet-stream'
        folder_id = request.form.get('folder_id')
        if folder_id:
            try:
                folder_id = int(folder_id)
                folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
                if not folder or folder['user_id'] != g.user['id']: return jsonify({'error': 'Dossier introuvable'}), 404
            except ValueError: return jsonify({'error': 'ID de dossier invalide'}), 400
        else: folder_id = None
        db_file = models.create_file(app.config['DATABASE'], g.user['id'], unique_name, original_name, file_size, mime_type, folder_id)
        return jsonify({'success': True, 'file': {
            'id': db_file['id'], 'original_name': db_file['original_name'], 'file_size': db_file['file_size'],
            'mime_type': db_file['mime_type'], 'share_token': db_file['share_token'], 'is_public': bool(db_file['is_public']),
            'human_size': human_size(db_file['file_size']), 'icon': get_file_icon(db_file['mime_type']), 'upload_date': db_file['upload_date'],
        }})

    @app.route('/api/files')
    @require_auth
    def api_files():
        files = models.get_files_by_user(app.config['DATABASE'], g.user['id'])
        return jsonify({'files': [{
            'id': f['id'], 'original_name': f['original_name'], 'filename': f['filename'], 'file_size': f['file_size'],
            'mime_type': f['mime_type'], 'share_token': f['share_token'], 'is_public': bool(f['is_public']),
            'upload_date': f['upload_date'], 'download_count': f['download_count'], 'human_size': human_size(f['file_size']),
            'icon': get_file_icon(f['mime_type']),
        } for f in files]})

    @app.route('/api/files/<int:file_id>/delete', methods=['DELETE'])
    @require_auth
    def api_delete(file_id):
        file = models.get_file_by_id(app.config['DATABASE'], file_id)
        if not file or file['user_id'] != g.user['id']: return jsonify({'error': 'Fichier introuvable'}), 404
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file['filename'])
        if os.path.exists(filepath): os.remove(filepath)
        models.delete_file(app.config['DATABASE'], file_id)
        return jsonify({'success': True})

    @app.route('/api/files/<int:file_id>/toggle-public', methods=['POST'])
    @require_auth
    def api_toggle_public(file_id):
        file = models.get_file_by_id(app.config['DATABASE'], file_id)
        if not file or file['user_id'] != g.user['id']: return jsonify({'error': 'Fichier introuvable'}), 404
        
        data = request.get_json() or {}
        is_public = data.get('is_public', not file['is_public'])
        
        slug = data.get('slug', '').strip() if 'slug' in data else file['share_token']
        if slug and slug != file['share_token'] and not models.is_slug_available(app.config['DATABASE'], slug, 'file', file_id):
            return jsonify({'error': 'Ce slug est déjà utilisé'}), 400
            
        if 'password' in data:
            pw_hash = hash_password(data['password'].strip()) if data['password'].strip() else None
        else:
            pw_hash = file['password_hash']
            
        if 'expiry' in data:
            expiry = data['expiry'].strip() or None
        else:
            expiry = file['expires_at']
        
        updated = models.update_file_share_config(
            app.config['DATABASE'], file_id, is_public, 
            share_token=slug, 
            password_hash=pw_hash, 
            expires_at=expiry
        )
        
        return jsonify({
            'success': True,
            'is_public': bool(updated['is_public']),
            'share_url': url_for('share_page', token=updated['share_token'], _external=True) if updated['is_public'] else None,
            'cdn_url': url_for('cdn_file', filename=updated['filename'], _external=True) if updated['is_public'] else None,
        })

    @app.route('/api/files/<int:file_id>/rename', methods=['POST'])
    @require_auth
    def api_rename(file_id):
        file = models.get_file_by_id(app.config['DATABASE'], file_id)
        if not file or file['user_id'] != g.user['id']: return jsonify({'error': 'Fichier introuvable'}), 404
        data = request.get_json()
        new_name = data.get('name', '').strip() if data else ''
        if not new_name: return jsonify({'error': 'Nom invalide'}), 400
        models.rename_file(app.config['DATABASE'], file_id, new_name)
        return jsonify({'success': True, 'new_name': new_name})

    @app.route('/api/files/<int:file_id>/move', methods=['POST'])
    @require_auth
    def api_move_file(file_id):
        file = models.get_file_by_id(app.config['DATABASE'], file_id)
        if not file or file['user_id'] != g.user['id']: return jsonify({'error': 'Fichier introuvable'}), 404
        data = request.get_json()
        folder_id = data.get('folder_id') if data else None
        if folder_id is not None:
            folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
            if not folder or folder['user_id'] != g.user['id']: return jsonify({'error': 'Dossier introuvable'}), 404
        new_name = models.get_unique_file_name(app.config['DATABASE'], file['original_name'], folder_id, g.user['id'])
        if new_name != file['original_name']: models.rename_file(app.config['DATABASE'], file_id, new_name)
        models.move_file(app.config['DATABASE'], file_id, folder_id)
        return jsonify({'success': True})

    @app.route('/api/files/<int:file_id>/copy', methods=['POST'])
    @require_auth
    def api_copy_file(file_id):
        file = models.get_file_by_id(app.config['DATABASE'], file_id)
        if not file or file['user_id'] != g.user['id']: return jsonify({'error': 'Fichier introuvable'}), 404
        data = request.get_json()
        folder_id = data.get('folder_id') if data else None
        if folder_id is not None:
            folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
            if not folder or folder['user_id'] != g.user['id']: return jsonify({'error': 'Dossier introuvable'}), 404
        new_file = models.copy_file_record(app.config['DATABASE'], file_id, folder_id, g.user['id'], app.config['UPLOAD_FOLDER'])
        if not new_file: return jsonify({'error': 'Erreur lors de la copie'}), 500
        return jsonify({'success': True, 'new_name': new_file['original_name']})

    @app.route('/api/folders', methods=['POST'])
    @require_auth
    def api_create_folder():
        data = request.get_json()
        name = data.get('name', '').strip() if data else ''
        parent_id = data.get('parent_id') if data else None
        if not name: return jsonify({'error': 'Nom de dossier requis'}), 400
        if parent_id is not None:
            parent = models.get_folder_by_id(app.config['DATABASE'], parent_id)
            if not parent or parent['user_id'] != g.user['id']: return jsonify({'error': 'Dossier parent introuvable'}), 404
        name = models.get_unique_folder_name(app.config['DATABASE'], name, parent_id, g.user['id'])
        folder = models.create_folder(app.config['DATABASE'], g.user['id'], name, parent_id)
        return jsonify({'success': True, 'folder': {'id': folder['id'], 'name': folder['name'], 'parent_id': folder['parent_id']}})

    @app.route('/api/folders/<int:folder_id>/rename', methods=['POST'])
    @require_auth
    def api_rename_folder(folder_id):
        folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
        if not folder or folder['user_id'] != g.user['id']: return jsonify({'error': 'Dossier introuvable'}), 404
        data = request.get_json()
        new_name = data.get('name', '').strip() if data else ''
        if not new_name: return jsonify({'error': 'Nom invalide'}), 400
        models.rename_folder(app.config['DATABASE'], folder_id, new_name)
        return jsonify({'success': True, 'new_name': new_name})

    @app.route('/api/folders/<int:folder_id>/delete', methods=['DELETE'])
    @require_auth
    def api_delete_folder(folder_id):
        folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
        if not folder or folder['user_id'] != g.user['id']: return jsonify({'error': 'Dossier introuvable'}), 404
        files_to_delete = models.get_all_files_in_folder_recursive(app.config['DATABASE'], folder_id)
        for file in files_to_delete:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file['filename'])
            if os.path.exists(filepath): os.remove(filepath)
        models.delete_folder(app.config['DATABASE'], folder_id)
        return jsonify({'success': True})

    @app.route('/api/folders/<int:folder_id>/move', methods=['POST'])
    @require_auth
    def api_move_folder(folder_id):
        folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
        if not folder or folder['user_id'] != g.user['id']: return jsonify({'error': 'Dossier introuvable'}), 404
        data = request.get_json()
        new_parent_id = data.get('folder_id') if data else None
        if new_parent_id is not None:
            parent = models.get_folder_by_id(app.config['DATABASE'], new_parent_id)
            if not parent or parent['user_id'] != g.user['id']: return jsonify({'error': 'Dossier parent introuvable'}), 404
        success = models.move_folder(app.config['DATABASE'], folder_id, new_parent_id)
        if not success: return jsonify({'error': 'Impossible de déplacer le dossier ici'}), 400
        return jsonify({'success': True})

    @app.route('/api/folders/<int:folder_id>/copy', methods=['POST'])
    @require_auth
    def api_copy_folder(folder_id):
        folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
        if not folder or folder['user_id'] != g.user['id']: return jsonify({'error': 'Dossier introuvable'}), 404
        data = request.get_json()
        new_parent_id = data.get('folder_id') if data else None
        if new_parent_id is not None:
            parent = models.get_folder_by_id(app.config['DATABASE'], new_parent_id)
            if not parent or parent['user_id'] != g.user['id']: return jsonify({'error': 'Dossier parent introuvable'}), 404
        new_folder = models.copy_folder_record(app.config['DATABASE'], folder_id, new_parent_id, g.user['id'], app.config['UPLOAD_FOLDER'])
        if not new_folder: return jsonify({'error': 'Erreur lors de la copie'}), 500
        return jsonify({'success': True, 'new_name': new_folder['name']})

    @app.route('/api/folders/<int:folder_id>/toggle-public', methods=['POST'])
    @require_auth
    def api_toggle_folder_public(folder_id):
        folder = models.get_folder_by_id(app.config['DATABASE'], folder_id)
        if not folder or folder['user_id'] != g.user['id']: abort(404)
        
        data = request.get_json() or {}
        is_public = data.get('is_public', not folder['is_public'])
        
        slug = data.get('slug', '').strip() if 'slug' in data else folder['share_token']
        if slug and slug != folder['share_token'] and not models.is_slug_available(app.config['DATABASE'], slug, 'folder', folder_id):
            return jsonify({'error': 'Ce slug est déjà utilisé'}), 400
            
        if 'password' in data:
            pw_hash = hash_password(data['password'].strip()) if data['password'].strip() else None
        else:
            pw_hash = folder['password_hash']
            
        if 'expiry' in data:
            expiry = data['expiry'].strip() or None
        else:
            expiry = folder['expires_at']
        
        updated = models.update_folder_share_config(
            app.config['DATABASE'], folder_id, is_public, 
            share_token=slug, 
            password_hash=pw_hash, 
            expires_at=expiry
        )
        
        return jsonify({
            'success': True,
            'is_public': bool(updated['is_public']),
            'share_url': url_for('share_folder_page', token=updated['share_token'], _external=True) if updated['is_public'] else None
        })

    @app.route('/api/batch', methods=['POST'])
    @require_auth
    def api_batch():
        data = request.get_json()
        if not data or 'action' not in data or 'items' not in data: return jsonify({'error': 'Requête invalide'}), 400
        action, items, target_folder_id = data['action'], data['items'], data.get('target_folder_id')
        if action in ['move', 'copy'] and target_folder_id is not None:
            parent = models.get_folder_by_id(app.config['DATABASE'], target_folder_id)
            if not parent or parent['user_id'] != g.user['id']: return jsonify({'error': 'Dossier cible introuvable'}), 404
        success_count, error_count = 0, 0
        for item in items:
            item_type, item_id = item.get('type'), item.get('id')
            if item_type == 'file':
                file = models.get_file_by_id(app.config['DATABASE'], item_id)
                if not file or file['user_id'] != g.user['id']: error_count += 1; continue
                if action == 'delete':
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file['filename'])
                    if os.path.exists(filepath): os.remove(filepath)
                    models.delete_file(app.config['DATABASE'], item_id); success_count += 1
                elif action == 'move':
                    new_name = models.get_unique_file_name(app.config['DATABASE'], file['original_name'], target_folder_id, g.user['id'])
                    if new_name != file['original_name']: models.rename_file(app.config['DATABASE'], item_id, new_name)
                    models.move_file(app.config['DATABASE'], item_id, target_folder_id); success_count += 1
                elif action == 'copy':
                    new_file = models.copy_file_record(app.config['DATABASE'], item_id, target_folder_id, g.user['id'], app.config['UPLOAD_FOLDER'])
                    if new_file: success_count += 1
                    else: error_count += 1
            elif item_type == 'folder':
                folder = models.get_folder_by_id(app.config['DATABASE'], item_id)
                if not folder or folder['user_id'] != g.user['id']: error_count += 1; continue
                if action == 'delete':
                    files_to_delete = models.get_all_files_in_folder_recursive(app.config['DATABASE'], item_id)
                    for f in files_to_delete:
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f['filename'])
                        if os.path.exists(filepath): os.remove(filepath)
                    models.delete_folder(app.config['DATABASE'], item_id); success_count += 1
                elif action == 'move':
                    new_name = models.get_unique_folder_name(app.config['DATABASE'], folder['name'], target_folder_id, g.user['id'])
                    if new_name != folder['name']: models.rename_folder(app.config['DATABASE'], item_id, new_name)
                    success = models.move_folder(app.config['DATABASE'], item_id, target_folder_id)
                    if success: success_count += 1
                    else: error_count += 1
                elif action == 'copy':
                    new_folder = models.copy_folder_record(app.config['DATABASE'], item_id, target_folder_id, g.user['id'], app.config['UPLOAD_FOLDER'])
                    if new_folder: success_count += 1
                    else: error_count += 1
        return jsonify({'success': True, 'success_count': success_count, 'error_count': error_count})

    # ─── File serving ─────────────────────────────────────

    @app.route('/share/file/<filename>')
    def cdn_file(filename):
        conn = models.get_db(app.config['DATABASE'])
        file = conn.execute('SELECT * FROM files WHERE filename = ?', (filename,)).fetchone()
        conn.close()
        if not file: abort(404)
        
        is_owner = ('user_id' in session and session['user_id'] == file['user_id'])
        if not is_owner:
            if not file['is_public']: abort(404)
            if models.is_share_expired(file['expires_at']): abort(410)
            if file['password_hash'] and not session.get(f"share_unlocked_{file['share_token']}"):
                return redirect(url_for('share_page', token=file['share_token']))
                
        models.increment_download_count(app.config['DATABASE'], file['id'])
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, download_name=file['original_name'])

    @app.route('/share/raw/<filename>')
    def cdn_file_raw(filename):
        conn = models.get_db(app.config['DATABASE'])
        file = conn.execute('SELECT * FROM files WHERE filename = ?', (filename,)).fetchone()
        conn.close()
        if not file: abort(404)
        
        is_owner = ('user_id' in session and session['user_id'] == file['user_id'])
        if not is_owner:
            if not file['is_public']: abort(404)
            if models.is_share_expired(file['expires_at']): abort(410)
            if file['password_hash'] and not session.get(f"share_unlocked_{file['share_token']}"):
                abort(403)
                
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, mimetype=file['mime_type'])

    # ─── Admin Panel ───────────────────────────────────────────

    @app.route('/admin', methods=['GET', 'POST'])
    def admin():
        if request.method == 'POST':
            if 'admin_token' in request.form:
                token = request.form.get('admin_token', '').strip()
                if token == app.config['ADMIN_TOKEN']:
                    session['is_admin'] = True; flash('Connecté en tant qu\'administrateur.', 'success')
                else: flash('Token administrateur invalide.', 'error')
                return redirect(url_for('admin'))
            elif session.get('is_admin'):
                action = request.form.get('action')
                if action == 'save_settings':
                    reg_enabled = '1' if request.form.get('registration_enabled') else '0'
                    quota_val_str, quota_unit = request.form.get('quota_val', '1'), request.form.get('quota_unit', 'GB')
                    try:
                        val = float(quota_val_str)
                        quota_bytes = int(val * 1024 * 1024 * (1024 if quota_unit == 'GB' else 1))
                        models.set_setting(app.config['DATABASE'], 'max_quota_bytes', str(quota_bytes))
                        models.set_setting(app.config['DATABASE'], 'registration_enabled', reg_enabled)
                        flash('Paramètres mis à jour.', 'success')
                    except ValueError: flash('Valeur de quota invalide.', 'error')
                elif action == 'logout': session.pop('is_admin', None); flash('Déconnecté de l\'interface d\'administration.', 'success')
                return redirect(url_for('admin'))
        if not session.get('is_admin'): return render_template('admin_login.html')
        reg_enabled = models.get_setting(app.config['DATABASE'], 'registration_enabled', '1') == '1'
        quota_bytes = int(models.get_setting(app.config['DATABASE'], 'max_quota_bytes', 1073741824))
        if quota_bytes >= 1024 * 1024 * 1024: quota_val, quota_unit = round(quota_bytes / (1024**3), 2), 'GB'
        else: quota_val, quota_unit = round(quota_bytes / (1024**2), 2), 'MB'
        if quota_val == int(quota_val): quota_val = int(quota_val)
        return render_template('admin.html', registration_enabled=reg_enabled, quota_val=quota_val, quota_unit=quota_unit)

    # ─── Error handlers ─────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e): return render_template('base.html', error_code=404, error_message="Page introuvable"), 404

    @app.errorhandler(413)
    def too_large(e): return jsonify({'error': 'Fichier trop volumineux'}), 413
