import os
import requests


def enviar_notificacao(titulo, mensagem):
    """
    Envia uma notificação push pelo OneSignal.

    IMPORTANTE:
    Nesta primeira etapa o comportamento é exatamente o mesmo do sistema atual:
    envia para o segmento "Active Subscriptions".

    A segmentação por filhos, público e turmas será implementada depois,
    sem alterar as chamadas existentes de uma vez.
    """
    try:
        onesignal_app_id = os.environ.get('ONESIGNAL_APP_ID', '')
        onesignal_api_key = os.environ.get('ONESIGNAL_API_KEY', '')

        if not onesignal_app_id or not onesignal_api_key:
            return False

        url = "https://onesignal.com/api/v1/notifications"

        headers = {
            "Authorization": f"Bearer {onesignal_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "app_id": onesignal_app_id,
            "headings": {"en": titulo},
            "contents": {"en": mensagem},
            "included_segments": ["Active Subscriptions"]
        }

        response = requests.post(
            url,
            json=data,
            headers=headers,
            timeout=15
        )

        return response.ok

    except Exception:
        return False