/* ═══════════════════════════════════════════
   FastFile — Dashboard Interactions
   NO TOKEN IS EXPOSED HERE — auth is server-side
   ═══════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const uploadProgress = document.getElementById('upload-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const filesGrid = document.getElementById('files-grid');
    const foldersGrid = document.getElementById('folders-grid');
    const searchInput = document.getElementById('search-input');
    const toastContainer = document.getElementById('toast-container');
    const currentFolderId = window.__CURRENT_FOLDER_ID || null;

    // ─── Toast ────────────────────────────
    function showToast(message, type = 'info') {
        const t = document.createElement('div');
        t.className = `toast toast-${type}`;
        t.textContent = message;
        toastContainer.appendChild(t);
        setTimeout(() => { t.classList.add('toast-out'); setTimeout(() => t.remove(), 300); }, 3000);
    }

    // ─── Drag & Drop ──────────────────────
    let isUploading = false;

    if (uploadZone) {
        ['dragenter','dragover'].forEach(e => uploadZone.addEventListener(e, ev => { 
            ev.preventDefault(); 
            if (!isUploading) uploadZone.classList.add('drag-over'); 
        }));
        ['dragleave','drop'].forEach(e => uploadZone.addEventListener(e, ev => { 
            ev.preventDefault(); 
            uploadZone.classList.remove('drag-over'); 
        }));
        uploadZone.addEventListener('drop', ev => { 
            if (isUploading) return;
            if (ev.dataTransfer.files.length) uploadFiles(ev.dataTransfer.files); 
        });
        uploadZone.addEventListener('click', ev => { 
            if (isUploading) return;
            if (ev.target.tagName !== 'LABEL' && ev.target.tagName !== 'INPUT') fileInput.click(); 
        });
        fileInput.addEventListener('change', () => { 
            if (isUploading) return;
            if (fileInput.files.length) uploadFiles(fileInput.files); 
        });
    }

    // ─── Upload ───────────────────────────
    async function uploadFiles(fileList) {
        if (isUploading) return;
        isUploading = true;

        const content = uploadZone.querySelector('.upload-content');
        content.style.display = 'none';
        uploadProgress.hidden = false;
        uploadZone.style.pointerEvents = 'none';
        uploadZone.style.opacity = '0.8';

        let uploaded = 0;
        const total = fileList.length;

        for (const file of fileList) {
            try {
                await new Promise((resolve, reject) => {
                    const xhr = new XMLHttpRequest();
                    const fd = new FormData();
                    fd.append('file', file);
                    if (window.__CURRENT_FOLDER_ID) fd.append('folder_id', window.__CURRENT_FOLDER_ID);

                    xhr.upload.addEventListener('progress', e => {
                        if (e.lengthComputable) {
                            const filePercent = (e.loaded / e.total) * 100;
                            const overallPercent = ((uploaded + (e.loaded / e.total)) / total) * 100;
                            progressFill.style.width = `${overallPercent}%`;
                            progressText.textContent = `Upload de ${file.name} (${Math.round(filePercent)}%)... (${uploaded+1}/${total})`;
                        }
                    });

                    xhr.onload = () => {
                        if (xhr.status >= 200 && xhr.status < 300) {
                            const data = JSON.parse(xhr.responseText);
                            if (data.success) {
                                uploaded++;
                                showToast(`${file.name} uploadé !`, 'success');
                                resolve();
                            } else {
                                showToast(data.error || 'Erreur upload', 'error');
                                resolve(); // Continue anyway
                            }
                        } else {
                            showToast('Erreur serveur', 'error');
                            resolve();
                        }
                    };

                    xhr.onerror = () => {
                        showToast('Erreur réseau', 'error');
                        resolve();
                    };

                    xhr.open('POST', '/api/upload');
                    xhr.send(fd);
                });
            } catch (err) {
                console.error(err);
            }
        }

        progressText.textContent = `${uploaded}/${total} fichier(s) uploadé(s)`;
        setTimeout(() => {
            isUploading = false;
            window.location.reload();
        }, 800);
    }

    // ─── Search ───────────────────────────
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const q = searchInput.value.toLowerCase();
            document.querySelectorAll('.file-card').forEach(c => { c.style.display = (c.dataset.name || '').includes(q) ? '' : 'none'; });
            document.querySelectorAll('.folder-card').forEach(c => { c.style.display = (c.dataset.name || '').includes(q) ? '' : 'none'; });
        });
    }

    // ─── File Actions (delegation) ────────
    const previewModal = document.getElementById('preview-modal');
    const previewModalContent = document.getElementById('preview-modal-content');
    const previewModalTitle = document.getElementById('preview-modal-title');
    const previewModalClose = document.getElementById('preview-modal-close');

    function openPreview(url, mime, name) {
        if (!previewModal) return;
        previewModalTitle.textContent = name;
        previewModalContent.innerHTML = ''; 

        if (mime.startsWith('image/')) {
            const img = document.createElement('img');
            img.src = url;
            img.style.cssText = 'max-width: 100%; max-height: 80vh; border-radius: 8px; object-fit: contain;';
            previewModalContent.appendChild(img);
        } else if (mime.startsWith('video/')) {
            const video = document.createElement('video');
            video.src = url;
            video.controls = true;
            video.autoplay = true;
            video.style.cssText = 'max-width: 100%; max-height: 80vh; border-radius: 8px; outline: none; background: black;';
            previewModalContent.appendChild(video);
        } else if (mime.startsWith('audio/')) {
            const audio = document.createElement('audio');
            audio.src = url;
            audio.controls = true;
            audio.autoplay = true;
            audio.style.cssText = 'width: 100%; min-width: 300px; outline: none; margin: 20px 0;';
            previewModalContent.appendChild(audio);
        } else if (mime.startsWith('text/') || mime === 'application/pdf') {
            const iframe = document.createElement('iframe');
            iframe.src = url;
            iframe.style.cssText = 'width: 80vw; height: 80vh; border: none; border-radius: 8px; background: white;';
            previewModalContent.appendChild(iframe);
        }
        previewModal.hidden = false;
    }

    if (previewModalClose) previewModalClose.addEventListener('click', () => {
        previewModal.hidden = true;
        previewModalContent.innerHTML = ''; 
    });
    if (previewModal) previewModal.addEventListener('click', ev => {
        if (ev.target === previewModal) {
            previewModal.hidden = true;
            previewModalContent.innerHTML = '';
        }
    });

    if (filesGrid) {
        filesGrid.addEventListener('click', ev => {
            const btn = ev.target.closest('button');
            const checkbox = ev.target.closest('.item-checkbox');
            
            // If click is on a button or checkbox, let existing logic handle it
            if (btn || checkbox) {
                if (btn) {
                    if (btn.classList.contains('btn-delete')) openDeleteModal(btn.dataset.id);
                    else if (btn.classList.contains('btn-toggle')) openShareModal('file', btn.dataset.id);
                    else if (btn.classList.contains('btn-rename')) openRenameModal(btn.dataset.id, btn.dataset.name);
                    else if (btn.classList.contains('btn-copy-link')) {
                        navigator.clipboard.writeText(window.location.origin + btn.dataset.cdnUrl).then(() => showToast('Lien public copié !', 'success'));
                    }
                    else if (btn.classList.contains('btn-clipboard-copy')) setClipboard('copy', [{type: 'file', id: btn.dataset.id, name: btn.dataset.name}]);
                    else if (btn.classList.contains('btn-clipboard-cut')) setClipboard('cut', [{type: 'file', id: btn.dataset.id, name: btn.dataset.name}]);
                }
                return;
            }

            // Otherwise, check if card is previewable
            const card = ev.target.closest('.file-card');
            if (card && card.dataset.previewable === 'true') {
                openPreview(card.dataset.url, card.dataset.mime, card.dataset.name);
            }
        });
    }

    // Global Escape Key Listener
    document.addEventListener('keydown', ev => {
        if (ev.key === 'Escape') {
            if (previewModal && !previewModal.hidden) {
                previewModalClose.click();
            } else if (shareModal && !shareModal.hidden) {
                shareModal.hidden = true;
            } else if (typeof folderModal !== 'undefined' && !folderModal.hidden) {
                folderCancel.click();
            } else if (typeof renameModal !== 'undefined' && !renameModal.hidden) {
                renameCancel.click();
            } else if (typeof deleteModal !== 'undefined' && !deleteModal.hidden) {
                deleteCancel.click();
            } else if (typeof deleteFolderModal !== 'undefined' && !deleteFolderModal.hidden) {
                deleteFolderCancel.click();
            }
        }
    });


    // ─── Delete File Modal ────────────────
    let deleteFileId = null;
    const deleteModal = document.getElementById('delete-modal');
    const deleteCancel = document.getElementById('delete-cancel');
    const deleteConfirm = document.getElementById('delete-confirm');

    function openDeleteModal(id) { deleteFileId = id; deleteModal.hidden = false; }
    if (deleteCancel) deleteCancel.addEventListener('click', () => deleteModal.hidden = true);
    if (deleteModal) deleteModal.addEventListener('click', ev => { if (ev.target === deleteModal) deleteModal.hidden = true; });
    if (deleteConfirm) deleteConfirm.addEventListener('click', async () => {
        if (!deleteFileId) return;
        try {
            const res = await fetch(`/api/files/${deleteFileId}/delete`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                const card = document.querySelector(`.file-card[data-id="${deleteFileId}"]`);
                if (card) { card.style.transform = 'scale(0.9)'; card.style.opacity = '0'; }
                deleteModal.hidden = true; showToast('Fichier supprimé', 'success');
                setTimeout(() => window.location.reload(), 300);
            } else showToast(data.error, 'error');
        } catch { showToast('Erreur réseau', 'error'); }
    });

    // ─── Rename File Modal ────────────────
    let renameFileId = null;
    const renameModal = document.getElementById('rename-modal');
    const renameInput = document.getElementById('rename-input');
    const renameCancel = document.getElementById('rename-cancel');
    const renameConfirm = document.getElementById('rename-confirm');

    function openRenameModal(id, name) { renameFileId = id; renameInput.value = name; renameModal.hidden = false; setTimeout(() => renameInput.focus(), 100); }
    if (renameCancel) renameCancel.addEventListener('click', () => renameModal.hidden = true);
    if (renameModal) renameModal.addEventListener('click', ev => { if (ev.target === renameModal) renameModal.hidden = true; });
    if (renameInput) renameInput.addEventListener('keydown', ev => { if (ev.key === 'Enter') renameConfirm.click(); });
    if (renameConfirm) renameConfirm.addEventListener('click', async () => {
        if (!renameFileId || !renameInput.value.trim()) return;
        try {
            const res = await fetch(`/api/files/${renameFileId}/rename`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: renameInput.value.trim() }) });
            const data = await res.json();
            if (data.success) { renameModal.hidden = true; showToast('Fichier renommé', 'success'); setTimeout(() => window.location.reload(), 500); }
            else showToast(data.error, 'error');
        } catch { showToast('Erreur réseau', 'error'); }
    });

    // ─── New Folder Modal ─────────────────
    const folderModal = document.getElementById('folder-modal');
    const folderInput = document.getElementById('folder-name-input');
    const folderCancel = document.getElementById('folder-cancel');
    const folderConfirm = document.getElementById('folder-confirm');
    const folderModalTitle = document.getElementById('folder-modal-title');
    const newFolderBtn = document.getElementById('new-folder-btn');
    let renameFolderId = null;

    if (newFolderBtn) newFolderBtn.addEventListener('click', () => {
        renameFolderId = null;
        folderModalTitle.textContent = 'Nouveau dossier';
        folderConfirm.textContent = 'Créer';
        folderInput.value = '';
        folderModal.hidden = false;
        setTimeout(() => folderInput.focus(), 100);
    });
    if (folderCancel) folderCancel.addEventListener('click', () => folderModal.hidden = true);
    if (folderModal) folderModal.addEventListener('click', ev => { if (ev.target === folderModal) folderModal.hidden = true; });
    if (folderInput) folderInput.addEventListener('keydown', ev => { if (ev.key === 'Enter') folderConfirm.click(); });
    if (folderConfirm) folderConfirm.addEventListener('click', async () => {
        const name = folderInput.value.trim();
        if (!name) return;
        if (renameFolderId) {
            // Rename folder
            try {
                const res = await fetch(`/api/folders/${renameFolderId}/rename`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
                const data = await res.json();
                if (data.success) { folderModal.hidden = true; showToast('Dossier renommé', 'success'); setTimeout(() => window.location.reload(), 500); }
                else showToast(data.error, 'error');
            } catch { showToast('Erreur réseau', 'error'); }
        } else {
            // Create folder
            try {
                const res = await fetch('/api/folders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, parent_id: currentFolderId }) });
                const data = await res.json();
                if (data.success) { folderModal.hidden = true; showToast('Dossier créé', 'success'); setTimeout(() => window.location.reload(), 500); }
                else showToast(data.error, 'error');
            } catch { showToast('Erreur réseau', 'error'); }
        }
    });

    // ─── Folder Actions (delegation) ──────
    let deleteFolderId = null;
    const deleteFolderModal = document.getElementById('delete-folder-modal');
    const deleteFolderCancel = document.getElementById('delete-folder-cancel');
    const deleteFolderConfirm = document.getElementById('delete-folder-confirm');

    if (foldersGrid) {
        foldersGrid.addEventListener('click', ev => {
            const btn = ev.target.closest('button');
            if (!btn) return;
            ev.preventDefault();
            ev.stopPropagation();
            if (btn.classList.contains('btn-rename-folder')) {
                renameFolderId = btn.dataset.id;
                folderModalTitle.textContent = 'Renommer le dossier';
                folderConfirm.textContent = 'Renommer';
                folderInput.value = btn.dataset.name;
                folderModal.hidden = false;
                setTimeout(() => folderInput.focus(), 100);
            } else if (btn.classList.contains('btn-delete-folder')) {
                deleteFolderId = btn.dataset.id;
                deleteFolderModal.hidden = false;
            } else if (btn.classList.contains('btn-toggle-folder')) {
                const fid = btn.dataset.id;
                openShareModal('folder', fid);
            } else if (btn.classList.contains('btn-copy-folder-link')) {
                navigator.clipboard.writeText(btn.dataset.url).then(() => showToast('Lien du dossier copié !', 'success'));
            }
        });
    }

    if (deleteFolderCancel) deleteFolderCancel.addEventListener('click', () => deleteFolderModal.hidden = true);
    if (deleteFolderModal) deleteFolderModal.addEventListener('click', ev => { if (ev.target === deleteFolderModal) deleteFolderModal.hidden = true; });
    if (deleteFolderConfirm) deleteFolderConfirm.addEventListener('click', async () => {
        if (!deleteFolderId) return;
        try {
            const res = await fetch(`/api/folders/${deleteFolderId}/delete`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                const card = document.querySelector(`.folder-card[data-id="${deleteFolderId}"]`);
                if (card) { card.style.transform = 'scale(0.9)'; card.style.opacity = '0'; }
                deleteFolderModal.hidden = true; showToast('Dossier supprimé', 'success');
                setTimeout(() => window.location.reload(), 300);
            } else showToast(data.error, 'error');
        } catch { showToast('Erreur réseau', 'error'); }
    });

    // ─── Multi-Selection ──────────────────
    const selectionBar = document.getElementById('selection-bar');
    const selectionLabel = document.getElementById('selection-label');
    const selCopyBtn = document.getElementById('sel-copy-btn');
    const selCutBtn = document.getElementById('sel-cut-btn');
    const selDeleteBtn = document.getElementById('sel-delete-btn');
    const selCancelBtn = document.getElementById('sel-cancel-btn');
    
    let selectedItems = new Map();

    function updateSelection() {
        if (selectedItems.size > 0) {
            selectionBar.hidden = false;
            selectionLabel.textContent = `${selectedItems.size} élément(s) sélectionné(s)`;
        } else {
            selectionBar.hidden = true;
        }
    }

    document.querySelectorAll('.item-checkbox').forEach(cb => {
        cb.addEventListener('change', ev => {
            const card = cb.closest('.file-card, .folder-card');
            const type = cb.dataset.type;
            const id = cb.dataset.id;
            const name = card.dataset.name;
            const key = `${type}-${id}`;
            
            if (cb.checked) {
                card.classList.add('selected');
                selectedItems.set(key, {type, id, name});
            } else {
                card.classList.remove('selected');
                selectedItems.delete(key);
            }
            updateSelection();
        });
    });

    if (selCancelBtn) selCancelBtn.addEventListener('click', () => {
        selectedItems.clear();
        document.querySelectorAll('.item-checkbox').forEach(cb => cb.checked = false);
        document.querySelectorAll('.file-card, .folder-card').forEach(c => c.classList.remove('selected'));
        updateSelection();
    });

    if (selDeleteBtn) selDeleteBtn.addEventListener('click', async () => {
        if (!confirm(`Supprimer ${selectedItems.size} élément(s) ?`)) return;
        const items = Array.from(selectedItems.values());
        try {
            const res = await fetch('/api/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'delete', items })
            });
            const data = await res.json();
            if (data.success) {
                showToast(`${data.success_count} élément(s) supprimé(s)`, 'success');
                setTimeout(() => window.location.reload(), 500);
            } else showToast(data.error || 'Erreur lors de la suppression', 'error');
        } catch { showToast('Erreur réseau', 'error'); }
    });

    if (selCopyBtn) selCopyBtn.addEventListener('click', () => {
        setClipboard('copy', Array.from(selectedItems.values()));
        selCancelBtn.click();
    });

    if (selCutBtn) selCutBtn.addEventListener('click', () => {
        setClipboard('cut', Array.from(selectedItems.values()));
        selCancelBtn.click();
    });

    // ─── Clipboard (Copy / Cut / Paste) ───
    const pasteBar = document.getElementById('paste-bar');
    const pasteLabel = document.getElementById('paste-label');
    const pasteHereBtn = document.getElementById('paste-here-btn');
    const pasteCancelBtn = document.getElementById('paste-cancel-btn');
    
    let clipboard = { mode: null, items: [] };
    try {
        const stored = sessionStorage.getItem('fastfile_clipboard');
        if (stored) {
            clipboard = JSON.parse(stored);
            if (clipboard.fileId) {
                clipboard.items = [{type: 'file', id: clipboard.fileId, name: clipboard.fileName}];
            }
            if (clipboard.items && clipboard.items.length > 0) {
                const modeLabel = clipboard.mode === 'copy' ? 'Copier' : 'Couper';
                pasteLabel.textContent = `${modeLabel} : ${clipboard.items.length} élément(s)`;
                pasteBar.hidden = false;
                if (clipboard.mode === 'cut') {
                    clipboard.items.forEach(item => {
                        const card = document.querySelector(`.${item.type}-card[data-id="${item.id}"]`);
                        if (card) card.classList.add('cut-highlight');
                    });
                }
            }
        }
    } catch (e) {}

    function setClipboard(mode, items) {
        clipboard = { mode, items };
        sessionStorage.setItem('fastfile_clipboard', JSON.stringify(clipboard));
        const modeLabel = mode === 'copy' ? 'Copier' : 'Couper';
        pasteLabel.textContent = `${modeLabel} : ${items.length} élément(s)`;
        pasteBar.hidden = false;
        
        document.querySelectorAll('.file-card, .folder-card').forEach(c => c.classList.remove('cut-highlight'));
        if (mode === 'cut') {
            items.forEach(item => {
                const card = document.querySelector(`.${item.type}-card[data-id="${item.id}"]`);
                if (card) card.classList.add('cut-highlight');
            });
        }
        showToast(`${items.length} élément(s) ${mode === 'copy' ? 'copié(s)' : 'coupé(s)'} — naviguez puis collez`, 'info');
    }

    if (pasteCancelBtn) pasteCancelBtn.addEventListener('click', () => {
        clipboard = { mode: null, items: [] };
        sessionStorage.removeItem('fastfile_clipboard');
        pasteBar.hidden = true;
        document.querySelectorAll('.file-card, .folder-card').forEach(c => c.classList.remove('cut-highlight'));
    });

    if (pasteHereBtn) pasteHereBtn.addEventListener('click', async () => {
        if (!clipboard.items || clipboard.items.length === 0) return;
        try {
            const res = await fetch('/api/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: clipboard.mode,
                    target_folder_id: currentFolderId,
                    items: clipboard.items
                })
            });
            const data = await res.json();
            if (data.success) {
                pasteBar.hidden = true;
                const verb = clipboard.mode === 'copy' ? 'copiés' : 'déplacés';
                showToast(`${data.success_count} élément(s) ${verb} ici`, 'success');
                if (data.error_count > 0) showToast(`${data.error_count} erreur(s)`, 'error');
                clipboard = { mode: null, items: [] };
                sessionStorage.removeItem('fastfile_clipboard');
                setTimeout(() => window.location.reload(), 600);
            } else showToast(data.error, 'error');
        } catch { showToast('Erreur réseau', 'error'); }
    });

    document.addEventListener('keydown', ev => {
        if (ev.key === 'Escape') {
            if (clipboard.items && clipboard.items.length > 0) pasteCancelBtn.click();
            if (selectedItems.size > 0) selCancelBtn.click();
        }
    });

    // ─── Drag & Drop (Items) ──────────────
    document.querySelectorAll('.file-card, .folder-card').forEach(card => {
        card.addEventListener('dragstart', ev => {
            const type = card.dataset.type;
            const id = card.dataset.id;
            ev.dataTransfer.setData('application/json', JSON.stringify({type, id}));
            ev.dataTransfer.effectAllowed = 'move';
            card.classList.add('dragging');
        });
        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            document.querySelectorAll('.drop-target').forEach(t => t.classList.remove('drag-over'));
        });
    });

    document.querySelectorAll('.drop-target').forEach(target => {
        target.addEventListener('dragover', ev => {
            ev.preventDefault();
            ev.dataTransfer.dropEffect = 'move';
            target.classList.add('drag-over');
        });
        target.addEventListener('dragleave', () => {
            target.classList.remove('drag-over');
        });
        target.addEventListener('drop', async ev => {
            ev.preventDefault();
            target.classList.remove('drag-over');
            
            const data = ev.dataTransfer.getData('application/json');
            if (!data) return;
            
            try {
                const item = JSON.parse(data);
                const targetIdStr = target.dataset.id;
                const targetFolderId = targetIdStr === 'null' ? null : parseInt(targetIdStr);
                
                if (item.type === 'folder' && parseInt(item.id) === targetFolderId) return;

                const res = await fetch('/api/batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'move',
                        target_folder_id: targetFolderId,
                        items: [item]
                    })
                });
                const responseData = await res.json();
                if (responseData.success) {
                    showToast(`Élément déplacé`, 'success');
                    setTimeout(() => window.location.reload(), 500);
                } else showToast(responseData.error, 'error');
            } catch {}
        });
    });

    // ─── Share Config Modal ──────────────
    const shareModal = document.getElementById('share-modal');
    const shareSlugInput = document.getElementById('share-slug');
    const sharePasswordInput = document.getElementById('share-password');
    const shareExpiryInput = document.getElementById('share-expiry');
    const shareCancel = document.getElementById('share-cancel');
    const shareConfirm = document.getElementById('share-confirm');
    const shareUnshare = document.getElementById('share-unshare');
    const sharePrefix = document.getElementById('share-prefix');
    let shareContext = { type: null, id: null };

    window.openShareModal = function(type, id) {
        shareContext = { type, id };
        if (shareSlugInput) shareSlugInput.value = '';
        if (sharePasswordInput) sharePasswordInput.value = '';
        if (shareExpiryInput) shareExpiryInput.value = '';

        if (sharePrefix) {
            sharePrefix.textContent = type === 'folder' ? '/share/folder/' : '/share/';
        }

        // Show unshare only if already public
        const card = document.querySelector(`.${type === 'file' ? 'file' : 'folder'}-card[data-id="${id}"]`);
        const toggleBtn = card && (card.querySelector('.btn-toggle.active') || card.querySelector('.btn-toggle-folder.active'));
        if (shareUnshare) shareUnshare.style.display = toggleBtn ? 'inline-block' : 'none';

        if (shareModal) shareModal.hidden = false;
        setTimeout(() => { if (shareSlugInput) shareSlugInput.focus(); }, 100);
    };

    if (shareCancel) shareCancel.addEventListener('click', () => { shareModal.hidden = true; });
    if (shareModal) shareModal.addEventListener('click', ev => { if (ev.target === shareModal) shareModal.hidden = true; });

    if (shareUnshare) shareUnshare.addEventListener('click', async () => {
        const endpoint = shareContext.type === 'file'
            ? `/api/files/${shareContext.id}/toggle-public`
            : `/api/folders/${shareContext.id}/toggle-public`;
        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_public: false })
            });
            const data = await res.json();
            if (data.success) {
                shareModal.hidden = true;
                showToast('Partage désactivé', 'info');
                setTimeout(() => window.location.reload(), 500);
            } else showToast(data.error || 'Erreur', 'error');
        } catch { showToast('Erreur réseau', 'error'); }
    });

    if (shareConfirm) shareConfirm.addEventListener('click', async () => {
        const payload = {
            is_public: true,
            slug: (shareSlugInput && shareSlugInput.value.trim()) || '',
            password: (sharePasswordInput && sharePasswordInput.value.trim()) || '',
            expiry: (shareExpiryInput && shareExpiryInput.value) || ''
        };

        const endpoint = shareContext.type === 'file'
            ? `/api/files/${shareContext.id}/toggle-public`
            : `/api/folders/${shareContext.id}/toggle-public`;

        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                shareModal.hidden = true;
                showToast('Partage configuré !', 'success');
                if (data.share_url) {
                    navigator.clipboard.writeText(data.share_url).then(() => {
                        showToast('Lien copié dans le presse-papier !', 'info');
                    });
                }
                setTimeout(() => window.location.reload(), 800);
            } else {
                showToast(data.error || 'Erreur', 'error');
            }
        } catch {
            showToast('Erreur réseau', 'error');
        }
    });

});
