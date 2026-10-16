LANGUAGES = [('en', 'English', ''), ('de', 'Deutsch', ''), ('fr', 'Français', ''), ('es', 'Español', ''), ('zh', '中文', '')]
TEXT = {
    'Connection': ['Verbindung', 'Connexion', 'Conexión', '连接'],
    'Service': ['Anbieter', 'Fournisseur', 'Proveedor', '提供商'],
    'API key': ['API-Schlüssel', 'Clé API', 'Clave API', 'API 密钥'],
    'Load models': ['Modelle laden', 'Charger les modèles', 'Cargar modelos', '加载模型'],
    'Choose model': ['Modell auswählen', 'Choisir un modèle', 'Elegir modelo', '选择模型'],
    'Model ID': ['Modell-ID', 'Identifiant du modèle', 'ID del modelo', '模型 ID'],
    'Open Studio Window': ['Studio öffnen', 'Ouvrir Studio', 'Abrir Studio', '打开 Studio'],
    'OpenCode Portable': ['OpenCode öffnen', 'Ouvrir OpenCode', 'Abrir OpenCode', '打开 OpenCode'],
    'Send': ['Senden', 'Envoyer', 'Enviar', '发送'],
    'Clear Chat': ['Chat leeren', 'Effacer le chat', 'Borrar chat', '清空聊天'],
    'Allow': ['Erlauben', 'Autoriser', 'Permitir', '允许'],
    'Reject': ['Ablehnen', 'Refuser', 'Rechazar', '拒绝'],
    'Generation': ['Generierung', 'Génération', 'Generación', '生成'],
    'Safety and preview': ['Sicherheit und Vorschau', 'Sécurité et aperçu', 'Seguridad y vista previa', '安全与预览'],
    'Asset services': ['Asset-Dienste', 'Services d’assets', 'Servicios de assets', '资产服务'],
    'External tools': ['Externe Werkzeuge', 'Outils externes', 'Herramientas externas', '外部工具'],
    'Workspace': ['Arbeitsbereich', 'Espace de travail', 'Espacio de trabajo', '工作区'],
    'External client': ['Externer Client', 'Client externe', 'Cliente externo', '外部客户端'],
    'Active model': ['Aktives Modell', 'Modèle actif', 'Modelo activo', '当前模型'],
    'Chat': ['Chat', 'Chat', 'Chat', '聊天'],
    'Recent activity': ['Letzte Aktivität', 'Activité récente', 'Actividad reciente', '最近活动'],
    'Quick guide': ['Kurzanleitung', 'Guide rapide', 'Guía rápida', '快速指南'],
    'Permission requested': ['Berechtigung erforderlich', 'Autorisation requise', 'Permiso requerido', '需要权限'],
    'Message': ['Nachricht', 'Message', 'Mensaje', '消息'],
    'Stop after current step': ['Nach aktuellem Schritt stoppen', 'Arrêter après l’étape', 'Detener después del paso', '当前步骤后停止'],
    'New conversation': ['Neues Gespräch', 'Nouvelle conversation', 'Nueva conversación', '新对话'],
    'No messages yet': ['Noch keine Nachrichten', 'Aucun message', 'Aún no hay mensajes', '暂无消息'],
    'Choose a provider or saved connection': ['Anbieter oder gespeicherte Verbindung wählen', 'Choisissez un fournisseur ou une connexion', 'Elige proveedor o conexión guardada', '选择服务或已保存连接'],
    'Enter a key, then load and select a model': ['Schlüssel eingeben, Modelle laden und auswählen', 'Saisissez la clé, chargez et choisissez un modèle', 'Introduce la clave, carga y elige un modelo', '输入密钥，加载并选择模型'],
    'Send a message here or open Studio': ['Nachricht senden oder Studio öffnen', 'Envoyez un message ou ouvrez Studio', 'Envía un mensaje o abre Studio', '发送消息或打开 Studio'],
    'Configure teams in Studio': ['Teams in Studio konfigurieren', 'Configurez les équipes dans Studio', 'Configura equipos en Studio', '在 Studio 中配置团队'],
    'Keep the access token private': ['Zugriffstoken geheim halten', 'Gardez le jeton privé', 'Mantén privado el token', '请勿公开访问令牌'],
    'Choose a connection': ['Verbindung auswählen', 'Choisir une connexion', 'Elegir conexión', '选择连接'],
    'Load and select a model': ['Modell laden und auswählen', 'Charger et choisir un modèle', 'Cargar y elegir modelo', '加载并选择模型'],
    'Send a message': ['Nachricht senden', 'Envoyer un message', 'Enviar un mensaje', '发送消息'],
    'Set up agents in Studio': ['Agenten in Studio einrichten', 'Configurer les agents dans Studio', 'Configurar agentes en Studio', '在 Studio 中设置代理'],
}


def t(text):
    from .core.util import prefs
    language = getattr(prefs(), "language", "en")
    languages = ["de", "fr", "es", "zh"]
    if language not in languages or text not in TEXT:
        return text
    return TEXT[text][languages.index(language)]
