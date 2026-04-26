import os
import secrets
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN') or 'default-admin-token'
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    DATABASE = os.path.join(DATA_DIR, 'fastfile.db')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024 * 1024  # 10 GB
    ALLOWED_EXTENSIONS = {
        # Images
        'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp', 'tiff', 'heic', 'psd', 'ai',
        # Vidéos
        'mp4', 'webm', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'm4v', '3gp',
        # Audio
        'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma', 'aiff', 'opus',
        # Documents
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'md', 'rtf', 'odt', 'ods', 'odp', 'epub', 'pages', 'numbers', 'key',
        # Archives
        'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'iso', 'dmg', 'apk',
        # Code
        'json', 'xml', 'yaml', 'yml', 'html', 'css', 'js', 'py', 'c', 'cpp', 'h', 'hpp', 'java', 'go', 'rs', 'php', 'sh', 'sql', 'rb', 'ts', 'tsx', 'jsx', 'vue',
        # Fonts
        'ttf', 'otf', 'woff', 'woff2',
        # Others
        'exe', 'msi', 'bin', 'torrent', 'deb', 'rpm'
    }
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
