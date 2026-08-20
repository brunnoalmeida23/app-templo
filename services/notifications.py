import os
import requests


ONESIGNAL_URL = "https://api.onesignal.com/notifications"


def _credenciais():
    app_id = os.environ.get('ONESIGNAL_APP_ID', '').strip()
    api_key = os.environ.get('ONESIGNAL_API_KEY', '').strip()
    return app_id, api_key


def _enviar(payload):
    """
    Envia um payload ao OneSignal.

    Retorna True somente quando o OneSignal realmente cria
    a mensagem e devolve um ID.
    """
    app_id, api_key = _credenciais()

    if not app_id:
        print("[OneSignal] ERRO: ONESIGNAL_APP_ID não configurado.")
        return False

    if not api_key:
        print("[OneSignal] ERRO: ONESIGNAL_API_KEY não configurada.")
        return False

    dados = {
        "app_id": app_id,
        "target_channel": "push",
        **payload
    }

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json"
    }

    try:
        resposta = requests.post(
            ONESIGNAL_URL,
            json=dados,
            headers=headers,
            timeout=15
        )

        print(
            f"[OneSignal] HTTP {resposta.status_code} - "
            f"{resposta.text}"
        )

        if not resposta.ok:
            return False

        try:
            resultado = resposta.json()
        except ValueError:
            print("[OneSignal] ERRO: resposta não é JSON.")
            return False

        mensagem_id = resultado.get("id")

        if not mensagem_id:
            print(
                "[OneSignal] AVISO: requisição aceita, "
                "mas nenhuma mensagem foi criada."
            )
            return False

        print(
            f"[OneSignal] Mensagem criada com sucesso: "
            f"{mensagem_id}"
        )

        return True

    except requests.RequestException as erro:
        print(f"[OneSignal] ERRO de conexão: {erro}")
        return False


def _conteudo(titulo, mensagem):
    return {
        "headings": {
            "pt": titulo,
            "en": titulo
        },
        "contents": {
            "pt": mensagem,
            "en": mensagem
        },
        "isAnyWeb": True
    }


def enviar_push_interno(titulo, mensagem):
    """
    Envia somente para usuários marcados como membros internos do TUPBAO.
    """
    payload = _conteudo(titulo, mensagem)
    payload["filters"] = [
        {
            "field": "tag",
            "key": "tupbao_membro",
            "relation": "=",
            "value": "1"
        }
    ]
    return _enviar(payload)


def enviar_push_publico(titulo, mensagem):
    """
    Envia somente para consulentes/público externo inscritos nesse canal.
    """
    payload = _conteudo(titulo, mensagem)
    payload["filters"] = [
        {
            "field": "tag",
            "key": "tupbao_publico",
            "relation": "=",
            "value": "1"
        }
    ]
    return _enviar(payload)


def enviar_push_turma(turma_id, titulo, mensagem):
    """
    Envia somente para usuários marcados como alunos da turma informada.

    Exemplo:
        turma_id = 1
        tag OneSignal = turma_1 = 1
    """
    try:
        turma_id = int(turma_id)
    except (TypeError, ValueError):
        print("[OneSignal] ERRO: turma_id inválido.")
        return False

    payload = _conteudo(titulo, mensagem)
    payload["filters"] = [
        {
            "field": "tag",
            "key": f"turma_{turma_id}",
            "relation": "=",
            "value": "1"
        }
    ]
    return _enviar(payload)


def enviar_notificacao(titulo, mensagem):
    """
    COMPATIBILIDADE TEMPORÁRIA.

    Mantém o comportamento antigo enquanto as chamadas existentes do sistema
    ainda não forem migradas para enviar_push_interno(), enviar_push_publico()
    ou enviar_push_turma().

    NÃO usar para os novos avisos segmentados.
    """
    payload = _conteudo(titulo, mensagem)
    payload["included_segments"] = ["Active Subscriptions"]
    return _enviar(payload)