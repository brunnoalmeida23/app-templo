def enviar_notificacao(titulo, mensagem):
    """Envia notificação push via OneSignal usando variáveis de ambiente"""
    try:
        onesignal_app_id = os.environ.get('ONESIGNAL_APP_ID', '')
        onesignal_api_key = os.environ.get('ONESIGNAL_API_KEY', '')
        print(f"DEBUG: App ID: {onesignal_app_id[:10]}...")
        print(f"DEBUG: API Key: {onesignal_api_key[:10]}...")
        if not onesignal_app_id or not onesignal_api_key:
            print("DEBUG: Variáveis de ambiente não encontradas!")
            return
        url = "https://onesignal.com/api/v1/notifications"
        headers = {
            "Authorization": f"Basic {onesignal_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "app_id": onesignal_app_id,
            "headings": {"en": titulo},
            "contents": {"en": mensagem},
            "included_segments": ["Subscribed Users"]
        }
        response = requests.post(url, json=data, headers=headers)
        print(f"DEBUG: OneSignal response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"DEBUG: Erro ao enviar notificação: {e}")